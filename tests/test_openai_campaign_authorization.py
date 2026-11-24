"""Test the one-time campaign authorization in actual temporary Git history."""
from __future__ import annotations
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_openai_campaign_authorization import AUTH_PATH, EXPECTED, INPUTS, check


class CampaignAuthorizationTests(unittest.TestCase):
    def test_initial_introduction_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.run(["git", *args], cwd=root, check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("init", "-q")
            git("config", "user.email", "fixture@example.invalid")
            git("config", "user.name", "Fixture")
            fixtures = {}
            for rel in INPUTS:
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(rel.encode())
                fixtures[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
                git("add", rel)
            git("commit", "-qm", "pinned input fixtures")
            before = git("rev-parse", "HEAD")
            record = root / AUTH_PATH
            record.write_bytes(EXPECTED)
            git("add", AUTH_PATH)
            git("commit", "-qm", "first approval")
            head = git("rev-parse", "HEAD")
            with patch("check_openai_campaign_authorization.INPUTS", fixtures):
                check(root, before, head, "push", "refs/heads/main", "1")
                for event, ref, attempt in (("push", "refs/heads/main", "2"),
                                            ("pull_request", "refs/heads/main", "1"),
                                            ("push", "refs/heads/test", "1")):
                    with self.assertRaises(ValueError):
                        check(root, before, head, event, ref, attempt)
                p = root / next(iter(INPUTS))
                old = p.read_bytes()
                p.write_bytes(b"changed")
                with self.assertRaises(ValueError):
                    check(root, before, head, "push", "refs/heads/main", "1")
                p.write_bytes(old)
                record.write_bytes(EXPECTED + b" ")
                with self.assertRaises(ValueError):
                    check(root, before, head, "push", "refs/heads/main", "1")
                git("add", AUTH_PATH)
                git("commit", "-qm", "edit")
                edited = git("rev-parse", "HEAD")
                with self.assertRaises(ValueError):
                    check(root, head, edited, "push", "refs/heads/main", "1")
                git("rm", AUTH_PATH)
                git("commit", "-qm", "remove")
                removed = git("rev-parse", "HEAD")
                record.write_bytes(EXPECTED)
                git("add", AUTH_PATH)
                git("commit", "-qm", "reintroduce")
                with self.assertRaises(ValueError):
                    check(root, removed, git("rev-parse", "HEAD"), "push", "refs/heads/main", "1")

    def test_production_commitments_and_workflow(self):
        self.assertEqual((ROOT / AUTH_PATH).read_bytes(), EXPECTED)
        for rel, digest in INPUTS.items():
            self.assertEqual(hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), digest)
        workflow = (ROOT / ".github/workflows/graphwalks-openai-campaign-authorized.yml").read_text()
        self.assertIn("branches:\n      - main", workflow)
        self.assertIn("paths:\n      - '" + AUTH_PATH + "'", workflow)
        self.assertIn("group: openai-graphwalks-paid", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("--budget 25 --publication PUBLISH_FINAL_LINE", workflow)
        self.assertLess(workflow.index("python scripts/check_openai_campaign_authorization.py"),
                        workflow.index("secrets.OPENAI_API_KEY"))
        for forbidden in ("workflow_dispatch:", "pull_request:", "schedule:", "secrets.GEMINI_API_KEY"):
            self.assertNotIn(forbidden, workflow)
        upload = workflow.split("name: Retain public plan and outcome journal", 1)[1]
        self.assertNotIn("/private/", upload)
        self.assertNotIn("response.json", upload)
        manual = (ROOT / ".github/workflows/graphwalks-openai-campaign-paid.yml").read_text()
        self.assertIn("exit 1", manual)
        self.assertNotIn("secrets.", manual)
        self.assertNotIn("openai_graphwalks_campaign_paid.py", manual)


if __name__ == "__main__":
    unittest.main()
