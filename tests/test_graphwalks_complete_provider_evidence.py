"""Source-ordered, provider-measured GraphWalks candidate feasibility evidence.

This check binds the public compact receipt to the original, byte-identical
GitHub Actions token-count plan. It does not claim authenticated model
generation, benchmark scoring, or equivalence to Google's undisclosed cohort.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from decimal import Decimal
from pathlib import Path

from model_claim_replay.graphwalks_runtime import _usd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "website" / "graphwalks-audit.json"
SUMMARY = ROOT / "website" / "graphwalks-gemini-feasibility.json"
ORIGINAL = (ROOT / "evidence" / "graphwalks" /
            "gemini-4-neon-full-200-token-plan-2026-11-23.json")
EXPECTED_PLAN_SHA256 = "4d6d9167c14a4dd15dc50506c848259ec2d66a8c779232ca0234d1987da97a83"


class CompleteGeminiFeasibilityTests(unittest.TestCase):
    """Validate all source commitments and arithmetic with no provider calls."""

    def test_exact_original_plan_from_successful_live_run(self) -> None:
        original_bytes = ORIGINAL.read_bytes()
        self.assertEqual(len(original_bytes), 43496)
        self.assertEqual(hashlib.sha256(original_bytes).hexdigest(), EXPECTED_PLAN_SHA256)
        plan = json.loads(original_bytes)
        source = json.loads(SOURCE.read_bytes())
        summary = json.loads(SUMMARY.read_bytes())
        self.assertEqual(plan["model"], "gemini-4-neon")
        self.assertEqual(plan["schema_version"], "graphwalks-gemini-plan-v2")
        self.assertEqual(plan["evidence_level"],
                         "candidate_public_dataset_api_token_preflight_not_a_model_evaluation")
        self.assertEqual(plan["planned_count"], 200)
        self.assertEqual(plan["blocked_for_context"], 100)
        self.assertEqual(plan["comparison_status"], "not_comparable")
        self.assertEqual(plan["max_output_tokens"], 8192)
        self.assertEqual(plan["context_limit"], 1048576)
        self.assertEqual(plan["selection_counts"], {"short_context": 100, "long_context": 100})
        self.assertEqual(plan["index_sha256"], source["source"]["reference_index_sha256"])
        self.assertEqual(plan["parquet_sha256"], source["source"]["parquet_sha256_verified"])
        self.assertEqual(summary["original_token_plan_sha256"], EXPECTED_PLAN_SHA256)
        self.assertEqual(summary["source_parquet_sha256"], plan["parquet_sha256"])
        self.assertEqual(summary["reference_index_sha256"], plan["index_sha256"])
        self.assertEqual(summary["candidate_source_task_count"], 200)
        self.assertEqual(summary["fits_context_with_output_allowance"], 100)
        self.assertEqual(summary["exceeds_provider_input_limit"], 100)
        self.assertEqual(summary["provider_input_token_limit"], 1048576)
        self.assertEqual(summary["provider_output_token_limit"], 65536)
        self.assertEqual(summary["reserved_future_output_tokens"], 8192)
        self.assertEqual(summary["model_generation_performed"], False)
        self.assertEqual(summary["published_claim_reproduced"], False)
        self.assertEqual(len(source["tasks"]), len(plan["planned_tasks"]))
        self.assertEqual(len(summary["input_token_counts_in_pinned_index_order"]), 200)

        total = Decimal(0)
        for i, (reference, task, tokens) in enumerate(zip(
            source["tasks"], plan["planned_tasks"],
            summary["input_token_counts_in_pinned_index_order"], strict=True,
        )):
            with self.subTest(task=task["id"]):
                self.assertEqual(task["id"], reference["id"])
                self.assertEqual(task["prompt_sha256"], reference["prompt_sha256"])
                self.assertEqual(task["input_tokens"], tokens)
                self.assertIs(type(tokens), int)
                self.assertGreater(tokens, 0)
                fit = tokens + 8192 <= 1048576
                self.assertEqual(task["fits_context_with_output_allowance"], fit)
                self.assertEqual(fit, i < 100)
                cost = _usd(tokens, 8192)
                self.assertEqual(Decimal(task["maximum_reserved_cost_usd"]), cost)
                total += cost
        self.assertEqual(Decimal(plan["maximum_reserved_cost_usd"]), total)
        self.assertEqual(str(total), "556.982841")

    def test_featured_public_finding_matches_pinned_receipt(self) -> None:
        receipt = json.loads(SUMMARY.read_text())
        page = (ROOT / "website" / "index.html").read_text()
        feature = page.split('<article class="hero-plate evidence-plate"', 1)[1].split("</article>", 1)[0]
        exceeds = receipt["exceeds_provider_input_limit"]
        total = receipt["candidate_source_task_count"]
        self.assertIn(f"{exceeds} of {total} public candidate prompts exceed", feature)
        self.assertIn(f'{receipt["provider_input_token_limit"]:,} tokens', feature)
        self.assertIn(receipt["provider_run"], feature)
        self.assertIn('href="./graphwalks-gemini-feasibility.json"', feature)
        self.assertIn("No model generation", feature)
        self.assertIn("publisher-selected cohort is unverified", feature)
        self.assertFalse(receipt["model_generation_performed"])
        self.assertFalse(receipt["published_claim_reproduced"])

    def test_group_bounds_and_no_unredacted_benchmark_content(self) -> None:
        receipt = json.loads(SUMMARY.read_text())
        values = receipt["input_token_counts_in_pinned_index_order"]
        self.assertEqual((min(values[:100]), max(values[:100])), (354061, 355496))
        self.assertEqual((min(values[100:]), max(values[100:])), (1419001, 1420682))
        self.assertEqual(sum(values), 177468947)
        for path in (SUMMARY, ORIGINAL):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn('"answer_nodes"', text)
            self.assertNotIn('"output"', text)
            self.assertNotIn('"prompt":', text)
            self.assertNotIn("Final Answer:", text)


if __name__ == "__main__":
    unittest.main()
