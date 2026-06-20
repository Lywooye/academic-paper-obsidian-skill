from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from scripts import config as pipeline_config  # noqa: E402
from scripts import convert_pdf as convert_pdf_module  # noqa: E402


class ConvertPdfTests(unittest.TestCase):
    def make_config(self, tmp_path: Path, mineru: dict | None = None) -> dict:
        override: dict = {"vaultRoot": str(tmp_path / "vault")}
        if mineru is not None:
            override["mineru"] = mineru
        return pipeline_config.deep_merge(pipeline_config.DEFAULT_CONFIG, override)

    def test_disabled_mineru_does_not_create_work_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pdf = tmp_path / "paper.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")
            cfg = self.make_config(tmp_path, {"enabled": False})
            work_root = Path(cfg["vaultRoot"]) / "99_Resources" / "mineru"

            with patch.object(convert_pdf_module, "run_mineru") as run_mineru:
                result = convert_pdf_module.convert_pdf(cfg, str(pdf))

            self.assertFalse(result["success"])
            self.assertIn("MinerU is disabled", result["error"])
            self.assertFalse(work_root.exists())
            run_mineru.assert_not_called()

    def test_failed_mineru_removes_empty_work_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pdf = tmp_path / "paper.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")
            cfg = self.make_config(tmp_path, {"enabled": True})
            work_root = Path(cfg["vaultRoot"]) / "99_Resources" / "mineru"

            with patch.object(convert_pdf_module, "run_mineru", return_value=(False, "conversion failed")):
                result = convert_pdf_module.convert_pdf(cfg, str(pdf))

            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "conversion failed")
            self.assertIn("work_dir", result)
            self.assertFalse(Path(result["work_dir"]).exists())
            self.assertTrue(work_root.exists())
            self.assertEqual(list(work_root.iterdir()), [])

    def test_missing_mineru_binary_returns_clean_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pdf = tmp_path / "paper.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")
            cfg = self.make_config(
                tmp_path,
                {"enabled": True, "bin": "/no/such/mineru_binary_xyz"},
            )
            work_dir = tmp_path / "work"
            work_dir.mkdir()

            ok, error = convert_pdf_module.run_mineru(cfg, pdf, work_dir, 30)

            self.assertFalse(ok)
            self.assertIn("MinerU binary not found", error)
            self.assertIn("/no/such/mineru_binary_xyz", error)

    def test_missing_mineru_binary_via_convert_pdf_cleans_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pdf = tmp_path / "paper.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")
            cfg = self.make_config(
                tmp_path,
                {"enabled": True, "bin": "/no/such/mineru_binary_xyz"},
            )
            work_root = Path(cfg["vaultRoot"]) / "99_Resources" / "mineru"

            result = convert_pdf_module.convert_pdf(cfg, str(pdf))

            self.assertFalse(result["success"])
            self.assertIn("MinerU binary not found", result["error"])
            self.assertFalse(Path(result["work_dir"]).exists())
            self.assertEqual(list(work_root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
