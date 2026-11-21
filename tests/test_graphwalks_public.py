"""Adversarial tests for the redacted, provider-independent receipt verifier."""

from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from model_claim_replay.cli import main
from model_claim_replay.core import ReplayError, sha256_bytes
from model_claim_replay.graphwalks_public import verify_public_graphwalks_receipts
from model_claim_replay.graphwalks_runtime import (
    CONTEXT_LIMIT, DATASET_REVISION, DATASET_SHA256, INDEX_SHA256,
    INPUT_USD_PER_M, MODEL, OUTPUT_USD_PER_M, PRICE_SOURCE, SCHEMA, SELECTION_POLICY,
)


def _cost(tokens: int, output: int) -> str:
    return str((Decimal(tokens) * INPUT_USD_PER_M
                + Decimal(output) * OUTPUT_USD_PER_M) / Decimal(1_000_000))


class PublicReceiptVerificationTests(unittest.TestCase):
    """Build synthetic receipts; no benchmark data, credentials or API use."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.paths = [root / name for name in ("plan.json", "audit.json", "grades.json")]
        self.report_path = root / "verified.json"
        first, second = "bfs-row-000001", "bfs-row-000150"
        tasks = [
            {"id": first, "prompt_sha256": "a" * 64, "input_tokens": 200,
             "fits_context_with_output_allowance": True,
             "maximum_reserved_cost_usd": _cost(200, 128)},
            {"id": second, "prompt_sha256": "b" * 64, "input_tokens": 800,
             "fits_context_with_output_allowance": True,
             "maximum_reserved_cost_usd": _cost(800, 128)},
        ]
        self.plan = {
            "schema_version": SCHEMA, "model": MODEL,
            "evidence_level": "candidate_public_dataset_api_token_preflight_not_a_model_evaluation",
            "thinking_level": "xhigh", "created_utc": "2026-11-21T16:00:00+00:00",
            "limitations": ["Synthetic source-bound token preflight only."],
            "pricing": {"input_usd_per_m": str(INPUT_USD_PER_M),
                        "output_usd_per_m": str(OUTPUT_USD_PER_M),
                        "as_of": "2026-11-20", "source": PRICE_SOURCE,
                        "tier": "standard", "currency": "USD"},
            "dataset_revision": DATASET_REVISION,
            "parquet_sha256": DATASET_SHA256, "index_sha256": INDEX_SHA256,
            "selection_policy": SELECTION_POLICY, "context_limit": CONTEXT_LIMIT,
            "reference_task_count": 200, "planned_tasks": tasks, "planned_count": 2,
            "selection_counts": {"short_context": 1, "long_context": 1},
            "max_output_tokens": 128, "blocked_for_context": 0,
            "maximum_reserved_cost_usd": str(sum(
                (Decimal(x["maximum_reserved_cost_usd"]) for x in tasks), Decimal(0))),
            "comparison_status": "not_comparable",
        }
        self.audit = {
            "schema_version": "graphwalks-private-journal-audit-v1",
            "evidence_level": "self_reported_local_journal_consistency_only",
            "plan_sha256": "", "index_sha256": INDEX_SHA256,
            "source_parquet_sha256": DATASET_SHA256, "model_declared": MODEL,
            "run_manifest_sha256": "c" * 64,
            "comparison_status": "not_comparable",
            "execution_authenticated": False,
            "planned": 2, "attempted": 2, "completed": 1,
            "failed": 1, "unresolved": 0, "not_attempted": 0,
            "responses_missing_usage": 1,
            "budget_reserved_usd": self.plan["maximum_reserved_cost_usd"],
            "entries": [
                {"id": first, "status": "completed",
                 "intent_sha256": "d" * 64, "result_sha256": "e" * 64},
                {"id": second, "status": "error",
                 "intent_sha256": "f" * 64, "result_sha256": "0" * 64},
            ],
        }
        rows = [{"id": f"bfs-row-{i:06d}", "status": "missing"}
                for i in range(200)]
        rows[1] = {
            "id": first, "status": "graded", "f1": 0.5,
            "precision": 0.5, "recall": 0.5,
            "parse_failed": False, "predicted_nodes": 2, "reference_nodes": 2,
        }
        rows[150] = {"id": second, "status": "error"}
        self.grades = {
            "schema_version": "graphwalks-offline-grade-v1",
            "evidence_level": "locally_imported_response_scores_unattested",
            "dataset_revision_user_declared": DATASET_REVISION,
            "reference_index_sha256": INDEX_SHA256,
            "response_file_sha256": "1" * 64,
            "comparison_status": "not_comparable", "results": rows,
            "comparison_explanation": "Only local scoring; provider not authenticated.",
            "task_count": 200, "graded": 1, "parsed": 1,
            "malformed": 0, "api_errors": 1, "missing": 198,
            "scored_subset_mean_f1_diagnostic": 0.5, "mean_f1": None,
        }
        self.write()

    def write(self) -> None:
        self.paths[0].write_text(json.dumps(self.plan, sort_keys=True) + "\n")
        self.audit["plan_sha256"] = sha256_bytes(self.paths[0].read_bytes())
        self.paths[1].write_text(json.dumps(self.audit, sort_keys=True) + "\n")
        self.paths[2].write_text(json.dumps(self.grades, sort_keys=True) + "\n")

    def verify(self) -> dict:
        return verify_public_graphwalks_receipts(*self.paths)

    def test_valid_partial_receipt_and_cli(self) -> None:
        result = self.verify()
        self.assertEqual(result["completed"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["graded"], 1)
        self.assertFalse(result["provider_execution_authenticated"])
        self.assertFalse(result["score_recomputed_from_model_outputs"])
        self.assertEqual(result["verification_status"],
                         "internally_consistent_self_reported_only")
        self.assertEqual(main([
            "verify-graphwalks-public", "--plan", str(self.paths[0]),
            "--audit", str(self.paths[1]), "--grades", str(self.paths[2]),
            "--out", str(self.report_path),
        ]), 0)
        self.assertEqual(json.loads(self.report_path.read_text())["graded"], 1)

    def test_changed_plan_is_rejected_even_when_counts_still_agree(self) -> None:
        self.plan["created_utc"] = "2026-11-21T16:00:01+00:00"
        self.paths[0].write_text(json.dumps(self.plan))
        with self.assertRaisesRegex(ReplayError, "does not bind"):
            self.verify()

    def test_false_success_and_missing_task_scores_are_rejected(self) -> None:
        self.grades["results"][150] = {
            **self.grades["results"][1], "id": "bfs-row-000150",
        }
        self.write()
        with self.assertRaisesRegex(ReplayError, "scored status"):
            self.verify()

    def test_tampered_score_arithmetic_is_rejected(self) -> None:
        self.grades["results"][1]["f1"] = 0.9
        self.grades["scored_subset_mean_f1_diagnostic"] = 0.9
        self.write()
        with self.assertRaisesRegex(ReplayError, "inconsistent F1"):
            self.verify()

    def test_coverage_and_budget_fabrication_is_rejected(self) -> None:
        self.audit["budget_reserved_usd"] = "0"
        self.write()
        with self.assertRaisesRegex(ReplayError, "reservation differs"):
            self.verify()
        self.audit["budget_reserved_usd"] = self.plan["maximum_reserved_cost_usd"]
        self.grades["mean_f1"] = 0.5
        self.write()
        with self.assertRaisesRegex(ReplayError, "partial cohort"):
            self.verify()

    def test_duplicate_and_unplanned_task_are_rejected(self) -> None:
        self.grades["results"][2]["id"] = "bfs-row-000001"
        self.write()
        with self.assertRaisesRegex(ReplayError, "duplicate scored"):
            self.verify()
        self.grades["results"][2]["id"] = "bfs-row-000002"
        self.grades["results"][2]["status"] = "graded"
        self.write()
        with self.assertRaisesRegex(ReplayError, "scored status"):
            self.verify()

    def test_nonfinite_and_unattested_statuses_are_rejected(self) -> None:
        self.grades["results"][1]["f1"] = float("nan")
        self.write()
        with self.assertRaisesRegex(ReplayError, "invalid f1"):
            self.verify()
        self.grades["results"][1]["f1"] = 0.5
        self.audit["execution_authenticated"] = True
        self.write()
        with self.assertRaisesRegex(ReplayError, "authentication"):
            self.verify()

    def test_unredacted_public_artifacts_are_rejected(self) -> None:
        self.plan["planned_tasks"][0]["prompt"] = "must stay private"
        self.write()
        with self.assertRaisesRegex(ReplayError, "unredacted"):
            self.verify()
        del self.plan["planned_tasks"][0]["prompt"]
        self.grades["results"][1]["output"] = "raw response"
        self.write()
        with self.assertRaisesRegex(ReplayError, "unexpected fields"):
            self.verify()

    def test_impossible_node_overlap_is_rejected(self) -> None:
        self.grades["results"][1]["precision"] = 0.3
        self.grades["results"][1]["recall"] = 0.3
        self.grades["results"][1]["f1"] = 0.3
        self.grades["scored_subset_mean_f1_diagnostic"] = 0.3
        self.write()
        with self.assertRaisesRegex(ReplayError, "impossible node overlap"):
            self.verify()

    def test_unresolved_request_must_remain_unscored(self) -> None:
        self.audit["entries"][1] = {
            "id": "bfs-row-000150", "status": "unresolved", "intent_sha256": "f" * 64,
        }
        self.audit.update(failed=0, unresolved=1, responses_missing_usage=0)
        self.grades["results"][150] = {"id": "bfs-row-000150", "status": "missing"}
        self.grades.update(api_errors=0, missing=199)
        self.write()
        self.assertEqual(self.verify()["unresolved"], 1)


if __name__ == "__main__":
    unittest.main()
