"""Bind the public log summary to source commitments and the two measured counts.

The original Actions archive digest is provider metadata, not an independently
recomputed local hash. These tests verify consistency and scope, not provenance
authentication or actual provider charges.
"""
from __future__ import annotations

import json
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "website"


class OpenAIPreflightReceiptTests(unittest.TestCase):
    def test_source_and_arithmetic(self):
        data = json.loads((ROOT / "graphwalks-openai-preflight.json").read_text())
        source = json.loads((ROOT / "graphwalks-audit.json").read_text())
        gemini = json.loads((ROOT / "graphwalks-gemini-feasibility.json").read_text())
        self.assertEqual(data["source_dataset_revision"], source["source"]["revision"])
        self.assertEqual(data["source_parquet_sha256"], source["source"]["parquet_sha256_verified"])
        self.assertEqual(data["reference_index_sha256"], source["source"]["reference_index_sha256"])
        index = next(n for n, task in enumerate(source["tasks"]) if task["id"] == data["task_id"])
        self.assertEqual(data["task_id"], "bfs-row-000100")
        self.assertEqual(data["prompt_sha256"], source["tasks"][index]["prompt_sha256"])
        self.assertEqual(gemini["input_token_counts_in_pinned_index_order"][index], 355124)
        self.assertEqual(data["input_tokens"], 255598)
        self.assertEqual(data["provider_run"], "https://github.com/fraware/model-claim-replay/actions/runs/45337852354")
        self.assertEqual(data["actions_artifact"]["id"], 14894591664)
        self.assertFalse(data["generation_performed"])
        self.assertFalse(data["published_claim_reproduced"])
        self.assertNotIn("grade", data)
        self.assertNotIn("output", data)
        self.assertIn("not a byte-identical copy", data["limitations"])
        self.assertTrue(data["input_tokens"] <= data["input_limit"])
        self.assertTrue(data["input_tokens"] + data["max_output_tokens"] <= data["context_limit"])
        expected = (
            Decimal(data["input_usd_per_million_upper"]) * data["input_tokens"]
            + Decimal(data["output_usd_per_million_upper"]) * data["max_output_tokens"]
        ) / Decimal(1000000)
        self.assertEqual(Decimal(data["reservation_usd"]), expected)
        self.assertLessEqual(expected, Decimal(data["planning_ceiling_usd"]))
        page = (ROOT / "graphwalks.html").read_text()
        self.assertIn(data["provider_run"], page)
        self.assertIn("graphwalks-openai-preflight.json", page)


if __name__ == "__main__":
    unittest.main()
