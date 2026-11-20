"""Offline checks for published GraphWalks parsing and local evidence accounting."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from model_claim_replay.core import ReplayError
from model_claim_replay.graphwalks import (
    extract_nodes, grade_response, score_recorded_bfs, save_scoring_report,
)


class GraphWalksOriginalGraderTests(unittest.TestCase):
    def test_exact_set(self):
        r = grade_response("reasoning\nFinal Answer: [a, b]", ["b", "a"])
        self.assertEqual((r["f1"], r["precision"], r["recall"]), (1, 1, 1))

    def test_partial_overlap_f1(self):
        r = grade_response("Final Answer: [a, c]", ["a", "b"])
        self.assertEqual(r["f1"], 0.5)
        self.assertEqual(r["precision"], 0.5)
        self.assertEqual(r["recall"], 0.5)

    def test_duplicate_predictions_do_not_change_f1(self):
        self.assertEqual(grade_response("Final Answer: [a, a]", ["a"])["f1"], 1.0)

    def test_well_formed_empty_sets_are_perfect(self):
        r = grade_response("Final Answer: []", [])
        self.assertEqual(r["f1"], 1.0)
        self.assertFalse(r["parse_failed"])

    def test_missing_marker_is_zero_even_if_gold_empty(self):
        r = grade_response("[]", [])
        self.assertEqual(r["f1"], 0)
        self.assertTrue(r["parse_failed"])

    def test_final_line_only_and_trailing_newline(self):
        self.assertTrue(grade_response("Final Answer: [a]\n", ["a"])["parse_failed"])
        self.assertTrue(grade_response("Final Answer: [a]\nThanks", ["a"])["parse_failed"])

    def test_case_sensitive_labels(self):
        self.assertEqual(grade_response("Final Answer: [A]", ["a"])["f1"], 0.0)

    def test_original_parser_is_permissive_about_marker_position(self):
        self.assertEqual(extract_nodes("anything [a] Final Answer:"), ({"a"}, False))

    def test_reject_invalid_reference(self):
        with self.assertRaisesRegex(ReplayError, "reference answer"):
            grade_response("Final Answer: [a]", [1])


class OfflineRecordedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.task_file = root / "tasks.jsonl"
        self.responses = root / "responses.jsonl"
        self.tasks = [
            {"id":"first","problem_type":"bfs","answer_nodes":["a","b"]},
            {"id":"second","problem_type":"bfs","answer_nodes":[]},
        ]
        self.epoch = "a" * 40
        self.write_tasks()
        self.write_responses([{"id":"first","status":"ok","output":"Final Answer: [a]"},
                              {"id":"second","status":"ok","output":"Final Answer: []"}])

    def write_tasks(self):
        self.task_file.write_text("".join(json.dumps(row)+"\n" for row in self.tasks))
        self.hash = hashlib.sha256(self.task_file.read_bytes()).hexdigest()

    def write_responses(self, rows):
        self.responses.write_text("".join(json.dumps(row)+"\n" for row in rows))

    def score(self):
        return score_recorded_bfs(self.task_file,self.responses,
                                  expected_index_sha256=self.hash,dataset_revision=self.epoch)

    def test_full_import_scores_offline(self):
        report=self.score()
        self.assertEqual(report["task_count"],2)
        self.assertAlmostEqual(report["mean_f1"],(2/3+1)/2)
        self.assertEqual(report["comparison_status"],"not_comparable")
        self.assertNotIn("Final Answer:", json.dumps(report))
        self.assertNotIn("answer_nodes", json.dumps(report))
        output=self.task_file.parent / "report.json"
        save_scoring_report(report,output)
        self.assertTrue(output.is_file())
        with self.assertRaisesRegex(ReplayError,"already exists"):
            save_scoring_report(report,output)

    def test_api_error_never_becomes_zero_grade(self):
        self.write_responses([{"id":"first","status":"ok","output":"Final Answer: [a]"},
                              {"id":"second","status":"error"}])
        report=self.score()
        self.assertIsNone(report["mean_f1"])
        self.assertEqual(report["api_errors"],1)
        self.assertEqual(report["graded"],1)

    def test_missing_answer_never_yields_full_score(self):
        self.write_responses([{"id":"first","status":"ok","output":"Final Answer: [a]"}])
        report=self.score()
        self.assertIsNone(report["mean_f1"])
        self.assertEqual(report["missing"],1)

    def test_cli_scores_synthetic_fixture_and_writes_report(self):
        from model_claim_replay.cli import main
        self.write_responses([
            {"id":"first","status":"ok","output":"Final Answer: [a]"},
            {"id":"second","status":"ok","output":"Final Answer: []"},
        ])
        output=self.task_file.parent / "cli-report.json"
        rc=main([
            "grade-graphwalks", "--index", str(self.task_file),
            "--responses", str(self.responses), "--index-sha256", self.hash,
            "--dataset-revision", self.epoch, "--out", str(output),
        ])
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(json.loads(output.read_text())["mean_f1"], 5 / 6)

    def test_reference_digest_mismatch_blocks(self):
        self.hash="0"*64
        with self.assertRaisesRegex(ReplayError,"do not match"):
            self.score()

    def test_response_with_unknown_task_is_refused(self):
        self.write_responses([{"id":"third","status":"ok","output":"Final Answer: []"}])
        with self.assertRaisesRegex(ReplayError,"IDs absent"):
            self.score()

    def test_non_bfs_task_is_refused(self):
        self.tasks[0]["problem_type"]="parents"
        self.write_tasks()
        with self.assertRaisesRegex(ReplayError,"non-BFS"):
            self.score()

    def test_malformed_model_answer_is_graded_zero(self):
        self.write_responses([{"id":"first","status":"ok","output":"No answer"},
                              {"id":"second","status":"ok","output":"Final Answer: []"}])
        report=self.score()
        self.assertEqual(report["mean_f1"],0.5)
        self.assertEqual(report["malformed"],1)


if __name__ == "__main__":
    unittest.main()
