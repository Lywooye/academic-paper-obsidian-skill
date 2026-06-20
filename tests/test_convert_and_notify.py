from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from scripts import config as pipeline_config  # noqa: E402
from scripts import convert_and_notify  # noqa: E402


class ConvertAndNotifyValidationTests(unittest.TestCase):
    def make_config(self, tmp_path: Path) -> dict:
        vault = tmp_path / "vault"
        return pipeline_config.deep_merge(
            pipeline_config.DEFAULT_CONFIG,
            {
                "vaultRoot": str(vault),
                "paths": {
                    "attachmentsDir": "99_Resources/Attachments",
                },
            },
        )

    def test_validate_conversion_result_checks_zotero_id_and_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cfg = self.make_config(tmp_path)
            vault = Path(cfg["vaultRoot"])
            attachments = vault / "99_Resources" / "Attachments"
            attachments.mkdir(parents=True)
            (attachments / "figure.png").write_bytes(b"png")
            md = vault / "00_Inbox" / "PDFs" / "Paper-2026-06-20-ABCDEFGH.md"
            md.parent.mkdir(parents=True)
            md.write_text("![[99_Resources/Attachments/figure.png]]\n", encoding="utf-8")

            result = convert_and_notify.validate_conversion_result(cfg, {"output_md": str(md)}, "ABCDEFGH")
            self.assertTrue(result["success"])
            self.assertEqual(result["validation"]["missing_image_count"], 0)

            mismatch = convert_and_notify.validate_conversion_result(cfg, {"output_md": str(md)}, "ZZZZ9999")
            self.assertFalse(mismatch["success"])

    def test_validate_conversion_result_fails_missing_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cfg = self.make_config(tmp_path)
            vault = Path(cfg["vaultRoot"])
            md = vault / "00_Inbox" / "PDFs" / "Paper-2026-06-20-ABCDEFGH.md"
            md.parent.mkdir(parents=True)
            md.write_text("![[99_Resources/Attachments/missing.png]]\n", encoding="utf-8")

            result = convert_and_notify.validate_conversion_result(cfg, {"output_md": str(md)}, "ABCDEFGH")
            self.assertFalse(result["success"])
            self.assertEqual(result["validation"]["missing_image_count"], 1)


if __name__ == "__main__":
    unittest.main()

