"""Untrusted public dataset metadata checks, entirely offline."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from graphwalks_preflight import PreflightError, extract_dataset_metadata  # noqa: E402


def fixture():
    return {
        "sha": "a" * 40,
        "private": False,
        "gated": False,
        "cardData": {"license": "mit"},
        "siblings": [
            {"rfilename": "graphwalks_256k_to_1mil.parquet", "size": 297_000_000,
             "lfs": {"sha256": "b" * 64}},
            {"rfilename": "graphwalks_128k_and_shorter.parquet"},
        ],
    }


class DatasetPreflightTests(unittest.TestCase):
    def test_valid_source_record(self):
        result = extract_dataset_metadata(fixture())
        self.assertEqual(result["dataset_repository_commit"], "a" * 40)
        self.assertEqual(result["files"][0]["lfs_sha256"], "b" * 64)
        self.assertIsNone(result["files"][1]["size_bytes"])
        self.assertEqual(result["evidence_level"], "upstream_metadata_only_not_dataset_bytes_verified")

    def test_reject_invalid_revision(self):
        item = fixture(); item["sha"] = "main"
        with self.assertRaisesRegex(PreflightError, "commit"):
            extract_dataset_metadata(item)

    def test_reject_gated_and_private(self):
        for name, value in (("gated", True), ("private", True)):
            item = fixture(); item[name] = value
            with self.assertRaisesRegex(PreflightError, "private or access-gated"):
                extract_dataset_metadata(item)

    def test_reject_missing_file(self):
        item = fixture(); item["siblings"].pop()
        with self.assertRaisesRegex(PreflightError, "required files"):
            extract_dataset_metadata(item)

    def test_reject_wrong_license(self):
        item = fixture(); item["cardData"]["license"] = "unknown"
        with self.assertRaisesRegex(PreflightError, "MIT license"):
            extract_dataset_metadata(item)

    def test_reject_invalid_digest(self):
        item = fixture(); item["siblings"][0]["lfs"]["sha256"] = "not-a-sha"
        with self.assertRaisesRegex(PreflightError, "LFS digest"):
            extract_dataset_metadata(item)

    def test_reject_duplicate_files(self):
        item = fixture(); item["siblings"].append(dict(item["siblings"][0]))
        with self.assertRaisesRegex(PreflightError, "Duplicate"):
            extract_dataset_metadata(item)

    def test_boolean_size_is_rejected(self):
        item = fixture(); item["siblings"][0]["size"] = True
        with self.assertRaisesRegex(PreflightError, "file size"):
            extract_dataset_metadata(item)


if __name__ == "__main__":
    unittest.main()
