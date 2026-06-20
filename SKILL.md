---
name: academic-paper-zotero-obsidian
description: >
  Process academic papers into Zotero-backed Obsidian reading lists. Use when a user provides a DOI, Zotero item key, or local PDF and wants the paper saved, summarized, queued for close reading, archived, or optionally converted to Markdown with MinerU.
metadata:
  requires:
    env:
      - ZOTERO_API_KEY
      - ZOTERO_USER_ID
---

# Academic Paper Zotero Obsidian

This skill is OpenClaw-first, not OpenClaw-only. It is written as an OpenClaw-style `SKILL.md`, but the underlying scripts are plain command-line tools and can be called by other agent systems or manually.

This skill turns academic-paper intake into deterministic script steps:

1. Ask a reference agent to resolve paper metadata through Zotero or another trusted scholarly source.
2. Attach a local PDF to the correct Zotero item by explicit DOI or item key.
3. Ask a summary agent to produce the paper summary body.
4. Let a coordinator agent write the summary note and reading-list state through scripts.
5. Optionally convert the PDF to Markdown with MinerU and validate local images.

## Runtime Notes

Codex can use this skill as a local CLI toolkit. Prefer direct deterministic script calls such as `scripts/attach_pdf_by_doi.py`, `scripts/write_summary_note.py`, `scripts/reading_list.py`, `scripts/convert_pdf.py`, and `scripts/convert_and_notify.py`, then inspect the resulting files/status JSON before reporting completion.

Do not assume OpenClaw queue behavior exists in Codex. `scripts/queue_convert_and_notify.py` is for OpenClaw command jobs with `--announce`; Codex should use it only when an OpenClaw CLI/runtime is actually available and configured. Otherwise, run the direct wrapper and report the verified result in the current session.

## Setup

Copy `config.example.json` to `config.json` and set:

- `vaultRoot`
- `paths.academicNotesDir`
- `paths.academicTodoList`
- `paths.academicArchiveList`
- `paths.summaryNotesDir`
- `agents.referenceAgentName`
- `agents.summaryAgentName`
- `agents.coordinatorAgentName`
- `zotero.apiKeyEnv`
- `zotero.userIdEnv` or `zotero.groupIdEnv`
- optional MinerU fields under `mineru`
- optional OpenClaw queue fields under `openclaw`

Set credentials in the environment. Never put secrets in `config.json`:

```bash
export ZOTERO_API_KEY="..."
export ZOTERO_USER_ID="..."
```

## Rules

- Do not write Obsidian reading-list entries by prompt text alone. Use `scripts/reading_list.py`.
- Do not write summary notes by prompt text alone. Use `scripts/write_summary_note.py`.
- Prefer explicit DOI or Zotero item key. Do not attach a PDF based only on the first DOI found in full PDF text unless no trusted metadata is available.
- Impact factor is not provided by Zotero or CrossRef. Use a local curated table or write `N/A`.
- Do not run long MinerU conversions inside a conversational child agent. In OpenClaw, use `scripts/queue_convert_and_notify.py` so a command job runs `scripts/convert_and_notify.py` with `--announce` and delivers the final output.
- Treat the immediate queue response as scheduling confirmation only. The final conversion deliverable is the later announced output from `scripts/convert_and_notify.py`.
- Do not use `nohup`, background shell jobs, process polling, or PID-check cron jobs as the user-facing conversion flow. Process existence is not proof of a usable Markdown artifact.
- Do not hard-code private delivery targets. Store platform user/channel IDs in the environment variable named by `openclaw.notifyToEnv`, or pass `--to` locally.
- Treat conversion success as final artifact validation: Markdown exists, the expected Zotero ID is present when provided, image links resolve, and the status JSON was written.
- Do not commit `config.json`, `.env`, Zotero keys, vault paths, session logs, or user identifiers.

## Standard Workflow Rules

Use these rules when translating local agent behavior into a portable workflow:

- Keep role boundaries strict. The reference agent returns structured metadata and attachment status; the summary agent returns summary text; the coordinator agent calls scripts and verifies outputs.
- Prefer isolated child runs for reference and summary work in OpenClaw-style systems. Do not route a new one-shot task through an old main session unless the user explicitly asks for an ongoing conversation with that agent.
- Track current-task identity across every handoff: DOI, Zotero item key, PDF path, planned Markdown filename, and summary note path. Ignore stale agent messages or status-only replies that do not match the current identity.
- Do not treat process notes such as "done", "sent", "queued", or "I will forward it" as deliverables. A deliverable must contain the expected structured fields, summary body, file path, or validation result.
- Send the summary to the user before writing reading-list state. Add to the close-reading or archive list only after the user chooses a status such as `todo` or `archive`.
- Trigger PDF-to-Markdown only when the user chooses close reading or explicitly asks for conversion. Archival entries do not need conversion by default.
- In OpenClaw, the coordinator agent should stop after `queue_convert_and_notify.py` reports that the command job was queued, then wait for the announced final result instead of creating a follow-up PID check.
- All durable state changes go through scripts: Zotero attachment, summary-note write, reading-list add/move, and PDF conversion. Agents should not hand-edit Obsidian list files.
- After every script step, verify the concrete output before reporting completion: item key, list entry, summary note, Markdown file, image links, and status JSON as applicable.

## Agent Roles

The public workflow uses generic names instead of private agent identities:

- **reference agent**: resolves DOI, Zotero item keys, PDF attachments, OA status, venue/date metadata, and provenance fields.
- **summary agent**: reads trusted metadata, abstract, PDF text, or converted Markdown and writes the research-facing summary body.
- **coordinator agent**: calls deterministic scripts, saves notes, updates reading lists, runs conversion jobs, and reports success only after verification.

Users can rename all roles in `config.json`:

```json
{
  "agents": {
    "referenceAgentName": "reference agent",
    "summaryAgentName": "summary agent",
    "coordinatorAgentName": "coordinator agent"
  }
}
```

The names are provenance labels in saved notes. The scripts do not require a specific agent runtime.

## Attach Local PDF To Zotero

When DOI is known:

```bash
python3 scripts/attach_pdf_by_doi.py "/path/to/paper.pdf" --doi "10.xxxx/example" --config config.json
```

When Zotero item key is known:

```bash
python3 scripts/attach_pdf_by_doi.py "/path/to/paper.pdf" --item-key "ABCDEFGH" --config config.json
```

When both are known, pass both so the script checks that they match:

```bash
python3 scripts/attach_pdf_by_doi.py "/path/to/paper.pdf" --item-key "ABCDEFGH" --doi "10.xxxx/example" --config config.json
```

## Add Paper To Reading List

Queue for close reading:

```bash
python3 scripts/reading_list.py \
  --config config.json \
  --action add \
  --status todo \
  --id "ABCDEFGH" \
  --title "Paper Title" \
  --file "Paper Title-2026-06-20-ABCDEFGH.md" \
  --cn-title "中文标题" \
  --journal "Medical Image Analysis" \
  --if "N/A" \
  --date "2026-06-20" \
  --doi "10.xxxx/example" \
  --summary "Why this paper matters in one sentence."
```

Archive without close reading:

```bash
python3 scripts/reading_list.py \
  --config config.json \
  --action add \
  --status archive \
  --id "ABCDEFGH" \
  --title "Paper Title" \
  --file "Paper Title-2026-06-20-ABCDEFGH.md" \
  --tags "diffusion,medical-ai" \
  --summary "Archived because it is relevant but not urgent."
```

Move from To Read to Read:

```bash
python3 scripts/reading_list.py --config config.json --action move --id "ABCDEFGH"
```

## Save Summary Agent Note

The summary agent should return only the summary body. Use `templates/paper_summary_prompt.md` as a starter prompt.

The coordinator agent then writes the note:

```bash
python3 scripts/write_summary_note.py \
  --config config.json \
  --id "ABCDEFGH" \
  --title "Paper Title" \
  --cn-title "中文标题" \
  --journal "Medical Image Analysis" \
  --if "N/A" \
  --date "2026-06-20" \
  --doi "10.xxxx/example" \
  --reference-agent "reference agent" \
  --summary-file "summary.md"
```

The script writes a Markdown file under `paths.summaryNotesDir`, records the reference/summary/coordinator agent names, and verifies that the note contains the paper ID, title, and summary body.

## Optional PDF To Markdown

Enable MinerU in `config.json`, then run:

```bash
python3 scripts/convert_and_notify.py \
  "/path/to/paper.pdf" \
  --config config.json \
  --zotero-id "ABCDEFGH" \
  --timeout-sec 3600
```

The wrapper calls `scripts/convert_pdf.py`, writes Markdown under `paths.academicNotesDir`, moves images under `paths.attachmentsDir`, converts image refs to Obsidian embeds, and writes a status JSON under `paths.statusDir`. Use this direct wrapper for manual runs or external job runners.

In OpenClaw, use the queue entrypoint for user-facing long conversions:

```bash
python3 scripts/queue_convert_and_notify.py \
  "/path/to/paper.pdf" \
  --config config.json \
  --zotero-id "ABCDEFGH"
```

The queue script is the recommended user-facing OpenClaw entrypoint. It creates an OpenClaw command job with `--announce`, the command job runs `convert_and_notify.py`, and `convert_and_notify.py` only reports success after the final Markdown and image links validate. If OpenClaw needs an explicit delivery target, configure `openclaw.notifyToEnv` and set that environment variable locally instead of hard-coding private IDs.

## Agent Handoff Contract

The reference agent should return structured fields, not direct writes:

```json
{
  "status": "ok",
  "zotero_id": "ABCDEFGH",
  "title": "Paper Title",
  "cn_title": "中文标题",
  "journal": "Medical Image Analysis",
  "date": "2026-06-20",
  "doi": "10.xxxx/example",
  "if": "N/A",
  "pdf_path": "/path/to/paper.pdf",
  "pdf_attached": true,
  "oa_status": "oa|non_oa|unknown",
  "summary_basis": "metadata_only|pdf_text"
}
```

The coordinator agent then calls the scripts above and only reports success after the concrete file/list/status check passes.
