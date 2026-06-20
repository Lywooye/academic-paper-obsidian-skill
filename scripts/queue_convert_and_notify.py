#!/usr/bin/env python3
"""Queue a MinerU PDF conversion as an OpenClaw command job."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

try:
    from .config import load_config
except ImportError:  # pragma: no cover - direct script execution
    from config import load_config  # type: ignore


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CONVERT_AND_NOTIFY = Path(__file__).resolve().parent / "convert_and_notify.py"


def openclaw_config(config: Mapping[str, Any]) -> Mapping[str, Any]:
    value = config.get("openclaw", {})
    return value if isinstance(value, Mapping) else {}


def mineru_python(config: Mapping[str, Any]) -> str:
    mineru = config.get("mineru", {})
    if isinstance(mineru, Mapping):
        configured = str(mineru.get("python") or "").strip()
        if configured:
            return configured
    return sys.executable


def resolve_openclaw_cli(config: Mapping[str, Any], explicit_cli: str = "") -> str:
    if explicit_cli:
        return explicit_cli
    configured = str(openclaw_config(config).get("cli") or "").strip()
    if configured and configured != "openclaw":
        return configured
    found = shutil.which(configured or "openclaw")
    return found or configured or "openclaw"


def command_cwd(config: Mapping[str, Any], explicit_cwd: str = "") -> Path:
    if explicit_cwd:
        return Path(explicit_cwd).expanduser()
    configured = str(openclaw_config(config).get("commandCwd") or "").strip()
    return Path(configured).expanduser() if configured else PACKAGE_ROOT


def optional_delivery_target(config: Mapping[str, Any], explicit_to: str = "") -> str:
    if explicit_to:
        return explicit_to
    env_name = str(openclaw_config(config).get("notifyToEnv") or "OPENCLAW_MINERU_NOTIFY_TO")
    return os.environ.get(env_name, "")


def build_convert_argv(args: argparse.Namespace, config: Mapping[str, Any]) -> list[str]:
    argv = [
        args.python or mineru_python(config),
        str(CONVERT_AND_NOTIFY),
        args.pdf_path,
        "--config",
        args.config,
        "--timeout-sec",
        str(args.timeout_sec),
    ]
    if args.zotero_id:
        argv.extend(["--zotero-id", args.zotero_id])
    if args.output_dir:
        argv.extend(["--output-dir", args.output_dir])
    return argv


def build_cron_command(args: argparse.Namespace, config: Mapping[str, Any]) -> list[str]:
    openclaw = openclaw_config(config)
    label = args.zotero_id or Path(args.pdf_path).stem[:24]
    job_name = args.name or f"MinerU {label} conversion"
    timeout_grace = args.timeout_grace_sec
    if timeout_grace is None:
        timeout_grace = int(openclaw.get("timeoutGraceSec", 300))
    timeout_seconds = args.timeout_sec + int(timeout_grace)
    channel = args.channel if args.channel is not None else str(openclaw.get("channel") or "")
    account = args.account if args.account is not None else str(openclaw.get("account") or "")
    notify_to = optional_delivery_target(config, args.to or "")
    output_max_bytes = args.output_max_bytes
    if output_max_bytes is None:
        output_max_bytes = int(openclaw.get("outputMaxBytes", 12000))

    command = [
        resolve_openclaw_cli(config, args.openclaw_cli or ""),
        "cron",
        "add",
        "--json",
        "--name",
        job_name,
        "--at",
        args.at,
        "--delete-after-run",
        "--announce",
        "--command-argv",
        json.dumps(build_convert_argv(args, config), ensure_ascii=False),
        "--command-cwd",
        str(command_cwd(config, args.command_cwd or "")),
        "--timeout-seconds",
        str(timeout_seconds),
        "--output-max-bytes",
        str(output_max_bytes),
    ]
    if channel:
        command.extend(["--channel", channel])
    if notify_to:
        command.extend(["--to", notify_to])
    if account:
        command.extend(["--account", account])
    return command


def parse_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Queue MinerU PDF conversion as an OpenClaw command job."
    )
    parser.add_argument("pdf_path", help="Path to the local PDF")
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--zotero-id", default="", help="Zotero item key")
    parser.add_argument("--output-dir", default="", help="Override output Markdown directory")
    parser.add_argument("--timeout-sec", type=int, default=3600, help="Max seconds for MinerU")
    parser.add_argument("--timeout-grace-sec", type=int, default=None, help="Extra command-job timeout after MinerU timeout")
    parser.add_argument("--python", default="", help="Python executable used for convert_and_notify.py")
    parser.add_argument("--at", default="+1s", help="When OpenClaw should run the command job")
    parser.add_argument("--name", default="", help="OpenClaw cron job name")
    parser.add_argument("--channel", default=None, help="Optional OpenClaw delivery channel")
    parser.add_argument("--to", default="", help="Optional OpenClaw delivery target")
    parser.add_argument("--account", default=None, help="Optional OpenClaw delivery account")
    parser.add_argument("--command-cwd", default="", help="Command working directory for the queued job")
    parser.add_argument("--openclaw-cli", default="", help="Path to the OpenClaw CLI")
    parser.add_argument("--output-max-bytes", type=int, default=None, help="Max captured command output bytes")
    parser.add_argument("--dry-run", action="store_true", help="Print the OpenClaw command without creating a job")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(args.config)
    pdf = Path(args.pdf_path).expanduser()
    if not pdf.exists():
        print(json.dumps({"success": False, "error": f"PDF not found: {pdf}"}, ensure_ascii=False, indent=2))
        return 2
    if not CONVERT_AND_NOTIFY.exists():
        print(json.dumps({"success": False, "error": f"notify wrapper not found: {CONVERT_AND_NOTIFY}"}, ensure_ascii=False, indent=2))
        return 2

    command = build_cron_command(args, config)
    if args.dry_run:
        print(json.dumps({"success": True, "dry_run": True, "command": command}, ensure_ascii=False, indent=2))
        return 0

    completed = subprocess.run(command, capture_output=True, text=True, cwd=str(command_cwd(config, args.command_cwd or "")))
    if completed.returncode != 0:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": "failed to queue OpenClaw command job",
                    "returncode": completed.returncode,
                    "stdout": completed.stdout.strip(),
                    "stderr": completed.stderr.strip(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return completed.returncode

    job = parse_json_object(completed.stdout) or {}
    print(
        json.dumps(
            {
                "success": True,
                "action": "queue-conversion",
                "job_id": job.get("id") or job.get("jobId") or "unknown",
                "zotero_id": args.zotero_id,
                "pdf_path": str(pdf),
                "message": "Queued MinerU conversion. The command job should deliver the final conversion result.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

