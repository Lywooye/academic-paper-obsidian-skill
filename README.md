# Academic Paper to Obsidian Skill

A lightweight OpenClaw-first skill for turning DOI/PDF handoffs into a Zotero-backed Obsidian reading workflow. It gives your agents a clear way to verify paper metadata, create Zotero items, save summaries, maintain reading/archive/read lists, and optionally convert PDFs into Obsidian-linked Markdown notes.

Core capabilities:

- verify paper metadata and create Zotero items from DOI/PDF handoffs
- attach local PDFs to the matching Zotero items
- generate and save summary Markdown notes by the summary agent
- maintain Obsidian close-reading, archive, and read lists
- optionally convert PDFs to Markdown with MinerU, which makes it easier to read the original paper and take notes inside Obsidian
- link close-reading list entries directly to generated Markdown files
- validate reading-list entries and converted Markdown image links

This repository intentionally keeps personal paths, API keys, Feishu IDs, agent names, and private logs out of the package. Configure everything through `config.json` and environment variables.

## OpenClaw First, Not OpenClaw Only

This project is designed for OpenClaw-style agent workflows: it includes a `SKILL.md`, three generic agent roles, and handoff rules for reference, summary, and coordinator agents.

The Python scripts are plain command-line tools. Other agent systems can use the same workflow if they can call shell commands with the documented arguments, and the scripts can also be run manually.

## Workflow

1. Send a DOI or PDF to your coordinator agent.
2. The reference agent verifies the Zotero information and adds the Zotero item.
3. The summary agent writes the paper summary, and the coordinator agent sends it to you.
4. Reply with a decision such as `close-reading` or `archive`.
5. The coordinator agent writes the paper to the matching Obsidian close-reading or archive list and verifies that the entry exists.
6. If you chose `close-reading`, the coordinator agent can optionally convert the PDF to Markdown with MinerU. The generated Markdown is saved under your configured Obsidian directory, and the paper title in the close-reading list links directly to that Markdown note. Tables and images are converted alongside the text. This makes it easier to read the original paper and take notes inside Obsidian.
7. After reading, tell the coordinator agent that this paper is `read`; the coordinator agent automatically moves the paper information to the Obsidian read list and verifies the move.

## Who It Is For

This is useful if you use:

- Zotero as the source of truth for paper metadata
- Obsidian as the durable reading list and note vault
- an agent system such as OpenClaw to coordinate literature search, summarization, and file operations
- optionally MinerU for PDF-to-Markdown conversion

It is probably too specialized for general readers, but it should be useful to researchers who already combine Zotero and Obsidian and want fewer broken PDF/list handoffs.

## Quick Start

```bash
git clone https://github.com/Lywooye/academic-paper-obsidian-skill.git
cd academic-paper-obsidian-skill
cp config.example.json config.json
cp .env.example .env
```

Edit `config.json`:

```json
{
  "vaultRoot": "/absolute/path/to/your/obsidian-vault"
}
```

Export Zotero credentials:

```bash
export ZOTERO_API_KEY="..."
export ZOTERO_USER_ID="..."
```

Run the tests:

```bash
python3 -m unittest discover -s tests
```

## Commands

Add a paper to the close-reading list:

```bash
python3 scripts/reading_list.py \
  --config config.json \
  --action add \
  --status todo \
  --id "ABCDEFGH" \
  --title "Paper Title" \
  --file "Paper Title-2026-06-20-ABCDEFGH.md" \
  --journal "Medical Image Analysis" \
  --if "N/A" \
  --date "2026-06-20" \
  --doi "10.xxxx/example" \
  --summary "A concise reason to read this paper."
```

Attach a local PDF to an existing Zotero item:

```bash
python3 scripts/attach_pdf_by_doi.py "/path/to/paper.pdf" --doi "10.xxxx/example" --config config.json
```

Save a summary-agent note:

```bash
python3 scripts/write_summary_note.py \
  --config config.json \
  --id "ABCDEFGH" \
  --title "Paper Title" \
  --cn-title "论文中文标题" \
  --journal "Medical Image Analysis" \
  --date "2026-06-20" \
  --doi "10.xxxx/example" \
  --summary-file examples/sample_summary.md
```

Convert a PDF to Markdown with MinerU manually or from a durable job runner:

```bash
python3 scripts/convert_and_notify.py "/path/to/paper.pdf" --config config.json --zotero-id "ABCDEFGH"
```

Queue a user-facing MinerU conversion in OpenClaw:

```bash
python3 scripts/queue_convert_and_notify.py \
  "/path/to/paper.pdf" \
  --config config.json \
  --zotero-id "ABCDEFGH"
```

For OpenClaw, this is the recommended user-facing path. The queue script creates an `openclaw cron add --command-argv ... --announce` command job, and that job delivers the final success/failure message after `convert_and_notify.py` validates the Markdown file and image links. Treat the immediate queue response as scheduling confirmation only; do not create a separate PID polling cron job.

MinerU is optional. Leave `mineru.enabled=false` until you have a working local MinerU install.

## Configuration

### Prerequisites

You need:

- Python 3.10+
- an Obsidian vault
- a Zotero API key
- optionally MinerU, only if you want PDF-to-Markdown conversion

### Configure Obsidian

Copy the example config:

```bash
cp config.example.json config.json
```

Set `vaultRoot` to your Obsidian vault:

```json
{
  "vaultRoot": "/absolute/path/to/your/obsidian-vault"
}
```

Then adjust the vault-relative paths if your vault uses different folders:

```json
{
  "paths": {
    "readingDir": "01_Maps/03_Reading",
    "academicTodoList": "Academic Papers - To Read.md",
    "academicArchiveList": "Academic Papers - Archive.md",
    "academicNotesDir": "00_Inbox/PDFs",
    "summaryNotesDir": "11_Academic/Summaries",
    "attachmentsDir": "99_Resources/Attachments"
  }
}
```

The list filenames can be localized. For example:

```json
{
  "academicTodoList": "Papers - Close Reading.md",
  "academicArchiveList": "Papers - Archive.md"
}
```

### Configure Zotero

Create a Zotero API key at Zotero's settings page and export it as an environment variable:

```bash
export ZOTERO_API_KEY="your-zotero-api-key"
export ZOTERO_USER_ID="your-zotero-user-id"
```

For a Zotero group library, export `ZOTERO_GROUP_ID` instead of `ZOTERO_USER_ID`:

```bash
export ZOTERO_GROUP_ID="your-zotero-group-id"
```

You can also copy `.env.example` to `.env` for local reference, but the scripts read credentials from environment variables.

### Configure Agent Names

The public workflow uses three generic role names:

- `reference agent`: resolves DOI/Zotero metadata, PDF attachment, and source provenance
- `summary agent`: produces the paper summary body from trusted metadata and available text
- `coordinator agent`: calls scripts, writes files, and verifies outputs

You can keep these defaults or personalize them in `config.json`:

```json
{
  "agents": {
    "referenceAgentName": "reference agent",
    "summaryAgentName": "summary agent",
    "coordinatorAgentName": "coordinator agent"
  }
}
```

These names are written into summary notes for provenance only. The scripts do not depend on any specific agent platform.

### Optional MinerU Setup

MinerU is disabled by default. If you only need Zotero attachment and Obsidian reading-list management, leave it disabled:

```json
{
  "mineru": {
    "enabled": false
  }
}
```

To enable PDF-to-Markdown conversion, install MinerU separately and point `mineru.bin` at your local executable:

```json
{
  "mineru": {
    "enabled": true,
    "bin": "/absolute/path/to/mineru",
    "deviceMode": "mps",
    "timeoutSec": 3600,
    "taskResultDownloadTimeoutSec": 600,
    "pdfRenderTimeoutSec": 600
  }
}
```

Use `mps` for Apple Silicon when available, `cuda` for supported NVIDIA setups, or `cpu` as a slower fallback.

### Optional OpenClaw Queue Setup

The project is OpenClaw-first. In OpenClaw, user-facing long PDF conversions should be queued as command jobs instead of running inside a conversational agent turn:

```json
{
  "openclaw": {
    "cli": "openclaw",
    "commandCwd": "",
    "channel": "",
    "notifyToEnv": "OPENCLAW_MINERU_NOTIFY_TO",
    "outputMaxBytes": 12000,
    "timeoutGraceSec": 300
  }
}
```

Set `OPENCLAW_MINERU_NOTIFY_TO` only if your OpenClaw deployment requires an explicit delivery target. Keep the actual platform user/channel ID in your local environment, not in `config.json`:

```bash
export OPENCLAW_MINERU_NOTIFY_TO="your-openclaw-delivery-target"
```

Use `--dry-run` first to confirm the command job OpenClaw will create:

```bash
python3 scripts/queue_convert_and_notify.py \
  "/path/to/paper.pdf" \
  --config config.json \
  --zotero-id "ABCDEFGH" \
  --dry-run
```

Do not put private user IDs in the public config or documentation. Other agent systems can skip `queue_convert_and_notify.py` and call `convert_and_notify.py` directly from their own durable job runner, but they should keep the same completion rule: report success only after the Markdown artifact and image links validate.

### Smoke Test

Run the unit tests:

```bash
python3 -m unittest discover -s tests
```

Then test a reading-list write against your configured vault:

```bash
python3 scripts/reading_list.py \
  --config config.json \
  --action add \
  --status todo \
  --id "ABCDEFGH" \
  --title "Paper Title" \
  --file "Paper Title-2026-06-20-ABCDEFGH.md" \
  --journal "Example Journal" \
  --if "N/A" \
  --date "2026-06-20" \
  --doi "10.xxxx/example" \
  --summary "A concise reason to read this paper."
```

Then test a summary-note write:

```bash
python3 scripts/write_summary_note.py \
  --config config.json \
  --id "ABCDEFGH" \
  --title "Paper Title" \
  --journal "Example Journal" \
  --date "2026-06-20" \
  --doi "10.xxxx/example" \
  --summary "This is a short test summary."
```

`config.example.json` contains all supported settings. The most important fields are:

- `vaultRoot`: absolute path to the Obsidian vault
- `paths.academicNotesDir`: where converted paper Markdown files live
- `paths.summaryNotesDir`: where summary-agent notes are saved
- `paths.attachmentsDir`: where extracted images live
- `paths.academicTodoList`: close-reading list filename
- `paths.academicArchiveList`: archive list filename
- `agents.referenceAgentName`: display name for the agent that resolves references and Zotero metadata
- `agents.summaryAgentName`: display name for the agent that writes summaries
- `agents.coordinatorAgentName`: display name for the agent that performs deterministic writes
- `zotero.*Env`: names of environment variables holding Zotero credentials
- `mineru.*`: optional local PDF conversion backend
- `openclaw.*`: optional command-job queue settings for OpenClaw deployments

Do not commit `config.json` or `.env`.

## Safety Model

The workflow separates model work from deterministic state changes:

- the reference agent resolves metadata, DOI, Zotero item keys, and PDF attachments
- the summary agent summarizes and classifies
- the coordinator agent performs deterministic writes and reports only after verification
- summary notes are saved through `scripts/write_summary_note.py`
- Zotero metadata comes from Zotero or another trusted scholarly source
- reading-list writes happen only through `scripts/reading_list.py`
- PDF attachment happens only through `scripts/attach_pdf_by_doi.py`
- in OpenClaw, user-facing MinerU work should be queued through `scripts/queue_convert_and_notify.py`
- MinerU completion is accepted only after Markdown, Zotero ID, and image links are validated

This avoids common failures where an agent says it wrote or converted something but no usable Obsidian artifact exists.

## Publishing Checklist

Before publishing publicly:

- run a local secret scan for real paths, API tokens, platform identifiers, user IDs, and private agent names
- keep `config.json` and `.env` untracked
- run `python3 -m unittest discover -s tests`
- test with a temporary vault before testing on a real vault
- add screenshots or example output only if they contain no private paper notes or user IDs

## License

MIT.
