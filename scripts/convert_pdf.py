#!/usr/bin/env python3
"""Convert a PDF to an Obsidian Markdown note with MinerU."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

try:
    from .config import load_config, relative_to_vault, require_vault_root, vault_path
except ImportError:  # pragma: no cover - direct script execution
    from config import load_config, relative_to_vault, require_vault_root, vault_path  # type: ignore


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}


def sanitize_filename(name: str) -> str:
    if not name:
        return "untitled"
    sanitized = re.sub(r'[\/:*?"<>|]', "_", name)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized[:120].strip() or "untitled"


def extract_title_from_md(md_path: Path) -> str | None:
    try:
        lines = md_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    for line in lines[:30]:
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped.lstrip("# ").strip()
            if len(title) > 3:
                return title

    for line in lines[:30]:
        stripped = line.strip()
        if not stripped or stripped.startswith(("---", "metadata:", ">", "```")):
            continue
        if len(stripped) > 10:
            return stripped[:150]
    return None


def extract_pdf_title(pdf_path: Path) -> str | None:
    """Use common poppler tools if present, otherwise fall back to filename."""
    try:
        result = subprocess.run(["pdfinfo", str(pdf_path)], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith("Title:"):
                    title = line.split(":", 1)[1].strip()
                    if len(title) > 3:
                        return title
    except Exception:
        pass

    try:
        result = subprocess.run(["pdftotext", "-l", "1", str(pdf_path), "-"], capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            for line in result.stdout.splitlines()[:10]:
                stripped = line.strip()
                if len(stripped) > 10 and not re.match(r"^(doi|http|www\.|arxiv|preprint)", stripped, re.I):
                    return stripped[:150]
    except Exception:
        pass
    return None


def find_generated_md(work_dir: Path) -> tuple[Path | None, Path | None]:
    for md_file in work_dir.rglob("*.md"):
        if md_file.name != "README.md" and not md_file.name.startswith("experiment"):
            return md_file, md_file.parent
    return None, None


def move_images_to_attachments(src_dir: Path, attachments_dir: Path, filename_prefix: str) -> dict[str, str]:
    attachments_dir.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    counter = 0
    for image in sorted(src_dir.rglob("*")):
        if not image.is_file() or image.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        counter += 1
        new_name = f"{filename_prefix}-{counter:02d}{image.suffix.lower()}"
        destination = attachments_dir / new_name
        shutil.copy2(str(image), str(destination))
        try:
            relative = image.relative_to(src_dir)
        except ValueError:
            relative = Path(image.name)
        mapping[str(relative)] = new_name
        mapping[image.name] = new_name
        mapping[f"images/{image.name}"] = new_name
    return mapping


def update_image_paths_to_wikilinks(md_path: Path, path_mapping: Mapping[str, str], attachment_link_prefix: str) -> int:
    content = md_path.read_text(encoding="utf-8", errors="replace")
    replacements = 0
    pattern = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")

    def replacer(match: re.Match[str]) -> str:
        nonlocal replacements
        image_ref = match.group(1).strip()
        if image_ref.startswith(("http://", "https://", "data:")):
            return match.group(0)
        if image_ref.startswith("<") and image_ref.endswith(">"):
            image_ref = image_ref[1:-1].strip()
        filename = Path(image_ref).name
        new_name = path_mapping.get(filename) or path_mapping.get(image_ref)
        if not new_name:
            return match.group(0)
        replacements += 1
        return f"![[{attachment_link_prefix}/{new_name}]]"

    md_path.write_text(pattern.sub(replacer, content), encoding="utf-8")
    return replacements


def missing_local_image_refs(config: Mapping[str, Any], md_path: Path) -> list[str]:
    content = md_path.read_text(encoding="utf-8", errors="replace")
    missing: list[str] = []
    vault_root = require_vault_root(config)

    for raw_ref in re.findall(r"!\[\[([^\]]+)\]\]", content):
        ref = raw_ref.split("|", 1)[0].split("#", 1)[0].strip()
        if ref and not ref.startswith(("http://", "https://")) and not (vault_root / ref).exists():
            missing.append(ref)

    for raw_ref in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", content):
        ref = raw_ref.strip()
        if ref.startswith("<") and ref.endswith(">"):
            ref = ref[1:-1].strip()
        if not ref or ref.startswith(("http://", "https://", "data:")):
            continue
        ref_path = Path(ref)
        target = ref_path if ref_path.is_absolute() else md_path.parent / ref_path
        if not target.exists():
            missing.append(ref)
    return missing


def run_mineru(config: Mapping[str, Any], pdf_path: Path, work_dir: Path, timeout_sec: int) -> tuple[bool, str]:
    mineru = config.get("mineru", {})
    if not isinstance(mineru, Mapping):
        return False, "Invalid config: mineru must be an object"
    if not mineru.get("enabled", False):
        return False, "MinerU is disabled in config. Set mineru.enabled=true and mineru.bin to enable conversion."

    mineru_bin = str(mineru.get("bin") or "mineru")
    backend = str(mineru.get("backend") or "vlm-engine")
    effort = str(mineru.get("effort") or "high")
    device_mode = str(mineru.get("deviceMode") or "mps")
    command = [mineru_bin, "-p", str(pdf_path), "-o", str(work_dir), "-b", backend, "--effort", effort]
    env = os.environ.copy()
    if device_mode:
        env["MINERU_DEVICE_MODE"] = device_mode
    env.setdefault("MINERU_TASK_RESULT_TIMEOUT_SECONDS", str(int(mineru.get("taskResultTimeoutSec", timeout_sec))))
    env.setdefault("MINERU_TASK_RESULT_DOWNLOAD_TIMEOUT_SECONDS", str(int(mineru.get("taskResultDownloadTimeoutSec", 600))))
    env.setdefault("MINERU_PDF_RENDER_TIMEOUT", str(int(mineru.get("pdfRenderTimeoutSec", 600))))

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout_sec, env=env)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return False, f"MinerU timed out after {timeout_sec}s\n{stdout[-1000:]}\n{stderr[-1000:]}".strip()

    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "MinerU conversion failed").strip()
    return True, ""


def convert_pdf(
    config: Mapping[str, Any],
    pdf_path: str,
    zotero_id: str = "",
    output_dir: str = "",
    timeout_sec: int | None = None,
) -> dict[str, Any]:
    pdf = Path(pdf_path).expanduser().resolve()
    if not pdf.exists():
        return {"success": False, "error": f"PDF not found: {pdf}"}

    mineru = config.get("mineru", {})
    default_timeout = int(mineru.get("timeoutSec", 3600)) if isinstance(mineru, Mapping) else 3600
    timeout = timeout_sec or default_timeout
    notes_dir = Path(output_dir).expanduser() if output_dir else vault_path(config, "academicNotesDir")
    attachments_dir = vault_path(config, "attachmentsDir")
    work_root = vault_path(config, "mineruWorkDir")
    notes_dir.mkdir(parents=True, exist_ok=True)
    attachments_dir.mkdir(parents=True, exist_ok=True)
    work_root.mkdir(parents=True, exist_ok=True)

    work_dir = work_root / f"{sanitize_filename(pdf.stem)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    work_dir.mkdir(parents=True, exist_ok=True)
    mineru_ok, mineru_error = run_mineru(config, pdf, work_dir, timeout)
    if not mineru_ok:
        return {"success": False, "error": mineru_error, "pdf": str(pdf), "work_dir": str(work_dir)}

    generated_md, md_parent = find_generated_md(work_dir)
    if not generated_md or not md_parent:
        return {"success": False, "error": "No Markdown file found in MinerU output", "work_dir": str(work_dir)}

    title = extract_title_from_md(generated_md) or extract_pdf_title(pdf) or pdf.stem
    date_str = datetime.now().strftime("%Y-%m-%d")
    name_parts = [sanitize_filename(title), date_str]
    if zotero_id:
        name_parts.append(zotero_id)
    final_stem = sanitize_filename("-".join(name_parts))
    final_md = notes_dir / f"{final_stem}.md"

    mapping = move_images_to_attachments(md_parent, attachments_dir, final_stem)
    attachment_prefix = relative_to_vault(config, attachments_dir).as_posix()
    replacements = update_image_paths_to_wikilinks(generated_md, mapping, attachment_prefix)
    shutil.copy2(str(generated_md), str(final_md))
    missing = missing_local_image_refs(config, final_md)
    if missing:
        return {
            "success": False,
            "error": "Missing local image links after conversion",
            "pdf": str(pdf),
            "output_md": str(final_md),
            "missing_image_count": len(missing),
            "missing_image_refs": missing[:10],
            "work_dir": str(work_dir),
        }

    try:
        shutil.rmtree(work_dir)
    except OSError:
        pass

    return {
        "success": True,
        "pdf": str(pdf),
        "title": title,
        "zotero_id": zotero_id,
        "output_md": str(final_md),
        "output_filename": final_md.name,
        "images_moved": len(set(mapping.values())),
        "image_paths_updated": replacements,
        "missing_image_count": 0,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert a PDF to Markdown using MinerU.")
    parser.add_argument("pdf_path", help="Path to the local PDF")
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--zotero-id", default="", help="Zotero item key for the output filename")
    parser.add_argument("--output-dir", default="", help="Override output Markdown directory")
    parser.add_argument("--timeout-sec", type=int, default=None, help="Override MinerU timeout")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = convert_pdf(load_config(args.config), args.pdf_path, args.zotero_id, args.output_dir, args.timeout_sec)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
