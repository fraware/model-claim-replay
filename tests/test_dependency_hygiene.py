"""Regression checks for non-generative CI dependency maintenance."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DependencyHygieneTests(unittest.TestCase):
    def test_all_ordinary_checkouts_disable_credential_persistence(self):
        ci = (ROOT / ".github/workflows/ci.yml").read_text()
        for checkout in ci.split("uses: actions/checkout@v5")[1:]:
            self.assertIn("persist-credentials: false", checkout.split("\n      - ", 1)[0])

    def test_audit_is_separate_and_not_suppressed(self):
        ci = (ROOT / ".github/workflows/ci.yml").read_text()
        audit = ci.split("\n  dependency-audit:", 1)[1]
        self.assertIn("pip check", audit)
        self.assertIn("--strict --no-deps --disable-pip", audit)
        self.assertIn("--exclude model-claim-replay", audit)
        self.assertIn("advisories.json", audit)
        self.assertIn("resolved.txt", audit)
        for forbidden in ("secrets.", "--ignore-vuln", "continue-on-error", "|| true", "AUTHORIZE_PAID"):
            self.assertNotIn(forbidden, audit)
        self.assertEqual((ROOT / "requirements-audit.txt").read_text().strip(), "pip-audit==2.10.1")

    def test_local_secret_files_are_ignored(self):
        patterns = (ROOT / ".gitignore").read_text().splitlines()
        for pattern in (".env", ".env.*", "*.pem", "*.key", ".runs/"):
            self.assertIn(pattern, patterns)


if __name__ == "__main__":
    unittest.main()
