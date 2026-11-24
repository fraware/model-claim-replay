"""Repository-wide regression test for Node.js 24 GitHub Actions versions."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
NODE24_VERSIONS = {
    "checkout": "v5",
    "setup-python": "v6",
    "upload-artifact": "v6",
    "configure-pages": "v6",
    "upload-pages-artifact": "v5",
    "deploy-pages": "v5",
}
USE = re.compile(r"^\s*-?\s*uses:\s*actions/([a-z-]+)@([^\s#]+)", re.MULTILINE)


class WorkflowRuntimeTests(unittest.TestCase):
    """Keep automation on known supported Node 24 action release tracks."""

    def test_every_referenced_first_party_action_uses_node24_release(self) -> None:
        files = sorted(WORKFLOWS.glob("*.yml"))
        self.assertTrue(files, "No workflow files found")
        seen: set[str] = set()
        for file in files:
            text = file.read_text(encoding="utf-8")
            for name, version in USE.findall(text):
                with self.subTest(workflow=file.name, action=name):
                    self.assertIn(name, NODE24_VERSIONS)
                    self.assertEqual(version, NODE24_VERSIONS[name])
                    seen.add(name)
        self.assertEqual(seen, set(NODE24_VERSIONS))

    def test_superseded_test_runs_are_cancelled_by_branch_or_pr(self) -> None:
        workflow = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("concurrency:\n", workflow)
        self.assertIn(
            "group: tests-${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}",
            workflow,
        )
        self.assertIn("  cancel-in-progress: true\n", workflow)
        self.assertIn("  push:\n", workflow)
        self.assertIn("  pull_request:\n", workflow)
        # The billing and source audit jobs never inherit this workflow-local
        # cancellation policy; interrupts there could leave unknown charges.
        paid = (WORKFLOWS / "graphwalks-paid-pilot.yml").read_text()
        self.assertNotIn("cancel-in-progress: true", paid)

    def test_paid_generation_remains_manual_after_action_upgrades(self) -> None:
        for filename, approval in (
            ("graphwalks-paid-pilot.yml", "AUTHORIZE_PAID_GEMINI"),
            ("graphwalks-openai-paid.yml", "AUTHORIZE_PAID_OPENAI"),
        ):
            with self.subTest(workflow=filename):
                paid = (WORKFLOWS / filename).read_text()
                self.assertIn("workflow_dispatch:", paid)
                self.assertIn(approval, paid)
                self.assertNotIn("\n  push:", paid)
                self.assertNotIn("\n  schedule:", paid)
                self.assertNotIn("\n  pull_request:", paid)
                self.assertNotIn("cancel-in-progress: true", paid)

    def test_openai_default_dispatch_is_preflight_only(self) -> None:
        paid = (WORKFLOWS / "graphwalks-openai-paid.yml").read_text()
        self.assertIn('default: "PREFLIGHT_ONLY"', paid)
        self.assertIn("type: choice", paid)
        self.assertIn("- AUTHORIZE_PAID_OPENAI", paid)
        self.assertIn('default: "5"', paid)
        self.assertIn("dispatch_mode(", paid)
        self.assertIn("include-hidden-files: true", paid)
        upload = paid.split("name: Retain redacted evidence only", 1)[1]
        for name in ("plan.json", "intent.json", "outcome.json"):
            self.assertIn(".runs/openai-diagnostic/public/" + name, upload)
        self.assertNotIn("/private/", upload)
        self.assertNotIn("response.json", upload)

    def test_provider_readiness_never_runs_with_secrets_in_pull_requests(self) -> None:
        readiness = (WORKFLOWS / "provider-readiness.yml").read_text()
        self.assertIn("branches:\n      - main", readiness)
        self.assertNotIn("pull_request:", readiness)
        self.assertNotIn("workflow_dispatch:", readiness)
        self.assertIn("scripts/provider_readiness.py", readiness)
        self.assertNotIn("secrets.GEMINI_API_KEY", readiness)
        self.assertNotIn("secrets.GOOGLE_API_KEY", readiness)
        self.assertNotIn("secrets.GOOGLE_GENAI_API_KEY", readiness)
        self.assertIn("secrets.OPENAI_API_KEY", readiness)


if __name__ == "__main__":
    unittest.main()
