# Academic Paper to Obsidian Skill

OpenClaw-style skill and scripts for a Zotero-backed academic reading workflow:

- attach a local PDF to the correct Zotero item by DOI or item key
- write academic papers into Obsidian reading/archive lists
- resolve bare Markdown filenames into vault-relative wikilinks
- optionally convert PDFs to Markdown with MinerU and validate image links

This repository intentionally keeps personal paths, API keys, Feishu IDs, agent names, and private logs out of the package. Configure everything through `config.json` and environment variables.

## Who It Is For

This is useful if you use:

- Zotero as the source of truth for paper metadata
- Obsidian as the durable reading list and note vault
- an agent system such as OpenClaw to coordinate literature search, summarization, and file operations
- optionally MinerU for PDF-to-Markdown conversion

It is probably too specialized for general readers, but it should be useful to researchers who already combine Zotero and Obsidian and want fewer broken PDF/list handoffs.

## Quick Start

```bash
git clone <your-repo-url>
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

Convert a PDF to Markdown with MinerU:

```bash
python3 scripts/convert_and_notify.py "/path/to/paper.pdf" --config config.json --zotero-id "ABCDEFGH"
```

MinerU is optional. Leave `mineru.enabled=false` until you have a working local MinerU install.

## Configuration

`config.example.json` contains all supported settings. The most important fields are:

- `vaultRoot`: absolute path to the Obsidian vault
- `paths.academicNotesDir`: where converted paper Markdown files live
- `paths.attachmentsDir`: where extracted images live
- `paths.academicTodoList`: close-reading list filename
- `paths.academicArchiveList`: archive list filename
- `zotero.*Env`: names of environment variables holding Zotero credentials
- `mineru.*`: optional local PDF conversion backend

Do not commit `config.json` or `.env`.

## Safety Model

The workflow separates model work from deterministic state changes:

- agents summarize and classify
- Zotero metadata comes from Zotero or another trusted scholarly source
- reading-list writes happen only through `scripts/reading_list.py`
- PDF attachment happens only through `scripts/attach_pdf_by_doi.py`
- MinerU completion is accepted only after Markdown and image links are validated

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
