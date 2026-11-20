"""Paired comparison tests, including incompatible protocols and failed outcomes."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from model_claim_replay.cli import main
from model_claim_replay.compare import compare_inspect_bundles, compare_report_html
from model_claim_replay.inspect_evidence import import_inspect_bundle
from test_inspect_evidence import CLAIM_PATH, fixture_log


class CompareInspectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.left_path = root / "left.eval"
        self.right_path = root / "right.eval"
        self.left_path.write_bytes(b"synthetic-left-inspect-log")
        self.right_path.write_bytes(b"synthetic-right-inspect-log")
        self.left_dir = root / "left"
        self.right_dir = root / "right"
        self.left_log = fixture_log(model="model-a")
        self.right_log = fixture_log(model="model-b")

    def import_pair(self):
        import_inspect_bundle(CLAIM_PATH, self.left_path, self.left_dir, log=self.left_log)
        import_inspect_bundle(CLAIM_PATH, self.right_path, self.right_dir, log=self.right_log)
        return compare_inspect_bundles(CLAIM_PATH, self.left_dir, self.right_dir)

    def test_paired_improvement_and_bootstrap(self):
        for row in self.right_log.samples[0:2]:
            row.scores["golden_answer_scorer"].value = {"accuracy": 0}
            row.scores["golden_answer_scorer"].metadata = {"result": "fail"}
        result = self.import_pair()
        self.assertEqual(result["status"], "paired_diagnostic_only")
        self.assertEqual(result["paired_samples"], 4)
        self.assertEqual(result["paired_tasks"], 2)
        self.assertEqual(result["delta_right_minus_left_pp"], -50)
        self.assertEqual(result["task_cluster_bootstrap_95_pp"], [-100, 0])
        self.assertFalse(result["covers_reference_grid"])
        self.assertIn("not authenticate model execution", result["interpretation"])

    def test_mismatched_task_sets_are_blocked(self):
        self.right_log.samples[0].id = "different-task"
        result = self.import_pair()
        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["delta_right_minus_left_pp"])
        self.assertTrue(any("Scored task/epoch sets differ" in b for b in result["blockers"]))

    def test_changed_chart_is_blocked_despite_matching_task_identifiers(self):
        self.right_log.samples[0].input[0].content[1].image = (
            "data:image/png;base64,aGVsbG8="
        )
        self.right_log.samples[1].input[0].content[1].image = (
            "data:image/png;base64,aGVsbG8="
        )
        result = self.import_pair()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("Chart inputs or reference answers differ" in b
                            for b in result["blockers"]))

    def test_changed_reference_answer_is_blocked(self):
        self.right_log.samples[0].target = "ALTERED GOLDEN ANSWER"
        self.right_log.samples[1].target = "ALTERED GOLDEN ANSWER"
        result = self.import_pair()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("Chart inputs or reference answers differ" in b
                            for b in result["blockers"]))

    def test_missing_image_bytes_are_blocked(self):
        for log in (self.left_log, self.right_log):
            for record in log.samples:
                record.input[0].content[1].image = "/tmp/chart.png"
        result = self.import_pair()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("Unpinned chart content" in b for b in result["blockers"]))

    def test_judge_mismatch_is_blocked(self):
        getattr(self.right_log, "eval").task_args["judge_model"] = "another/judge"
        result = self.import_pair()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("judge_model" in x for x in result["blockers"]))

    def test_missing_judge_is_blocked_even_when_equal(self):
        del getattr(self.left_log, "eval").task_args["judge_model"]
        del getattr(self.right_log, "eval").task_args["judge_model"]
        result = self.import_pair()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("unspecified at judge_model" in x for x in result["blockers"]))

    def test_irregular_epoch_grid_is_blocked(self):
        # Both inputs omit the same epoch. Identical observed IDs alone are
        # insufficient to establish a properly balanced repeated-run design.
        self.left_log.samples.pop()
        self.right_log.samples.pop()
        result = self.import_pair()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("irregular per-task" in x for x in result["blockers"]))

    def test_missing_scores_are_blocked(self):
        self.right_log.samples[0].scores = {}
        result = self.import_pair()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("errored or unscored" in x for x in result["blockers"]))

    def test_same_source_log_is_blocked(self):
        self.right_path.write_bytes(self.left_path.read_bytes())
        result = self.import_pair()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("same original source log" in b for b in result["blockers"]))

    def test_tampering_with_one_bundle_blocks_verification(self):
        self.import_pair()
        p = self.right_dir / "results.jsonl"
        p.write_text(p.read_text() + "\n")
        from model_claim_replay.core import ReplayError
        with self.assertRaisesRegex(ReplayError, "changed"):
            compare_inspect_bundles(CLAIM_PATH, self.left_dir, self.right_dir)

    def test_report_and_cli_html_escape_model_labels(self):
        getattr(self.right_log, "eval").model = "<script>alert(1)</script>"
        result = self.import_pair()
        markup = compare_report_html(result)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", markup)
        self.assertNotIn("<script>", markup)
        html_path = self.left_dir.parent / "paired.html"
        self.assertEqual(main(["compare-inspect", "--claim", str(CLAIM_PATH),
                               "--left", str(self.left_dir), "--right", str(self.right_dir),
                               "--format", "html", "--output", str(html_path)]), 0)
        self.assertIn("Paired difference", html_path.read_text())


if __name__ == "__main__":
    unittest.main()
