#!/usr/bin/env python3
"""Attach a local PDF to a Zotero item by explicit DOI or item key."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping

try:
    from .config import load_config
except ImportError:  # pragma: no cover - direct script execution
    from config import load_config  # type: ignore

try:
    from PyPDF2 import PdfReader

    HAS_PYPDF2 = True
except ImportError:  # pragma: no cover - optional dependency
    HAS_PYPDF2 = False


def normalize_doi(doi: str | None) -> str:
    """Normalize a DOI string for lookup and comparison."""
    if not doi:
        return ""
    value = doi.strip()
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^doi:\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"[\.,;\)\]\>\:\?\!]+$", "", value.strip())
    return value


def validate_item_key(item_key: str | None) -> bool:
    """Return True for Zotero item keys such as VNPN6FHT."""
    return bool(re.fullmatch(r"[A-Z0-9]{8}", item_key or ""))


def zotero_config(config: Mapping[str, Any]) -> tuple[str, str, str]:
    zotero = config.get("zotero", {})
    if not isinstance(zotero, Mapping):
        raise SystemExit("Invalid config: zotero must be an object")
    api_key = os.environ.get(str(zotero.get("apiKeyEnv", "ZOTERO_API_KEY")))
    user_id = os.environ.get(str(zotero.get("userIdEnv", "ZOTERO_USER_ID")))
    group_id = os.environ.get(str(zotero.get("groupIdEnv", "ZOTERO_GROUP_ID")))
    api_base = str(zotero.get("apiBase", "https://api.zotero.org")).rstrip("/")

    if not api_key:
        raise SystemExit("Zotero API key is not set. Configure zotero.apiKeyEnv and export that variable.")
    if not user_id and not group_id:
        raise SystemExit("Set either the Zotero user ID env var or group ID env var.")

    prefix = f"users/{user_id}" if user_id else f"groups/{group_id}"
    return api_key, prefix, api_base


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from a PDF when PyPDF2 is installed."""
    if not HAS_PYPDF2:
        return ""
    try:
        reader = PdfReader(str(pdf_path))
    except Exception:
        return ""

    texts: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text()
        except Exception:
            text = None
        if text:
            texts.append(text)
    return "\n".join(texts)


def find_doi_in_text(text: str) -> str | None:
    """Find the first DOI in text. Prefer explicit --doi in production."""
    if not text:
        return None
    patterns = (
        r"(?:doi|DOI)[:\s/]+(10\.\d{4,}/[^\s\]\)\>\,\;\:]+)",
        r"\b(10\.\d{4,}/[^\s\]\)\>\,\;\:]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            doi = normalize_doi(match.group(1))
            doi = re.sub(
                r"(Key|Table|Figure|Supplement|Appendix|Section|Part|Chapter|Vol|No|Issue|Page|pp?|et al|and|or)$",
                "",
                doi,
                flags=re.IGNORECASE,
            ).strip()
            if doi.startswith("10."):
                return doi
    return None


def zotero_request(
    url: str,
    api_key: str,
    data: bytes | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: int = 30,
) -> Any:
    request_headers = {
        "Zotero-API-Version": "3",
        "Zotero-API-Key": api_key,
    }
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=data, headers=request_headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else None


def get_item_data(item_key: str, api_key: str, prefix: str, api_base: str) -> dict[str, Any] | None:
    try:
        item = zotero_request(f"{api_base}/{prefix}/items/{item_key}", api_key, timeout=15)
    except Exception:
        return None
    if isinstance(item, Mapping):
        data = item.get("data", {})
        return dict(data) if isinstance(data, Mapping) else None
    return None


def item_matches_doi(item_data: Mapping[str, Any], doi: str) -> bool:
    expected = normalize_doi(doi).lower()
    item_doi = normalize_doi(str(item_data.get("DOI", ""))).lower()
    if item_doi == expected:
        return True
    extra = str(item_data.get("extra", "")).lower()
    return f"doi: {expected}" in extra


def find_item_by_doi(doi: str, api_key: str, prefix: str, api_base: str) -> str | None:
    """Search Zotero for an existing top-level item with a matching DOI."""
    normalized = normalize_doi(doi)
    encoded = urllib.parse.quote(normalized, safe="")
    urls = (
        f"{api_base}/{prefix}/items?qmode=everything&q={encoded}",
        f"{api_base}/{prefix}/items?limit=200&sort=dateAdded&direction=desc",
    )
    for url in urls:
        try:
            items = zotero_request(url, api_key, timeout=30)
        except Exception:
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            data = item.get("data", {}) if isinstance(item, Mapping) else {}
            if data.get("itemType") == "attachment":
                continue
            if item_matches_doi(data, normalized):
                return str(data.get("key"))
    return None


def existing_pdf_attachment(parent_key: str, filename: str, api_key: str, prefix: str, api_base: str) -> str | None:
    try:
        children = zotero_request(f"{api_base}/{prefix}/items/{parent_key}/children", api_key, timeout=15)
    except Exception:
        return None
    if not isinstance(children, list):
        return None
    for child in children:
        data = child.get("data", {}) if isinstance(child, Mapping) else {}
        if data.get("itemType") == "attachment" and data.get("contentType") == "application/pdf":
            if data.get("filename") == filename or data.get("title") == filename:
                return str(data.get("key"))
    return None


def upload_pdf_to_zotero(
    parent_key: str,
    pdf_path: Path,
    api_key: str,
    prefix: str,
    api_base: str,
) -> dict[str, Any]:
    """Upload a local PDF as an imported Zotero attachment."""
    filename = pdf_path.name
    existing = existing_pdf_attachment(parent_key, filename, api_key, prefix, api_base)
    if existing:
        return {"success": True, "attachment_key": existing, "message": "Already exists"}

    file_size = pdf_path.stat().st_size
    file_mtime = str(int(pdf_path.stat().st_mtime * 1000))
    md5_hash = hashlib.md5(pdf_path.read_bytes()).hexdigest()
    attachment_data = {
        "itemType": "attachment",
        "parentItem": parent_key,
        "linkMode": "imported_file",
        "title": filename,
        "accessDate": "",
        "note": "",
        "tags": [],
        "relations": {},
        "contentType": "application/pdf",
        "charset": "",
        "filename": filename,
        "md5": None,
        "mtime": None,
    }

    try:
        create_result = zotero_request(
            f"{api_base}/{prefix}/items",
            api_key,
            data=json.dumps([attachment_data]).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        if isinstance(create_result, list) and create_result:
            attachment_key = create_result[0].get("key")
        elif isinstance(create_result, Mapping):
            attachment_key = create_result.get("successful", {}).get("0", {}).get("key")
        else:
            attachment_key = None
        if not attachment_key:
            return {"success": False, "error": "No attachment key returned"}

        time.sleep(2)
        auth_url = f"{api_base}/{prefix}/items/{attachment_key}/file"
        auth_form = urllib.parse.urlencode(
            {
                "md5": md5_hash,
                "filename": filename,
                "filesize": str(file_size),
                "mtime": file_mtime,
            }
        ).encode("utf-8")
        auth_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "If-None-Match": "*",
        }
        try:
            auth_result = zotero_request(auth_url, api_key, data=auth_form, headers=auth_headers, timeout=30)
        except urllib.error.HTTPError as error:
            if error.code == 412:
                return {"success": True, "attachment_key": str(attachment_key), "message": "File already in storage"}
            auth_result = zotero_request(
                auth_url,
                api_key,
                data=auth_form,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )

        if int(auth_result.get("exists", 0)) == 1:
            return {"success": True, "attachment_key": str(attachment_key), "message": "File already in storage"}

        upload_url = auth_result.get("url")
        content_type = auth_result.get("contentType")
        upload_prefix = auth_result.get("prefix")
        upload_suffix = auth_result.get("suffix")
        if not (upload_url and content_type and isinstance(upload_prefix, str) and isinstance(upload_suffix, str)):
            return {"success": False, "error": f"Invalid upload auth response: {auth_result}"}

        body = upload_prefix.encode("utf-8") + pdf_path.read_bytes() + upload_suffix.encode("utf-8")
        upload_req = urllib.request.Request(upload_url, data=body, headers={"Content-Type": content_type})
        with urllib.request.urlopen(upload_req, timeout=120) as upload_response:
            if upload_response.status not in (200, 201, 204):
                return {"success": False, "error": f"Upload HTTP {upload_response.status}"}

        upload_key = str(auth_result.get("uploadKey") or "")
        if not upload_key:
            return {"success": False, "error": "Missing uploadKey"}

        register_form = urllib.parse.urlencode({"upload": upload_key}).encode("utf-8")
        register_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "If-None-Match": "*",
        }
        try:
            zotero_request(auth_url, api_key, data=register_form, headers=register_headers, timeout=30)
        except urllib.error.HTTPError as error:
            if error.code != 412:
                raise
            zotero_request(
                auth_url,
                api_key,
                data=register_form,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
        return {"success": True, "attachment_key": str(attachment_key)}
    except urllib.error.HTTPError as error:
        return {"success": False, "error": f"HTTP {error.code}: {error.reason}"}
    except Exception as error:
        return {"success": False, "error": str(error)}


def fail(message: str, **extra: Any) -> None:
    payload = {"success": False, "error": message}
    payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(1)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Attach a local PDF to a Zotero item.")
    parser.add_argument("pdf_path", help="Path to the local PDF")
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--doi", help="Known DOI for the target paper")
    parser.add_argument("--item-key", help="Known Zotero parent item key")
    parser.add_argument("--dry-run", action="store_true", help="Resolve target item but do not upload")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pdf_path = Path(args.pdf_path).expanduser()
    if not pdf_path.exists():
        fail(f"File not found: {pdf_path}")

    config = load_config(args.config)
    api_key, prefix, api_base = zotero_config(config)
    doi = normalize_doi(args.doi)
    item_key = args.item_key.upper() if args.item_key else ""
    if item_key and not validate_item_key(item_key):
        fail(f"Invalid Zotero item key: {item_key}")

    doi_source = "argument" if doi else ("item-key" if item_key else "pdf")
    if item_key:
        item_data = get_item_data(item_key, api_key, prefix, api_base)
        if item_data is None:
            fail(f"Zotero item not found: {item_key}", item_key=item_key)
        if doi and not item_matches_doi(item_data, doi):
            fail(
                "Explicit item key DOI does not match --doi",
                item_key=item_key,
                doi=doi,
                item_title=item_data.get("title"),
                item_doi=item_data.get("DOI"),
            )
    else:
        if not doi:
            text = extract_text_from_pdf(pdf_path)
            if not text:
                fail("Could not extract text from PDF. Pass --doi or --item-key.")
            doi = find_doi_in_text(text) or ""
            if not doi:
                fail("No DOI found in PDF text. Pass --doi or --item-key.")
        item_key = find_item_by_doi(doi, api_key, prefix, api_base) or ""
        if not item_key:
            fail(f"No Zotero item found for DOI {doi}", doi=doi)

    if args.dry_run:
        print(
            json.dumps(
                {
                    "success": True,
                    "dry_run": True,
                    "doi": doi,
                    "doi_source": doi_source,
                    "item_key": item_key,
                    "pdf_path": str(pdf_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    result = upload_pdf_to_zotero(item_key, pdf_path, api_key, prefix, api_base)
    payload = {
        "success": bool(result.get("success")),
        "doi": doi,
        "doi_source": doi_source,
        "item_key": item_key,
        "pdf_path": str(pdf_path),
        "attachment_key": result.get("attachment_key"),
        "message": result.get("message"),
        "error": result.get("error"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["success"] else 1


if __name__ == "__main__":
    sys.exit(main())

