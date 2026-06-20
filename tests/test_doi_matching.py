from __future__ import annotations

import sys
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from scripts import attach_pdf_by_doi  # noqa: E402


class DoiMatchingTests(unittest.TestCase):
    def test_normalize_doi(self) -> None:
        cases = {
            "https://doi.org/10.1234/ABC.": "10.1234/ABC",
            "http://dx.doi.org/10.5555/example);": "10.5555/example",
            "doi: 10.1000/test": "10.1000/test",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(attach_pdf_by_doi.normalize_doi(raw), expected)

    def test_validate_item_key(self) -> None:
        self.assertTrue(attach_pdf_by_doi.validate_item_key("ABCDEFGH"))
        self.assertTrue(attach_pdf_by_doi.validate_item_key("AB12CD34"))
        self.assertFalse(attach_pdf_by_doi.validate_item_key("abc12345"))
        self.assertFalse(attach_pdf_by_doi.validate_item_key("TOO-LONG"))

    def test_item_matches_doi_field_or_extra(self) -> None:
        self.assertTrue(
            attach_pdf_by_doi.item_matches_doi(
                {"DOI": "https://doi.org/10.1234/example"},
                "10.1234/example",
            )
        )
        self.assertTrue(
            attach_pdf_by_doi.item_matches_doi(
                {"extra": "Submitted version\nDOI: 10.5555/preprint"},
                "10.5555/preprint",
            )
        )
        self.assertFalse(
            attach_pdf_by_doi.item_matches_doi(
                {"DOI": "10.1234/other"},
                "10.1234/example",
            )
        )

    def test_find_doi_in_text(self) -> None:
        text = "Paper metadata\nDOI: 10.7777/sample.paper\nReferences\n10.9999/ref"
        self.assertEqual(attach_pdf_by_doi.find_doi_in_text(text), "10.7777/sample.paper")


if __name__ == "__main__":
    unittest.main()

