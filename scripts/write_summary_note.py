#!/usr/bin/env python3
"""Write a summary-agent paper note into an Obsidian vault."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

try:
    from .config import load_config, relative_to_vault, require_vault_root, vault_path
except ImportError:  # pragma: no cover - direct script execution
    from config import load_config, relative_to_vault, require_vault_root, vault_path  # type: ignore


def sanitize_filename(name: str) -> str:
    if not name:
        return "untitled"
    sanitized = re.sub(r'[\/:*?"<>|]', "_", name)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized[:120].strip() or "untitled"


def yaml_string(value: str) -> str:
    return json.dumps(value or "", ensure_ascii=False)


def configured_agent_name(config: Mapping[str, Any], key: str, fallback: str) -> str:
    agents = config.get("agents", {})
    if isinstance(agents, Mapping):
        value = str(agents.get(key) or "").strip()
        if value:
            return value
    return fallback


def read_summary_text(summary: str, summary_file: str) -> str:
    if summary_file:
        return Path(summary_file).expanduser().read_text(encoding="utf-8")
    if summary:
        return summary
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def resolve_output_path(config: Mapping[str, Any], output_file: str, title: str, date: str, entry_id: str) -> Path:
    summary_dir = vault_path(config, "summaryNotesDir")
    if output_file:
        raw = Path(output_file).expanduser()
        if raw.is_absolute():
            return raw
        if raw.parent != Path("."):
            return require_vault_root(config) / raw
        return summary_dir / raw

    stem_parts = [sanitize_filename(title)]
    if date:
        stem_parts.append(sanitize_filename(date))
    if entry_id:
        stem_parts.append(sanitize_filename(entry_id))
    return summary_dir / ("-".join(stem_parts) + ".md")


def build_note(
    *,
    entry_id: str,
    title: str,
    cn_title: str,
    journal: str,
    if_value: str,
    date: str,
    doi: str,
    tags: str,
    reference_agent: str,
    summary_agent: str,
    coordinator_agent: str,
    summary_text: str,
) -> str:
    created_at = datetime.now().strftime("%Y-%m-%d")
    tag_line = tags or ""
    frontmatter = [
        "---",
        f'zotero_id: {yaml_string(entry_id)}',
        f'title: {yaml_string(title)}',
        f'cn_title: {yaml_string(cn_title)}',
        f'venue: {yaml_string(journal)}',
        f'impact_factor: {yaml_string(if_value)}',
        f'date: {yaml_string(date)}',
        f'doi: {yaml_string(doi)}',
        f'tags: {yaml_string(tag_line)}',
        f'reference_agent: {yaml_string(reference_agent)}',
        f'summary_agent: {yaml_string(summary_agent)}',
        f'coordinator_agent: {yaml_string(coordinator_agent)}',
        f'created: {yaml_string(created_at)}',
        "---",
        "",
    ]
    metadata = [
        f"# {title}",
        "",
        f"- Zotero ID: {entry_id or 'N/A'}",
        f"- Chinese title: {cn_title or 'N/A'}",
        f"- Venue: {journal or 'N/A'}",
        f"- IF: {if_value or 'N/A'}",
        f"- Date: {date or 'N/A'}",
        f"- DOI: {doi or 'N/A'}",
        f"- Reference agent: {reference_agent}",
        f"- Summary agent: {summary_agent}",
        f"- Coordinator agent: {coordinator_agent}",
    ]
    if tags:
        metadata.append(f"- Tags: {tags}")
    return "\n".join([*frontmatter, *metadata, "", "## Summary", "", summary_text.strip(), ""])


def write_summary_note(
    config: Mapping[str, Any],
    *,
    entry_id: str,
    title: str,
    cn_title: str = "",
    journal: str = "",
    if_value: str = "",
    date: str = "",
    doi: str = "",
    tags: str = "",
    summary_text: str = "",
    reference_agent: str = "",
    summary_agent: str = "",
    coordinator_agent: str = "",
    output_file: str = "",
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not summary_text.strip():
        return {"success": False, "error": "summary text is required"}

    reference_agent = reference_agent or configured_agent_name(config, "referenceAgentName", "reference agent")
    summary_agent = summary_agent or configured_agent_name(config, "summaryAgentName", "summary agent")
    coordinator_agent = coordinator_agent or configured_agent_name(config, "coordinatorAgentName", "coordinator agent")
    target = resolve_output_path(config, output_file, title, date, entry_id)
    note_text = build_note(
        entry_id=entry_id,
        title=title,
        cn_title=cn_title,
        journal=journal,
        if_value=if_value,
        date=date,
        doi=doi,
        tags=tags,
        reference_agent=reference_agent,
        summary_agent=summary_agent,
        coordinator_agent=coordinator_agent,
        summary_text=summary_text,
    )
    vault_link = relative_to_vault(config, target.with_suffix("")).as_posix()

    if dry_run:
        return {
            "success": True,
            "action": "write-summary",
            "dry_run": True,
            "output_md": str(target),
            "vault_link": vault_link,
            "reference_agent": reference_agent,
            "summary_agent": summary_agent,
            "coordinator_agent": coordinator_agent,
        }

    if target.exists() and not overwrite:
        return {"success": False, "error": f"Summary note already exists: {target}", "output_md": str(target)}

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(note_text, encoding="utf-8")
    written = target.read_text(encoding="utf-8")
    if entry_id and entry_id not in written:
        return {"success": False, "error": "Verification failed: entry ID missing after write", "output_md": str(target)}
    if title not in written:
        return {"success": False, "error": "Verification failed: title missing after write", "output_md": str(target)}
    if summary_text.strip()[:40] not in written:
        return {"success": False, "error": "Verification failed: summary body missing after write", "output_md": str(target)}

    return {
        "success": True,
        "action": "write-summary",
        "output_md": str(target),
        "vault_link": vault_link,
        "reference_agent": reference_agent,
        "summary_agent": summary_agent,
        "coordinator_agent": coordinator_agent,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a summary-agent paper note into Obsidian.")
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--id", required=True, help="Zotero item key or stable paper ID")
    parser.add_argument("--title", required=True, help="Paper title")
    parser.add_argument("--cn-title", default="", help="Translated title")
    parser.add_argument("--journal", default="", help="Journal or conference")
    parser.add_argument("--if", dest="if_value", default="", help="Impact factor, h-index, or N/A")
    parser.add_argument("--date", default="", help="Publication or conversion date")
    parser.add_argument("--doi", default="", help="DOI")
    parser.add_argument("--tags", default="", help="Tags, comma-separated")
    parser.add_argument("--summary", default="", help="Summary Markdown text")
    parser.add_argument("--summary-file", default="", help="Path to a Markdown file containing the summary body")
    parser.add_argument("--reference-agent", default="", help="Display name for the reference agent")
    parser.add_argument("--summary-agent", default="", help="Display name for the summary agent")
    parser.add_argument("--coordinator-agent", default="", help="Display name for the coordinator agent")
    parser.add_argument("--file", default="", help="Optional output filename or vault-relative path")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite an existing summary note")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print result without writing")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(args.config)
    result = write_summary_note(
        config,
        entry_id=args.id,
        title=args.title,
        cn_title=args.cn_title,
        journal=args.journal,
        if_value=args.if_value,
        date=args.date,
        doi=args.doi,
        tags=args.tags,
        summary_text=read_summary_text(args.summary, args.summary_file),
        reference_agent=args.reference_agent,
        summary_agent=args.summary_agent,
        coordinator_agent=args.coordinator_agent,
        output_file=args.file,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
