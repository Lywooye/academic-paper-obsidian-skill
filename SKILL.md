---
name: academic-paper-obsidian
description: >
  Process academic papers into Zotero-backed Obsidian reading lists. Use when a user provides a DOI, Zotero item key, or local PDF and wants the paper saved, summarized, queued for close reading, archived, or optionally converted to Markdown with MinerU.
metadata:
  requires:
    env:
      - ZOTERO_API_KEY
      - ZOTERO_USER_ID
---

# Academic Paper to Obsidian

This skill turns academic-paper intake into deterministic script steps:

1. Resolve paper metadata through Zotero or another trusted scholarly source.
2. Attach a local PDF to the correct Zotero item by explicit DOI or item key.
3. Write or move the paper in an Obsidian reading list.
4. Optionally convert the PDF to Markdown with MinerU and validate local images.

## Setup

Copy `config.example.json` to `config.json` and set:

- `vaultRoot`
- `paths.academicNotesDir`
- `paths.academicTodoList`
- `paths.academicArchiveList`
- `zotero.apiKeyEnv`
- `zotero.userIdEnv` or `zotero.groupIdEnv`
- optional MinerU fields under `mineru`

Set credentials in the environment. Never put secrets in `config.json`:

```bash
export ZOTERO_API_KEY="..."
export ZOTERO_USER_ID="..."
```

## Rules

- Do not write Obsidian reading-list entries by prompt text alone. Use `scripts/reading_list.py`.
- Prefer explicit DOI or Zotero item key. Do not attach a PDF based only on the first DOI found in full PDF text unless no trusted metadata is available.
- Impact factor is not provided by Zotero or CrossRef. Use a local curated table or write `N/A`.
- Do not run long MinerU conversions inside a conversational child agent. Schedule or run `scripts/convert_and_notify.py` as a command job and deliver its output.
- Treat conversion success as final artifact validation: Markdown exists, image links resolve, and the status JSON was written.
- Do not commit `config.json`, `.env`, Zotero keys, vault paths, session logs, or user identifiers.

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

## Optional PDF To Markdown

Enable MinerU in `config.json`, then run:

```bash
python3 scripts/convert_and_notify.py \
  "/path/to/paper.pdf" \
  --config config.json \
  --zotero-id "ABCDEFGH" \
  --timeout-sec 3600
```

The wrapper calls `scripts/convert_pdf.py`, writes Markdown under `paths.academicNotesDir`, moves images under `paths.attachmentsDir`, converts image refs to Obsidian embeds, and writes a status JSON under `paths.statusDir`.

## Agent Handoff Contract

The literature-search agent should return structured fields, not direct writes:

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

