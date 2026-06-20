#!/usr/bin/env python3
"""Manage academic paper reading lists in an Obsidian vault."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

try:
    from .config import load_config, relative_to_vault, require_vault_root, vault_path
except ImportError:  # pragma: no cover - direct script execution
    from config import load_config, relative_to_vault, require_vault_root, vault_path  # type: ignore


TODO_SECTION = "## To Read"
DONE_SECTION = "## Read"
ARCHIVE_SECTION = "## Archive"


def list_file(config: Mapping[str, Any], status: str) -> Path:
    if status == "todo":
        return vault_path(config, "readingDir") / str(config["paths"]["academicTodoList"])
    if status == "archive":
        return vault_path(config, "readingDir") / str(config["paths"]["academicArchiveList"])
    raise ValueError(f"Unsupported status: {status}")


def ensure_lists(config: Mapping[str, Any]) -> None:
    """Create list files with stable headers if they do not exist."""
    templates = {
        "todo": "# Academic Papers - To Read\n\n## To Read\n\n## Read\n",
        "archive": "# Academic Papers - Archive\n\n## Archive\n",
    }
    for status, template in templates.items():
        path = list_file(config, status)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(template, encoding="utf-8")


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").split("\n")


def write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines), encoding="utf-8")


def find_section_bounds(lines: list[str], marker: str) -> tuple[int | None, int | None]:
    start = None
    for index, line in enumerate(lines):
        if line.strip() == marker:
            start = index + 1
            while start < len(lines) and lines[start].strip() == "":
                start += 1
            break
    if start is None:
        return None, None

    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].strip().startswith("## "):
            end = index
            break
    return start, end


def renumber_section(lines: list[str], marker: str) -> None:
    start, end = find_section_bounds(lines, marker)
    if start is None or end is None:
        return
    sequence = 1
    for index in range(start, end):
        if re.match(r"^\d+\.", lines[index]):
            lines[index] = re.sub(r"^\d+\.", f"{sequence}.", lines[index])
            sequence += 1


def normalize_zotero_id(value: str) -> str:
    match = re.search(r"([A-Z0-9]{8})", value.upper())
    return match.group(1) if match else ""


def resolve_note_path(config: Mapping[str, Any], filename: str) -> Path | None:
    """Resolve a Markdown note path from an absolute, vault-relative, or bare filename."""
    if not filename:
        return None

    vault_root = require_vault_root(config)
    academic_notes_dir = vault_path(config, "academicNotesDir")
    raw = Path(filename).expanduser()
    candidates: list[Path] = []

    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append(vault_root / raw)
        candidates.append(academic_notes_dir / raw)

    expanded: list[Path] = []
    for candidate in candidates:
        expanded.append(candidate)
        if candidate.suffix != ".md":
            expanded.append(candidate.with_suffix(".md"))

    for candidate in expanded:
        if candidate.exists():
            return candidate

    zotero_id = normalize_zotero_id(raw.stem)
    if zotero_id:
        matches = sorted(academic_notes_dir.glob(f"*-{zotero_id}.md"))
        if matches:
            return matches[0]

    return expanded[0] if expanded else None


def to_obsidian_link(config: Mapping[str, Any], filename: str) -> str:
    """Convert a note path to a vault-relative Obsidian wikilink target."""
    raw = Path(filename).expanduser()
    note_path = resolve_note_path(config, filename)
    if note_path is None:
        return raw.with_suffix("").as_posix()

    if not note_path.exists() and raw.parent == Path("."):
        note_path = vault_path(config, "academicNotesDir") / raw

    if note_path.suffix == ".md":
        note_path = note_path.with_suffix("")
    return relative_to_vault(config, note_path).as_posix()


def find_entry_lines(lines: list[str], entry_id: str) -> dict[int, str]:
    found: dict[int, str] = {}
    for index, line in enumerate(lines):
        if entry_id and entry_id in line:
            found[index] = line
    return found


def format_entry(
    sequence: int,
    config: Mapping[str, Any],
    entry_id: str,
    title: str,
    filename: str,
    cn_title: str = "",
    journal: str = "",
    if_value: str = "",
    date: str = "",
    doi: str = "",
    tags: str = "",
    summary: str = "",
) -> str:
    link = to_obsidian_link(config, filename)
    details = [
        f"   - Zotero ID: {entry_id}",
        f"   - Chinese title: {cn_title or 'N/A'}",
        f"   - Venue: {journal or 'N/A'} (IF: {if_value or 'N/A'})",
        f"   - Date: {date or 'N/A'}",
        f"   - DOI: {doi or 'N/A'}",
    ]
    if tags:
        details.append(f"   - Tags: {tags}")
    if summary:
        details.append(f"   - Summary: {summary}")
    return "\n".join([f"{sequence}. [[{link}|{title}]]", *details])


def ensure_section(lines: list[str], marker: str, fallback_header: str) -> list[str]:
    if marker in [line.strip() for line in lines]:
        return lines
    if not lines or not lines[0].startswith("# "):
        return [fallback_header, "", marker, "", *lines]
    return [*lines, "", marker, ""]


def add_entry(
    config: Mapping[str, Any],
    status: str,
    entry_id: str,
    title: str,
    filename: str,
    cn_title: str = "",
    journal: str = "",
    if_value: str = "",
    date: str = "",
    doi: str = "",
    tags: str = "",
    summary: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    ensure_lists(config)
    path = list_file(config, status)
    lines = read_lines(path)
    marker = TODO_SECTION if status == "todo" else ARCHIVE_SECTION
    header = "# Academic Papers - To Read" if status == "todo" else "# Academic Papers - Archive"
    lines = ensure_section(lines, marker, header)

    if find_entry_lines(lines, entry_id):
        return {"success": False, "error": f"Entry with ID '{entry_id}' already exists", "list": str(path)}

    entry_text = format_entry(
        1,
        config,
        entry_id,
        title,
        filename,
        cn_title,
        journal,
        if_value,
        date,
        doi,
        tags if status == "archive" else "",
        summary,
    )
    start, _ = find_section_bounds(lines, marker)
    if start is None:
        lines.extend(["", marker, "", entry_text, ""])
    else:
        entry_lines = entry_text.split("\n")
        for offset, line in enumerate(entry_lines):
            lines.insert(start + offset, line)
        lines.insert(start + len(entry_lines), "")
        renumber_section(lines, marker)

    expected_link = to_obsidian_link(config, filename)
    if dry_run:
        return {
            "success": True,
            "action": "add",
            "dry_run": True,
            "list": str(path),
            "entry_id": entry_id,
            "expected_link": expected_link,
        }

    write_lines(path, lines)
    verify_text = "\n".join(read_lines(path))
    if entry_id not in verify_text:
        return {"success": False, "error": "Verification failed: entry ID not found after write"}
    if expected_link not in verify_text:
        return {"success": False, "error": "Verification failed: linked note not found after write"}

    return {
        "success": True,
        "action": "add",
        "list": str(path),
        "entry_id": entry_id,
        "expected_link": expected_link,
    }


def capture_entry_block(lines: list[str], entry_id: str) -> tuple[int | None, int | None, list[str]]:
    for index, line in enumerate(lines):
        if entry_id in line and re.match(r"^\d+\.", line.strip()):
            block = [line]
            end = index + 1
            for cursor in range(index + 1, len(lines)):
                current = lines[cursor]
                if current.strip() == "":
                    end = cursor
                    break
                if re.match(r"^\d+\.", current.strip()) or current.strip().startswith("## "):
                    end = cursor
                    break
                block.append(current)
                end = cursor + 1
            return index, end, block
    return None, None, []


def move_entry(config: Mapping[str, Any], entry_id: str, dry_run: bool = False) -> dict[str, Any]:
    ensure_lists(config)
    path = list_file(config, "todo")
    lines = read_lines(path)
    start, end, block = capture_entry_block(lines, entry_id)
    if start is None or end is None:
        return {"success": False, "error": f"Entry '{entry_id}' not found", "list": str(path)}

    todo_start, todo_end = find_section_bounds(lines, TODO_SECTION)
    if todo_start is None or todo_end is None or not (todo_start <= start < todo_end):
        return {"success": False, "error": f"Entry '{entry_id}' is not in the To Read section"}

    updated = list(lines)
    remove_end = end
    if remove_end < len(updated) and updated[remove_end].strip() == "":
        remove_end += 1
    del updated[start:remove_end]
    renumber_section(updated, TODO_SECTION)

    updated = ensure_section(updated, DONE_SECTION, "# Academic Papers - To Read")
    done_start, _ = find_section_bounds(updated, DONE_SECTION)
    block[0] = re.sub(r"^\d+\.", "1.", block[0])
    if done_start is None:
        updated.extend(["", DONE_SECTION, "", *block, ""])
    else:
        updated.insert(done_start, "")
        for offset, line in enumerate(block):
            updated.insert(done_start + 1 + offset, line)
    renumber_section(updated, DONE_SECTION)

    if dry_run:
        return {"success": True, "action": "move", "dry_run": True, "entry_id": entry_id, "list": str(path)}

    write_lines(path, updated)
    verify_lines = read_lines(path)
    new_todo_start, new_todo_end = find_section_bounds(verify_lines, TODO_SECTION)
    done_start, done_end = find_section_bounds(verify_lines, DONE_SECTION)
    todo_text = "\n".join(verify_lines[new_todo_start:new_todo_end]) if new_todo_start is not None else ""
    done_text = "\n".join(verify_lines[done_start:done_end]) if done_start is not None else ""
    if entry_id in todo_text:
        return {"success": False, "error": "Verification failed: entry still present in To Read"}
    if entry_id not in done_text:
        return {"success": False, "error": "Verification failed: entry not present in Read"}
    return {"success": True, "action": "move", "entry_id": entry_id, "from": "To Read", "to": "Read"}


def list_entries(config: Mapping[str, Any], status: str) -> dict[str, Any]:
    path = list_file(config, status)
    if not path.exists():
        return {"success": True, "list": str(path), "content": ""}
    return {"success": True, "list": str(path), "content": path.read_text(encoding="utf-8")}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage academic reading lists in Obsidian.")
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--action", choices=["add", "move", "list"], required=True)
    parser.add_argument("--status", choices=["todo", "archive"])
    parser.add_argument("--id", help="Zotero item key or stable paper ID")
    parser.add_argument("--title", help="Paper title")
    parser.add_argument("--file", help="Markdown filename or vault-relative path")
    parser.add_argument("--cn-title", default="", help="Translated title")
    parser.add_argument("--journal", default="", help="Journal or conference")
    parser.add_argument("--if", dest="if_value", default="", help="Impact factor, h-index, or N/A")
    parser.add_argument("--date", default="", help="Publication or conversion date")
    parser.add_argument("--doi", default="", help="DOI")
    parser.add_argument("--tags", default="", help="Tags, comma-separated")
    parser.add_argument("--summary", default="", help="One-sentence summary")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print result without writing")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(args.config)

    if args.action == "add":
        if not args.status:
            raise SystemExit("--status is required for add")
        missing = [name for name in ("id", "title", "file") if not getattr(args, name)]
        if missing:
            raise SystemExit(f"Missing required arguments: {', '.join('--' + item for item in missing)}")
        result = add_entry(
            config,
            args.status,
            args.id,
            args.title,
            args.file,
            args.cn_title,
            args.journal,
            args.if_value,
            args.date,
            args.doi,
            args.tags,
            args.summary,
            args.dry_run,
        )
    elif args.action == "move":
        if not args.id:
            raise SystemExit("--id is required for move")
        result = move_entry(config, args.id, args.dry_run)
    else:
        if not args.status:
            raise SystemExit("--status is required for list")
        result = list_entries(config, args.status)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
