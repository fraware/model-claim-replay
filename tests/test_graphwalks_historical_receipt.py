"""Regression checks for the original 23 Nov 2026 provider token-count receipt.

This receipt comes from an authenticated, no-generation GitHub Actions run.
Its SHA-256 is verified against the downloaded Actions artifact before being
committed. The test verifies its byte identity and internal arithmetic only:
it cannot independently authenticate the provider's internal accounting.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from decimal import Decimal
from pathlib import Path

from model_claim_replay.graphwalks_runtime import (
    CONTEXT_LIMIT, DATASET_SHA256, INDEX_SHA256, MODEL, _usd,
)

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = (
    ROOT / "evidence" / "graphwalks" /
    "gemini-4-neon-two-task-token-plan-2026-11-23.json"
)
ORIGINAL_SHA256 = "552f98fd33a53f585362abaee989c601c7754f48008792255c963cd45449f92f"


class HistoricalProviderCountTests(unittest.TestCase):
    """Check source commitments and feasibility, never provider generation."""

    def test_original_provider_artifact_is_byte_identical(self) -> None:
        raw = RECEIPT.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), ORIGINAL_SHA256)
        data = json.loads(raw)
        self.assertEqual(data["model"], MODEL)
        self.assertEqual(data["parquet_sha256"], DATASET_SHA256)
        self.assertEqual(data["index_sha256"], INDEX_SHA256)
        self.assertEqual(data["context_limit"], CONTEXT_LIMIT)
        self.assertEqual(data["comparison_status"], "not_comparable")
        self.assertEqual(data["planned_count"], 2)
        self.assertEqual(data["max_output_tokens"], 8192)
        self.assertEqual(data["blocked_for_context"], 1)

        rows = data["planned_tasks"]
        self.assertEqual(
            [(r["id"], r["input_tokens"]) for r in rows],
            [("bfs-row-000100", 355124), ("bfs-row-000300", 1419783)],
        )
        for row in rows:
            tokens = row["input_tokens"]
            self.assertEqual(
                row["fits_context_with_output_allowance"],
                tokens + data["max_output_tokens"] <= CONTEXT_LIMIT,
            )
            self.assertEqual(
                Decimal(row["maximum_reserved_cost_usd"]),
                _usd(tokens, data["max_output_tokens"]),
            )
        self.assertGreater(rows[1]["input_tokens"], CONTEXT_LIMIT)
        self.assertEqual(rows[1]["input_tokens"] - CONTEXT_LIMIT, 371207)
        self.assertEqual(
            Decimal(data["maximum_reserved_cost_usd"]),
            sum(Decimal(row["maximum_reserved_cost_usd"]) for row in rows),
        )

    def test_original_receipt_does_not_contain_prompt_or_model_output(self) -> None:
        data = json.loads(RECEIPT.read_text())
        for task in data["planned_tasks"]:
            self.assertEqual(
                set(task),
                {"id", "prompt_sha256", "input_tokens",
                 "fits_context_with_output_allowance",
                 "maximum_reserved_cost_usd"},
            )
        self.assertNotIn("output", data)
        self.assertNotIn("prompt", data)
        self.assertIn("not_a_model_evaluation", data["evidence_level"])


if __name__ == "__main__":
    unittest.main()
