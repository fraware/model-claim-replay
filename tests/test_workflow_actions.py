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
        self.assertEqual(len(files), 9)
        seen: set[str] = set()
        for file in files:
            text = file.read_text(encoding="utf-8")
            for name, version in USE.findall(text):
                with self.subTest(workflow=file.name, action=name):
                    self.assertIn(name, NODE24_VERSIONS)
                    self.assertEqual(version, NODE24_VERSIONS[name])
                    seen.add(name)
        self.assertEqual(seen, set(NODE24_VERSIONS))

    def test_paid_generation_remains_manual_after_action_upgrades(self) -> None:
        paid = (WORKFLOWS / "graphwalks-paid-pilot.yml").read_text()
        self.assertIn("workflow_dispatch:", paid)
        self.assertIn("AUTHORIZE_PAID_GEMINI", paid)
        self.assertNotIn("\n  push:", paid)
        self.assertNotIn("\n  schedule:", paid)
        self.assertNotIn("\n  pull_request:", paid)

    def test_provider_readiness_never_runs_with_secrets_in_pull_requests(self) -> None:
        readiness = (WORKFLOWS / "provider-readiness.yml").read_text()
        self.assertIn("branches:\n      - main", readiness)
        self.assertNotIn("pull_request:", readiness)
        self.assertNotIn("workflow_dispatch:", readiness)
        self.assertIn("scripts/provider_readiness.py", readiness)


if __name__ == "__main__":
    unittest.main()
