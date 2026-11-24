"""Exercise the one-time authorization using actual Git history."""
from __future__ import annotations
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_openai_first_generation import AUTH_PATH, EXPECTED, check


class FirstGenerationAuthorizationTests(unittest.TestCase):
    def test_guard_rejects_reruns_edits_and_reintroduction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.run(["git", *args], cwd=root, check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("init", "-q")
            git("config", "user.email", "fixture@example.invalid")
            git("config", "user.name", "Fixture")
            git("commit", "--allow-empty", "-qm", "initial")
            before = git("rev-parse", "HEAD")
            record = root / AUTH_PATH
            record.parent.mkdir(parents=True)
            record.write_bytes(EXPECTED)
            git("add", AUTH_PATH)
            git("commit", "-qm", "first authorization")
            head = git("rev-parse", "HEAD")
            check(root, before, head, "push", "refs/heads/main", "1")
            for event, ref, attempt in (("push", "refs/heads/main", "2"),
                                        ("pull_request", "refs/heads/main", "1"),
                                        ("push", "refs/heads/test", "1")):
                with self.assertRaises(ValueError):
                    check(root, before, head, event, ref, attempt)
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
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_bytes(EXPECTED)
            git("add", AUTH_PATH)
            git("commit", "-qm", "reintroduce")
            with self.assertRaises(ValueError):
                check(root, removed, git("rev-parse", "HEAD"), "push", "refs/heads/main", "1")

    def test_committed_authorization_and_workflow_scope(self):
        self.assertEqual((ROOT / AUTH_PATH).read_bytes(), EXPECTED)
        workflow = (ROOT / ".github/workflows/graphwalks-openai-first-generation.yml").read_text()
        self.assertIn("branches:\n      - main", workflow)
        self.assertIn("paths:\n      - '" + AUTH_PATH + "'", workflow)
        self.assertIn("group: openai-graphwalks-paid", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("--max-spend-usd 5 --publication PUBLISH_FINAL_LINE", workflow)
        self.assertLess(workflow.index("python scripts/check_openai_first_generation.py"),
                        workflow.index("secrets.OPENAI_API_KEY"))
        for forbidden in ("workflow_dispatch:", "pull_request:", "schedule:", "secrets.GEMINI_API_KEY"):
            self.assertNotIn(forbidden, workflow)
        upload = workflow.split("name: Retain explicitly authorized score evidence", 1)[1]
        self.assertNotIn("/private/", upload)
        self.assertNotIn("response.json", upload)


if __name__ == "__main__":
    unittest.main()
