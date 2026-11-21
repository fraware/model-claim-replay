"""End-to-end checks of the installable, offline first-run experience."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from importlib import resources
from pathlib import Path
from unittest.mock import patch

from model_claim_replay.cli import main
from model_claim_replay.core import ReplayError, verify_bundle
from model_claim_replay.demo import generate_offline_demo

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "claim.json": ROOT / "claims/demo-text-exact-match.json",
    "tasks.jsonl": ROOT / "examples/demo-tasks.jsonl",
    "responses.jsonl": ROOT / "examples/demo-responses.jsonl",
}


class InstalledDemoTests(unittest.TestCase):
    """Exercise the same interface a new developer runs after installation."""

    def test_packaged_fixtures_match_versioned_repository_examples(self) -> None:
        package = resources.files("model_claim_replay")
        for name, original in SOURCES.items():
            with self.subTest(name=name):
                self.assertEqual(
                    package.joinpath("demo_assets", name).read_bytes(),
                    original.read_bytes(),
                )

    def test_complete_report_and_repeatability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "first-run"
            self.assertEqual(main(["demo", "--out", str(dest)]), 0)
            self.assertEqual(
                {p.name for p in dest.iterdir()},
                {"claim.json", "tasks.jsonl", "responses.jsonl",
                 "run", "report.json", "report.html", "README.md"},
            )
            summary = verify_bundle(
                dest / "claim.json", dest / "tasks.jsonl", dest / "run",
            )
            self.assertEqual(summary["successes"], 2)
            self.assertEqual(summary["assessed"], 3)
            self.assertEqual(summary["kind"], "synthetic")
            self.assertEqual(summary["run_kind"], "imported")
            self.assertEqual(summary["comparison_status"], "not_comparable")
            self.assertEqual(json.loads(json.dumps(summary)),
                             json.loads((dest / "report.json").read_text()))
            page = (dest / "report.html").read_text()
            self.assertIn("66.7%", page)
            self.assertIn("synthetic", page.lower())
            self.assertIn("self-reported", page)
            self.assertNotIn("<script src=", page)
            old = {str(p.relative_to(dest)): p.read_bytes()
                   for p in dest.rglob("*") if p.is_file()}
            self.assertEqual(main(["demo", "--out", str(dest)]), 2)
            self.assertEqual(
                old,
                {str(p.relative_to(dest)): p.read_bytes()
                 for p in dest.rglob("*") if p.is_file()},
            )

    def test_existing_file_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "preexisting"
            dest.write_text("IMPORTANT")
            with self.assertRaisesRegex(ReplayError, "already exists"):
                generate_offline_demo(dest)
            self.assertEqual(dest.read_text(), "IMPORTANT")

    def test_invalid_fixture_never_publishes_partial_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_assets = Path(tmp) / "demo_assets"
            fake_assets.mkdir()
            for name, original in SOURCES.items():
                (fake_assets / name).write_bytes(original.read_bytes())
            with (fake_assets / "tasks.jsonl").open("ab") as file:
                file.write(b"\n")
            dest = Path(tmp) / "output"
            with patch("model_claim_replay.demo.resources.files",
                       return_value=Path(tmp)):
                with self.assertRaisesRegex(ReplayError, "SHA-256"):
                    generate_offline_demo(dest)
            self.assertFalse(dest.exists())

    def test_cli_executes_from_unrelated_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            unrelated = Path(tmp) / "other-cwd"
            unrelated.mkdir()
            process = subprocess.run(
                [sys.executable, "-m", "model_claim_replay.cli", "demo",
                 "--out", "example"],
                cwd=unrelated, capture_output=True, text=True, timeout=30,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertTrue((unrelated / "example/report.html").is_file())
            self.assertIn("No model API calls", process.stdout)


if __name__ == "__main__":
    unittest.main()
