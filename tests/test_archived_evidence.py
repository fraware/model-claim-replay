"""Execute the actual offline verifiers against the historical originals."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_archived_evidence import verify_archived_evidence


class ArchivedEvidenceTests(unittest.TestCase):
    def test_original_archives_recompute_disclosed_scores(self):
        result = verify_archived_evidence()
        pilot, campaign = result["pilot"], result["campaign"]
        self.assertEqual(pilot["grade"]["f1"], 1.0)
        self.assertEqual(campaign["selected_tasks"], 16)
        self.assertEqual(campaign["attempted"], 8)
        self.assertEqual(campaign["disclosed_scores_recomputed"], 7)
        self.assertEqual(campaign["withheld_scores_not_recomputed"], 1)
        self.assertFalse(campaign["all_graded_scores_recomputed"])
        self.assertEqual(campaign["bands"]["overall"]["conditional_mean_f1"], 0.875)
        self.assertIsNone(campaign["bands"]["overall"]["full_selected_mean_f1"])
        for report in (pilot, campaign):
            self.assertFalse(report["published_claim_reproduced"])
            self.assertFalse(report["provider_execution_authenticated"])
            self.assertFalse(report["full_answer_extraction_verified"])


if __name__ == "__main__":
    unittest.main()
