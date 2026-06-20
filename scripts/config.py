#!/usr/bin/env python3
"""Configuration helpers for the academic paper Obsidian workflow."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATHS = (
    Path(os.environ["ACADEMIC_PIPELINE_CONFIG"]).expanduser()
    if os.environ.get("ACADEMIC_PIPELINE_CONFIG")
    else None,
    Path.cwd() / "config.json",
    PACKAGE_ROOT / "config.json",
)

DEFAULT_CONFIG: dict[str, Any] = {
    "vaultRoot": "",
    "paths": {
        "readingDir": "01_Maps/03_Reading",
        "academicTodoList": "Academic Papers - To Read.md",
        "academicArchiveList": "Academic Papers - Archive.md",
        "academicNotesDir": "00_Inbox/PDFs",
        "summaryNotesDir": "11_Academic/Summaries",
        "attachmentsDir": "99_Resources/Attachments",
        "mineruWorkDir": "99_Resources/mineru",
        "statusDir": ".academic-paper-obsidian/tmp",
    },
    "agents": {
        "referenceAgentName": "reference agent",
        "summaryAgentName": "summary agent",
        "coordinatorAgentName": "coordinator agent",
    },
    "zotero": {
        "apiBase": "https://api.zotero.org",
        "apiKeyEnv": "ZOTERO_API_KEY",
        "userIdEnv": "ZOTERO_USER_ID",
        "groupIdEnv": "ZOTERO_GROUP_ID",
    },
    "mineru": {
        "enabled": False,
        "bin": "mineru",
        "python": "",
        "deviceMode": "mps",
        "backend": "vlm-engine",
        "effort": "high",
        "timeoutSec": 3600,
        "taskResultTimeoutSec": 3600,
        "taskResultDownloadTimeoutSec": 600,
        "pdfRenderTimeoutSec": 600,
    },
    "openclaw": {
        "cli": "openclaw",
        "commandCwd": "",
        "channel": "",
        "notifyToEnv": "OPENCLAW_MINERU_NOTIFY_TO",
        "account": "",
        "outputMaxBytes": 12000,
        "timeoutGraceSec": 300,
    },
}


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Return a recursive merge without mutating either input."""
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = deep_merge(merged[key], value)  # type: ignore[arg-type]
        else:
            merged[key] = value
    return merged


def find_config_path(explicit_path: str | None = None) -> Path | None:
    """Find the first existing config path."""
    if explicit_path:
        path = Path(explicit_path).expanduser()
        return path if path.exists() else None
    for candidate in DEFAULT_CONFIG_PATHS:
        if candidate and candidate.exists():
            return candidate
    return None


def load_config(explicit_path: str | None = None) -> dict[str, Any]:
    """Load config.json and merge it with defaults."""
    config = dict(DEFAULT_CONFIG)
    path = find_config_path(explicit_path)
    if path:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        config = deep_merge(DEFAULT_CONFIG, loaded)
        config["_configPath"] = str(path)
    return config


def require_vault_root(config: Mapping[str, Any]) -> Path:
    """Return the configured vault root or raise a user-facing error."""
    raw = str(config.get("vaultRoot") or "").strip()
    if not raw:
        raise SystemExit(
            "vaultRoot is not configured. Copy config.example.json to config.json "
            "or set ACADEMIC_PIPELINE_CONFIG."
        )
    path = Path(raw).expanduser()
    return path


def vault_path(config: Mapping[str, Any], path_key: str) -> Path:
    """Resolve a path under the Obsidian vault from config.paths."""
    root = require_vault_root(config)
    paths = config.get("paths", {})
    if not isinstance(paths, Mapping) or path_key not in paths:
        raise KeyError(f"Missing paths.{path_key} in config")
    raw = Path(str(paths[path_key])).expanduser()
    return raw if raw.is_absolute() else root / raw


def relative_to_vault(config: Mapping[str, Any], path: Path) -> Path:
    """Best-effort path relative to vault root."""
    root = require_vault_root(config)
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError:
        return path
