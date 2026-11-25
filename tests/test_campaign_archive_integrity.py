"""Regression check of the original historical paid campaign ZIP."""
from pathlib import Path
import hashlib
import json
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "evidence/graphwalks/openai-campaign-paid-evidence-2026-11-24.zip"
SUMMARY = ROOT / "evidence/graphwalks/openai-campaign-result-summary-2026-11-24.json"


class CampaignArchiveIntegrityTests(unittest.TestCase):
    def test_original_archive_bytes_and_manifest(self):
        raw = ARCHIVE.read_bytes()
        self.assertEqual(len(raw), 37801)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), "f6a2dc1af63a5f50be087f1db45de0145a7880ac527852ebf0be0d9ef8a3d113")
        derived = json.loads(SUMMARY.read_bytes())
        self.assertTrue(derived["original_archive_permanently_committed"])
        self.assertEqual(derived["original_archive_path"], ARCHIVE.relative_to(ROOT).as_posix())
        self.assertEqual(derived["artifact_sha256"], hashlib.sha256(raw).hexdigest())
        with zipfile.ZipFile(ARCHIVE) as z:
            expected = {"plan.json", "summary.json"}
            expected.update(f"task-{i:02d}-outcome.json" for i in range(1, 17))
            expected.update(f"task-{i:02d}-intent.json" for i in range(1, 9))
            self.assertEqual(len(z.namelist()), len(expected))
            self.assertEqual(set(z.namelist()), expected)
            self.assertEqual(hashlib.sha256(z.read("plan.json")).hexdigest(), derived["plan_sha256"])
            report = json.loads(z.read("summary.json"))
            self.assertEqual(report["status"], "finished")
            self.assertEqual(report["generation_attempted"], derived["graded"])
            self.assertEqual(report["overall"]["selected"], derived["selected"])
            self.assertEqual(report["overall"]["graded"], derived["graded"])
            self.assertEqual(report["overall"]["parse_failures"], derived["parse_failures"])
            self.assertEqual(report["overall"]["conditional_mean_f1"], derived["recorded_conditional_mean_f1"])
            self.assertIsNone(report["overall"]["full_selected_mean_f1"])
            self.assertEqual(report["known_usage_cost_estimate_usd"], derived["conservative_usage_cost_estimate_usd"])
            self.assertFalse(report["published_claim_reproduced"])


if __name__ == "__main__":
    unittest.main()
