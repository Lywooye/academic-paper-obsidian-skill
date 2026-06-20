from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from scripts import config as pipeline_config  # noqa: E402
from scripts import reading_list  # noqa: E402


class ReadingListTests(unittest.TestCase):
    def make_config(self, tmp_path: Path) -> dict:
        vault = tmp_path / "vault"
        cfg = pipeline_config.deep_merge(
            pipeline_config.DEFAULT_CONFIG,
            {
                "vaultRoot": str(vault),
                "paths": {
                    "readingDir": "01_Maps/03_Reading",
                    "academicTodoList": "Academic Papers - To Read.md",
                    "academicArchiveList": "Academic Papers - Archive.md",
                    "academicNotesDir": "00_Inbox/PDFs",
                    "attachmentsDir": "99_Resources/Attachments",
                    "mineruWorkDir": "99_Resources/mineru",
                    "statusDir": ".academic-paper-zotero-obsidian/tmp",
                },
            },
        )
        (vault / "00_Inbox" / "PDFs").mkdir(parents=True)
        (vault / "01_Maps" / "03_Reading").mkdir(parents=True)
        return cfg

    def test_obsidian_link_resolves_existing_bare_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.make_config(Path(tmp))
            note = Path(cfg["vaultRoot"]) / "00_Inbox" / "PDFs" / "Exact Paper-2026-06-20-ABCDEFGH.md"
            note.write_text("# Exact Paper\n", encoding="utf-8")

            link = reading_list.to_obsidian_link(cfg, "Exact Paper-2026-06-20-ABCDEFGH.md")
            self.assertEqual(link, "00_Inbox/PDFs/Exact Paper-2026-06-20-ABCDEFGH")

    def test_obsidian_link_resolves_real_mineru_filename_by_zotero_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.make_config(Path(tmp))
            note = Path(cfg["vaultRoot"]) / "00_Inbox" / "PDFs" / "Sanitized Real Title-2026-06-20-ABCDEFGH.md"
            note.write_text("# Sanitized Real Title\n", encoding="utf-8")

            link = reading_list.to_obsidian_link(cfg, "Prompt Title-2026-06-20-ABCDEFGH.md")
            self.assertEqual(link, "00_Inbox/PDFs/Sanitized Real Title-2026-06-20-ABCDEFGH")

    def test_add_entry_inserts_at_top_and_renumbers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.make_config(Path(tmp))
            result_a = reading_list.add_entry(
                cfg,
                "todo",
                "ABCDEFGH",
                "First Paper",
                "First Paper-2026-06-20-ABCDEFGH.md",
                summary="First summary",
            )
            result_b = reading_list.add_entry(
                cfg,
                "todo",
                "IJKL1234",
                "Second Paper",
                "Second Paper-2026-06-20-IJKL1234.md",
                summary="Second summary",
            )
            self.assertTrue(result_a["success"])
            self.assertTrue(result_b["success"])
            text = reading_list.list_file(cfg, "todo").read_text(encoding="utf-8")
            self.assertLess(text.index("1. [[00_Inbox/PDFs/Second Paper"), text.index("2. [[00_Inbox/PDFs/First Paper"))
            self.assertIn("Zotero ID: ABCDEFGH", text)
            self.assertIn("Zotero ID: IJKL1234", text)

    def test_move_entry_from_todo_to_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.make_config(Path(tmp))
            reading_list.add_entry(
                cfg,
                "todo",
                "ABCDEFGH",
                "First Paper",
                "First Paper-2026-06-20-ABCDEFGH.md",
            )
            result = reading_list.move_entry(cfg, "ABCDEFGH")
            self.assertTrue(result["success"])
            text = reading_list.list_file(cfg, "todo").read_text(encoding="utf-8")
            to_read = text.split("## To Read", 1)[1].split("## Read", 1)[0]
            read = text.split("## Read", 1)[1]
            self.assertNotIn("ABCDEFGH", to_read)
            self.assertIn("ABCDEFGH", read)


if __name__ == "__main__":
    unittest.main()
