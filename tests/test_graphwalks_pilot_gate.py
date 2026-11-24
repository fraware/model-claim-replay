"""Offline spending-gate and workflow security contract tests.

No provider credentials, HTTP requests, or paid generation are used.
"""

from __future__ import annotations

import os
import shutil
import subprocess
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

    def test_paid_rerun_guard_precedes_checkout_and_credentials(self) -> None:
        workflow = (ROOT / ".github/workflows/graphwalks-paid-pilot.yml").read_text()
        guard = "Refuse reuse of paid authorization on a rerun"
        self.assertLess(workflow.index(guard), workflow.index("actions/checkout@"))
        self.assertLess(workflow.index(guard), workflow.index("secrets.GEMINI_API_KEY"))
        self.assertIn('"${GITHUB_RUN_ATTEMPT:-}" != "1"', workflow)
        self.assertIn("!cancelled() && github.run_attempt == 1", workflow)

    @unittest.skipUnless(shutil.which("bash"), "Bash is needed to exercise Actions guard")
    def test_paid_rerun_guard_rejects_reused_or_missing_attempt(self) -> None:
        workflow = (ROOT / ".github/workflows/graphwalks-paid-pilot.yml").read_text()
        guard = workflow.split("Refuse reuse of paid authorization on a rerun", 1)[1]
        body = guard.split("        run: |\n", 1)[1].split("      - uses:", 1)[0]
        script = "\n".join(line[10:] for line in body.splitlines())
        for attempt in (None, "", "0", "1", "2", "3", "01", "invalid"):
            with self.subTest(attempt=attempt):
                env = dict(os.environ)
                env.pop("GITHUB_RUN_ATTEMPT", None)
                if attempt is not None:
                    env["GITHUB_RUN_ATTEMPT"] = attempt
                result = subprocess.run(
                    ["bash", "-c", script], env=env, capture_output=True,
                    text=True, check=False, timeout=5,
                )
                self.assertEqual(result.returncode, 0 if attempt == "1" else 1)

    def test_interrupted_paid_step_preserves_audit_and_limits_output(self) -> None:
        workflow = (ROOT / ".github/workflows/graphwalks-paid-pilot.yml").read_text()
        self.assertIn('          - "65536"', workflow)
        self.assertIn('default: "16384"', workflow)
        self.assertIn("    timeout-minutes: 360", workflow)
        self.assertIn("        id: paid_execution", workflow)
        self.assertIn("        timeout-minutes: 330", workflow)
        self.assertIn("        id: private_audit", workflow)
        self.assertIn(
            "if: ${{ !cancelled() && steps.paid_execution.outcome != 'skipped' }}",
            workflow,
        )
        self.assertIn(
            "steps.private_audit.outcome == 'success'", workflow,
        )
        self.assertLess(
            workflow.index("id: paid_execution"), workflow.index("id: private_audit"),
        )
        self.assertLess(
            workflow.index("id: private_audit"),
            workflow.index("Upload only score-free plan"),
        )
        self.assertIn("if: ${{ !cancelled() && github.run_attempt == 1 }}", workflow)

    def test_manual_workflows_scope_the_same_authenticated_key(self) -> None:
        paid = (ROOT / ".github/workflows/graphwalks-paid-pilot.yml").read_text()
        preflight = (ROOT / ".github/workflows/graphwalks-token-preflight.yml").read_text()
        selector = "scripts/graphwalks_select_gemini_secret.py --alias-only"
        self.assertLess(paid.index('--approval "$APPROVAL"'), paid.index(selector))
        for workflow, expected_uses, download in (
            (paid, 2, "Independently download and verify"),
            (preflight, 1, "Verify complete public source"),
        ):
            self.assertLess(workflow.index(selector), workflow.index(download))
            self.assertEqual(workflow.count("id: gemini_credential"), 1)
            self.assertNotIn("secrets.OPENAI", workflow)
            self.assertNotIn("GITHUB_ENV", workflow)
            for alias in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY"):
                self.assertEqual(workflow.count("secrets." + alias), 1 + expected_uses)
                self.assertEqual(
                    workflow.count("steps.gemini_credential.outputs.alias == '" + alias + "'"),
                    expected_uses,
                )
            self.assertEqual(
                workflow.count("GEMINI_API_KEY: ${{ (steps.gemini_credential.outputs.alias"),
                expected_uses,
            )

    def test_non_generating_preflight_covers_paid_pilot_settings(self) -> None:
        """Avoid UI/runner drift at the exact pilot cohort and output limit."""
        preflight = (ROOT / ".github/workflows/graphwalks-token-preflight.yml").read_text()
        paid = (ROOT / ".github/workflows/graphwalks-paid-pilot.yml").read_text()
        self.assertIn('default: "1"', preflight)
        self.assertIn('default: "1"', paid)
        self.assertIn('          - "2"', preflight)
        self.assertIn('          - "65536"', preflight)
        self.assertIn('          - "65536"', paid)
        self.assertIn('          - "16384"', preflight)
        self.assertIn('          - "16384"', paid)
        self.assertIn("retention-days: 90", preflight)
        self.assertIn("workflow_dispatch:", preflight)
        self.assertNotIn("--execute-paid", preflight)
        for forbidden in ("\n  push:", "\n  pull_request:", "\n  schedule:"):
            self.assertNotIn(forbidden, preflight)

    def test_public_artifact_allowlist_excludes_private_source_and_raw_responses(self) -> None:
        workflow = (ROOT / ".github/workflows/graphwalks-paid-pilot.yml").read_text()
        artifact = workflow.split("- name: Upload only score-free plan, redacted audit and verified task-level grades", 1)[1]
        self.assertIn("path: |", artifact)
        for filename in ("token-plan.json", "pilot-audit.json", "pilot-scores.json", "pilot-public-verification.json", "pilot-public-report.html"):
            self.assertIn(filename, artifact)
        for private_name in ("pilot-responses.jsonl", "graphwalks_256k_to_1mil.parquet", "pilot-run", "bfs-reference-index.jsonl", "pilot-scores-pending.json"):
            self.assertNotIn(private_name, artifact)
        self.assertIn("retention-days: 90", artifact)
        self.assertIn("claim-replay report-graphwalks-public", workflow)
        self.assertLess(
            workflow.index("verify-graphwalks-public"),
            workflow.index("report-graphwalks-public"),
        )
        self.assertLess(
            workflow.index("report-graphwalks-public"),
            workflow.index("mv .runs/private/pilot-scores-pending.json"),
        )


if __name__ == "__main__":
    unittest.main()
