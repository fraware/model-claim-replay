"""Validate the user-facing explorer against the pinned public source evidence."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "website" / "graphwalks-audit.json"


class PublicGraphWalksExplorerTests(unittest.TestCase):
    def test_complete_public_candidate_cohort_without_answers_or_prompts(self):
        data = json.loads(DATA.read_text())
        self.assertEqual(data["schema_version"], "graphwalks-public-explorer-v1")
        self.assertEqual(data["summary"]["source_rows"], 400)
        self.assertEqual(data["summary"]["bfs_tasks"], 200)
        tasks = data["tasks"]
        self.assertEqual(len(tasks), 200)
        self.assertEqual(len({row["id"] for row in tasks}), 200)
        self.assertEqual([row["source_row_index"] for row in tasks], sorted(row["source_row_index"] for row in tasks))
        for row in tasks:
            self.assertEqual(set(row), {"id", "source_row_index", "prompt_chars", "answer_node_count", "prompt_sha256"})
            self.assertEqual(row["id"], f"bfs-row-{row['source_row_index']:06d}")
            self.assertRegex(row["prompt_sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(row["prompt_chars"], 0)
        self.assertNotIn("answer_nodes", DATA.read_text())
        self.assertNotIn("Final Answer:", DATA.read_text())

    def test_derived_aggregate_math(self):
        d = json.loads(DATA.read_text())
        chars = sorted(row["prompt_chars"] for row in d["tasks"])
        s = d["summary"]
        self.assertEqual(s["shorter_tasks"], sum(c < 1000000 for c in chars))
        self.assertEqual(s["longer_tasks"], sum(c >= 1000000 for c in chars))
        self.assertEqual(s["min_prompt_chars"], chars[0])
        self.assertEqual(s["median_prompt_chars"], (chars[99]+chars[100])/2)
        self.assertEqual(s["max_prompt_chars"], chars[-1])
        self.assertEqual(s["total_prompt_chars"], sum(chars))
        self.assertEqual(s["shorter_tasks"], 100)
        self.assertEqual(s["longer_tasks"], 100)

    def test_independent_algorithmic_control_is_source_matched_and_not_a_model_score(self):
        import hashlib
        path = ROOT / "website" / "graphwalks-control.json"
        raw = path.read_bytes()
        control = json.loads(raw)
        source = json.loads(DATA.read_text())
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "627be857ef90db4fe9ff3363f810c313b8454ee8ab0d5dfb2383825ec204bc0b")
        self.assertEqual(control["schema_version"], "graphwalks-algorithmic-control-v1")
        self.assertEqual(control["comparison_status"], "not_comparable_to_gemini_model_claim")
        self.assertEqual(control["source_parquet_sha256"], source["source"]["parquet_sha256_verified"])
        self.assertEqual(control["reference_index_sha256"], source["source"]["reference_index_sha256"])
        self.assertEqual((control["graded"], control["parse_failures"]), (200, 0))
        self.assertEqual(control["mean_f1_full_cohort"], 1.0)
        by_id = {row["id"]: row for row in control["tasks"]}
        self.assertEqual(len(by_id), 200)
        self.assertEqual(sum(row["band"] == "short" for row in by_id.values()), 100)
        self.assertEqual(sum(row["band"] == "long" for row in by_id.values()), 100)
        for row in source["tasks"]:
            result = by_id[row["id"]]
            self.assertEqual(result["prompt_sha256"], row["prompt_sha256"])
            self.assertEqual(result["status"], "graded")
            self.assertEqual(result["f1"], 1.0)
        self.assertNotIn("Final Answer:", raw.decode())
        self.assertNotIn("answer_nodes", raw.decode())
        html = (ROOT / "website" / "graphwalks.html").read_text()
        self.assertIn("OPENAI CAMPAIGN · GRADED SUBSET", html)
        self.assertIn("8 graded of 16 selected", html)
        self.assertIn("ONE PRESPECIFIED SOURCE TASK", html)
        self.assertIn("No full-cohort mean is reported for all 16 selected tasks", html)
        self.assertIn("ALGORITHMIC CONTROL", html)
        self.assertIn("No publisher claim reproduced", html)
        self.assertIn("does not reproduce or invalidate the publisher", html)
        self.assertIn("One original task. All 9 reference nodes recovered.", html)
        self.assertIn("graphwalks-control.json", (ROOT / "website" / "graphwalks.js").read_text())

    def test_provenance_hashes_and_claim_status(self):
        d = json.loads(DATA.read_text())
        src = d["source"]
        self.assertEqual(src["revision"], "be6cc6ecf9b4d495b07d1ff53d2a16598e90fed7")
        self.assertEqual(src["parquet_sha256_verified"], "537879431c72a42e3b500f80efc3047e7facb90390b6063d33679b4320985911")
        self.assertEqual(src["reference_index_sha256"], "250d80874ad9bc8edf278cf3bf7aa145da3f2b34967c5504b8fa8703358480ee")
        self.assertIn("No model inference", d["disclaimer"])
        html = (ROOT / "website" / "graphwalks.html").read_text()
        self.assertIn("No publisher claim reproduced", html)
        self.assertIn("does not reproduce or invalidate the publisher", html)
        self.assertIn("One original task. All 9 reference nodes recovered.", html)
        self.assertIn("graphwalks-audit.json", (ROOT / "website" / "graphwalks.js").read_text())


if __name__ == "__main__":
    unittest.main()
