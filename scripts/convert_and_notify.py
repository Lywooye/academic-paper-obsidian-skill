#!/usr/bin/env python3
"""Run PDF conversion and print a compact status message for agent delivery."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

try:
    from .config import load_config, vault_path
except ImportError:  # pragma: no cover - direct script execution
    from config import load_config, vault_path  # type: ignore


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
    return "\n".join(
        [
            "MinerU conversion completed",
            f"Title: {result.get('title') or Path(str(result.get('output_md', ''))).stem}",
            f"Markdown: {result.get('output_md')}",
            f"Images moved: {result.get('images_moved', 0)}; missing links: {result.get('missing_image_count', 0)}",
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
    status_file = write_status(config, payload, args.status_file)
    if payload["success"]:
        return 0, success_message(result, elapsed, status_file)
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

