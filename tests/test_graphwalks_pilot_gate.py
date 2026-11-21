"""Offline spending-gate and workflow security contract tests.

No provider credentials, HTTP requests, or paid generation are used.
"""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

from model_claim_replay.core import ReplayError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from graphwalks_pilot_gate import (  # noqa: E402
    APPROVAL_PHRASE,
    MAX_PILOT_USD,
    validate_authorization,
    validate_pilot_plan,
)


class GraphWalksPilotGateTests(unittest.TestCase):
    def test_explicit_authorization_is_exact(self) -> None:
        self.assertEqual(validate_authorization(APPROVAL_PHRASE, "2.50"), Decimal("2.50"))
        for invalid in ("NO", "yes", "", " AUTHORIZE_PAID_GEMINI ", "AUTHORIZE_PAID_GEMINI\n"):
            with self.subTest(value=invalid), self.assertRaisesRegex(ReplayError, "authorization phrase"):
                validate_authorization(invalid, "5")

    def test_nonfinite_negative_or_over_cap_budgets_are_rejected(self) -> None:
        for invalid in ("", "nan", "NaN", "Infinity", "-Infinity", "-1", "0", "100.01", "1e9999", "hello"):
            with self.subTest(value=invalid), self.assertRaises(ReplayError):
                validate_authorization(APPROVAL_PHRASE, invalid)
        self.assertEqual(validate_authorization(APPROVAL_PHRASE, "100"), MAX_PILOT_USD)
        self.assertEqual(validate_authorization(APPROVAL_PHRASE, "0.01"), Decimal("0.01"))

    def test_complete_token_plan_must_fit_authorized_ceiling(self) -> None:
        plan = {
            "planned_count": 2,
            "planned_tasks": [{"id": "short"}, {"id": "long"}],
            "blocked_for_context": 0,
            "maximum_reserved_cost_usd": "4.500000",
        }
        self.assertEqual(validate_pilot_plan(plan, budget=Decimal("5"), tasks=2), Decimal("4.500000"))
        with self.assertRaisesRegex(ReplayError, "exceeds authorized"):
            validate_pilot_plan(plan, budget=Decimal("4.49"), tasks=2)
        with self.assertRaisesRegex(ReplayError, "requested diagnostic"):
            validate_pilot_plan(plan, budget=Decimal("5"), tasks=5)
        with self.assertRaisesRegex(ReplayError, "context"):
            validate_pilot_plan({**plan, "blocked_for_context": 1}, budget=Decimal("5"), tasks=2)
        for invalid in ("-1", "0", "NaN", "Infinity", "bad"):
            with self.subTest(value=invalid), self.assertRaises(ReplayError):
                validate_pilot_plan({**plan, "maximum_reserved_cost_usd": invalid}, budget=Decimal("5"), tasks=2)
        for invalid in (0, 3, 200, True):
            with self.subTest(tasks=invalid), self.assertRaises(ReplayError):
                validate_pilot_plan(plan, budget=Decimal("5"), tasks=invalid)

    def test_workflow_has_only_explicit_manual_trigger(self) -> None:
        workflow = (ROOT / ".github/workflows/graphwalks-paid-pilot.yml").read_text()
        self.assertIn("  workflow_dispatch:\n", workflow)
        for forbidden in ("\n  push:", "\n  pull_request:", "\n  schedule:", "\n  repository_dispatch:"):
            self.assertNotIn(forbidden, workflow)
        self.assertIn('default: "NO"', workflow)
        self.assertIn('default: "0"', workflow)
        self.assertIn("--execute-paid", workflow)
        self.assertIn("--approval \"$APPROVAL\"", workflow)
        self.assertIn("--max-spend-usd \"$MAX_SPEND_USD\"", workflow)
        self.assertIn("GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}", workflow)
        self.assertNotIn("--api-key ", workflow)
        # User-controlled strings are passed via environment, not inserted
        # into bash source where they could change shell behavior.
        self.assertNotIn("\"${{ inputs.max_spend_usd }}\"", workflow)
        self.assertNotIn("\"${{ inputs.approval }}\"", workflow)
        self.assertLess(workflow.index("Refuse unauthorized, unbounded"),
                        workflow.index("Independently download and verify"))
        self.assertLess(workflow.index("Refuse partial-coverage"),
                        workflow.index("Perform explicitly authorized"))

    def test_public_artifact_allowlist_excludes_private_source_and_raw_responses(self) -> None:
        workflow = (ROOT / ".github/workflows/graphwalks-paid-pilot.yml").read_text()
        artifact = workflow.split("- name: Upload only score-free plan, redacted audit and task-level grades", 1)[1]
        self.assertIn("path: |", artifact)
        for filename in ("token-plan.json", "pilot-audit.json", "pilot-scores.json"):
            self.assertIn(filename, artifact)
        for private_name in ("pilot-responses.jsonl", "graphwalks_256k_to_1mil.parquet", "pilot-run", "bfs-reference-index.jsonl"):
            self.assertNotIn(private_name, artifact)
        self.assertIn("retention-days: 7", artifact)


if __name__ == "__main__":
    unittest.main()
