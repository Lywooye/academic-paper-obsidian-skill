from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from scripts import config as pipeline_config  # noqa: E402
from scripts import write_summary_note  # noqa: E402


class WriteSummaryNoteTests(unittest.TestCase):
    def make_config(self, tmp_path: Path) -> dict:
        vault = tmp_path / "vault"
        cfg = pipeline_config.deep_merge(
            pipeline_config.DEFAULT_CONFIG,
            {
                "vaultRoot": str(vault),
                "paths": {
                    "summaryNotesDir": "11_Academic/Summaries",
                },
                "agents": {
                    "summaryAgentName": "My Summary Agent",
                    "coordinatorAgentName": "My Coordinator",
                },
            },
        )
        return cfg

    def test_write_summary_note_uses_configured_agent_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.make_config(Path(tmp))
            result = write_summary_note.write_summary_note(
                cfg,
                entry_id="ABCDEFGH",
                title="A Useful Paper",
                cn_title="一篇有用的论文",
                journal="Example Journal",
                date="2026-06-20",
                doi="10.1234/example",
                summary_text="This is the summary body.",
            )
            self.assertTrue(result["success"])
            output = Path(result["output_md"])
            text = output.read_text(encoding="utf-8")
            self.assertIn("My Summary Agent", text)
            self.assertIn("My Coordinator", text)
            self.assertIn("This is the summary body.", text)
            self.assertEqual(result["vault_link"], "11_Academic/Summaries/A Useful Paper-2026-06-20-ABCDEFGH")

    def test_dry_run_does_not_write_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.make_config(Path(tmp))
            result = write_summary_note.write_summary_note(
                cfg,
                entry_id="ABCDEFGH",
                title="A Useful Paper",
                summary_text="This is the summary body.",
                dry_run=True,
            )
            self.assertTrue(result["success"])
            self.assertFalse(Path(result["output_md"]).exists())

    def test_empty_summary_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.make_config(Path(tmp))
            result = write_summary_note.write_summary_note(
                cfg,
                entry_id="ABCDEFGH",
                title="A Useful Paper",
                summary_text="",
            )
            self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()

