#!/usr/bin/env python3
"""Run PDF conversion and print a compact status message for agent delivery."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

try:
    from .config import load_config, require_vault_root, vault_path
except ImportError:  # pragma: no cover - direct script execution
    from config import load_config, require_vault_root, vault_path  # type: ignore


CONVERT_SCRIPT = Path(__file__).resolve().parent / "convert_pdf.py"


def tail_text(value: str | None, max_chars: int = 2000) -> str:
    if not value:
        return ""
    value = value.strip()
    return value if len(value) <= max_chars else value[-max_chars:]


def human_duration(seconds: float) -> str:
    total = int(seconds)
    minutes, second = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{second:02d}s"
    if minutes:
        return f"{minutes}m{second:02d}s"
    return f"{second}s"


def extract_json(stdout: str) -> dict[str, Any]:
    stripped = stdout.strip()
    if not stripped:
        raise ValueError("conversion produced no stdout")
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    for index in [i for i, char in enumerate(stdout) if char == "{"][::-1]:
        try:
            parsed = json.loads(stdout[index:].strip())
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("could not parse JSON result from conversion stdout")


def normalize_wikilink_ref(ref: str) -> str:
    return ref.split("|", 1)[0].split("#", 1)[0].strip()


def validate_markdown_images(config: Mapping[str, Any], md_path: Path) -> dict[str, Any]:
    text = md_path.read_text(encoding="utf-8", errors="replace")
    missing: list[str] = []
    vault_root = require_vault_root(config)

    wikilinks = re.findall(r"!\[\[([^\]]+)\]\]", text)
    for raw_ref in wikilinks:
        ref = normalize_wikilink_ref(raw_ref)
        if not ref or ref.startswith(("http://", "https://")):
            continue
        if not (vault_root / ref).exists():
            missing.append(ref)

    markdown_links = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    for raw_ref in markdown_links:
        ref = raw_ref.strip()
        if ref.startswith("<") and ref.endswith(">"):
            ref = ref[1:-1].strip()
        if not ref or ref.startswith(("http://", "https://", "data:")):
            continue
        ref_path = Path(ref)
        target = ref_path if ref_path.is_absolute() else md_path.parent / ref_path
        if not target.exists():
            missing.append(ref)

    stat = md_path.stat()
    return {
        "md_path": str(md_path),
        "size_bytes": stat.st_size,
        "chars": len(text),
        "wikilink_image_count": len(wikilinks),
        "markdown_image_count": len(markdown_links),
        "missing_image_count": len(missing),
        "missing_image_refs": missing[:10],
    }


def validate_conversion_result(config: Mapping[str, Any], result: Mapping[str, Any], zotero_id: str = "") -> dict[str, Any]:
    output_md = Path(str(result.get("output_md", ""))).expanduser()
    if not output_md.exists():
        return {"success": False, "error": f"output markdown not found: {output_md}"}

    output_name = output_md.name
    if zotero_id and zotero_id not in output_name:
        return {
            "success": False,
            "error": f"output markdown does not include expected Zotero ID {zotero_id}: {output_name}",
        }

    image_validation = validate_markdown_images(config, output_md)
    if image_validation["missing_image_count"]:
        return {
            "success": False,
            "error": "missing local image links after conversion",
            "validation": image_validation,
        }
    return {"success": True, "validation": image_validation}


def write_status(config: Mapping[str, Any], payload: dict[str, Any], status_file: str = "") -> Path:
    if status_file:
        path = Path(status_file).expanduser()
    else:
        status_dir = vault_path(config, "statusDir")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zotero_id = str(payload.get("zotero_id") or "no-zotero").lower()
        path = status_dir / f"mineru-{zotero_id}-{stamp}.status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def success_message(result: Mapping[str, Any], elapsed: float, status_file: Path) -> str:
    validation = result.get("validation", {})
    if not isinstance(validation, Mapping):
        validation = {}
    return "\n".join(
        [
            "MinerU conversion completed",
            f"Title: {result.get('title') or Path(str(result.get('output_md', ''))).stem}",
            f"Markdown: {result.get('output_md')}",
            f"Images moved: {result.get('images_moved', 0)}; missing links: {validation.get('missing_image_count', result.get('missing_image_count', 0))}",
            f"Elapsed: {human_duration(elapsed)}",
            f"Status: {status_file}",
        ]
    )


def failure_message(pdf_path: str, elapsed: float, status_file: Path, error: str, stdout: str = "", stderr: str = "") -> str:
    lines = [
        "MinerU conversion failed",
        f"PDF: {pdf_path}",
        f"Error: {error}",
        f"Elapsed: {human_duration(elapsed)}",
        f"Status: {status_file}",
    ]
    stderr_tail = tail_text(stderr, 1500)
    stdout_tail = tail_text(stdout, 800)
    if stderr_tail:
        lines.extend(["stderr:", stderr_tail])
    elif stdout_tail:
        lines.extend(["stdout:", stdout_tail])
    return "\n".join(lines)


def run(args: argparse.Namespace) -> tuple[int, str]:
    config = load_config(args.config)
    start = time.time()
    command = [
        args.python or sys.executable,
        str(CONVERT_SCRIPT),
        args.pdf_path,
        "--config",
        args.config,
        "--timeout-sec",
        str(args.timeout_sec),
    ]
    if args.zotero_id:
        command.extend(["--zotero-id", args.zotero_id])
    if args.output_dir:
        command.extend(["--output-dir", args.output_dir])

    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout_sec + 180)
    except subprocess.TimeoutExpired as exc:
        elapsed = time.time() - start
        payload = {
            "success": False,
            "error": f"wrapper timed out after {args.timeout_sec + 180}s",
            "pdf": args.pdf_path,
            "zotero_id": args.zotero_id,
            "elapsed_seconds": elapsed,
            "stdout_tail": tail_text(exc.stdout if isinstance(exc.stdout, str) else "", 2000),
            "stderr_tail": tail_text(exc.stderr if isinstance(exc.stderr, str) else "", 2000),
        }
        status_file = write_status(config, payload, args.status_file)
        return (1 if args.strict_exit else 0), failure_message(
            args.pdf_path,
            elapsed,
            status_file,
            payload["error"],
            payload["stdout_tail"],
            payload["stderr_tail"],
        )

    elapsed = time.time() - start
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    try:
        result = extract_json(stdout)
    except ValueError as error:
        payload = {
            "success": False,
            "error": str(error),
            "pdf": args.pdf_path,
            "zotero_id": args.zotero_id,
            "elapsed_seconds": elapsed,
            "returncode": completed.returncode,
            "stdout_tail": tail_text(stdout, 3000),
            "stderr_tail": tail_text(stderr, 3000),
        }
        status_file = write_status(config, payload, args.status_file)
        return (1 if args.strict_exit else 0), failure_message(args.pdf_path, elapsed, status_file, str(error), stdout, stderr)

    payload = {
        "success": bool(result.get("success")),
        "error": result.get("error"),
        "pdf": args.pdf_path,
        "zotero_id": args.zotero_id,
        "elapsed_seconds": elapsed,
        "returncode": completed.returncode,
        "result": result,
        "stderr_tail": tail_text(stderr, 3000),
    }
    if payload["success"]:
        validation = validate_conversion_result(config, result, args.zotero_id)
        payload["validation"] = validation.get("validation")
        if not validation.get("success"):
            payload["success"] = False
            payload["error"] = validation.get("error")
    status_file = write_status(config, payload, args.status_file)
    if payload["success"]:
        result_with_validation = dict(result)
        result_with_validation["validation"] = payload.get("validation") or {}
        return 0, success_message(result_with_validation, elapsed, status_file)
    return (1 if args.strict_exit else 0), failure_message(
        args.pdf_path,
        elapsed,
        status_file,
        str(result.get("error") or "conversion failed"),
        stdout,
        stderr,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert a PDF and print a delivery-safe status message.")
    parser.add_argument("pdf_path", help="Path to the local PDF")
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--zotero-id", default="", help="Zotero item key")
    parser.add_argument("--output-dir", default="", help="Override output directory")
    parser.add_argument("--timeout-sec", type=int, default=3600, help="Max seconds for MinerU")
    parser.add_argument("--python", default="", help="Python executable used for convert_pdf.py")
    parser.add_argument("--status-file", default="", help="Optional JSON status file path")
    parser.add_argument("--strict-exit", action="store_true", help="Exit non-zero on handled conversion failure")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        code, message = run(parse_args(argv))
    except Exception as error:
        code = 1
        message = f"MinerU notification wrapper failed: {error}"
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
