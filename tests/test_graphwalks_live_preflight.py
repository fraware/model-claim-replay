"""No-network tests for a source-pinned, non-generative Gemini preflight."""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from graphwalks_select_gemini_secret import main, select_gemini_secret  # noqa: E402
from provider_readiness import GEMINI_CLAIM_MODEL, ProviderProbeError  # noqa: E402


class GeminiSecretSelectionTests(unittest.TestCase):
    """Use synthetic credentials and fake metadata; no network calls."""

    def test_finds_valid_alternate_after_stale_primary_key(self) -> None:
        attempted: list[str] = []

        def fake(host, path, headers):
            self.assertEqual(host, "generativelanguage.googleapis.com")
            self.assertEqual(path, "/v1beta/models/" + GEMINI_CLAIM_MODEL)
            attempted.append(headers["x-goog-api-key"])
            if len(attempted) == 1:
                return 401, None
            return 200, {"name": "models/" + GEMINI_CLAIM_MODEL}

        choice = select_gemini_secret(
            {
                "GEMINI_API_KEY": "fixture-stale-gemini-credential",
                "GOOGLE_API_KEY": "fixture-valid-alternate-credential",
            }, request=fake,
        )
        self.assertEqual(choice, ("GOOGLE_API_KEY", "fixture-valid-alternate-credential"))
        self.assertEqual(len(attempted), 2)

    def test_duplicate_alias_values_are_checked_once(self) -> None:
        calls = []
        def fake(host, path, headers):
            calls.append(headers["x-goog-api-key"])
            raise ProviderProbeError("network unavailable")
        self.assertIsNone(select_gemini_secret({
            "GEMINI_API_KEY": "same-token",
            "GOOGLE_API_KEY": "same-token",
            "GOOGLE_GENAI_API_KEY": "other-token",
        }, request=fake))
        self.assertEqual(calls, ["same-token", "other-token"])

    def test_missing_invalid_or_mismatched_credentials_are_rejected(self) -> None:
        self.assertIsNone(select_gemini_secret({}, request=lambda *_: self.fail("network")))
        self.assertIsNone(select_gemini_secret(
            {"GEMINI_API_KEY": "multiline\ninjection"},
            request=lambda *_: self.fail("Invalid key sent"),
        ))
        self.assertIsNone(select_gemini_secret(
            {"GEMINI_API_KEY": "test-secret"},
            request=lambda *_: (200, {"name": "models/a-different-model"}),
        ))

    def test_secret_enters_ephemeral_environment_file_without_logging(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "github-env"
            target.touch()
            transcript = io.StringIO()
            with patch.dict(os.environ, {"GITHUB_ENV": str(target)}, clear=True):
                with patch(
                    "graphwalks_select_gemini_secret.select_gemini_secret",
                    return_value=("GOOGLE_API_KEY", "fixture-private-key-1234567890"),
                ):
                    with redirect_stdout(transcript):
                        self.assertEqual(main(), 0)
            self.assertEqual(target.read_text(), "GEMINI_API_KEY=fixture-private-key-1234567890\n")
            self.assertNotIn("fixture-private-key-1234567890", transcript.getvalue())
            self.assertIn("GOOGLE_API_KEY", transcript.getvalue())

    def test_missing_github_env_fails_before_key_selection(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "graphwalks_select_gemini_secret.select_gemini_secret",
                side_effect=AssertionError("unexpected key access"),
            ):
                self.assertEqual(main(), 2)

    def test_one_time_source_workflow_is_safe_and_pinned(self) -> None:
        workflow = (ROOT / ".github/workflows/graphwalks-live-token-count.yml").read_text()
        self.assertIn("    branches:\n      - main", workflow)
        self.assertIn("      - '.github/workflows/graphwalks-live-token-count.yml'", workflow)
        self.assertNotIn("  pull_request:", workflow)
        self.assertNotIn("  schedule:", workflow)
        self.assertNotIn("  workflow_dispatch:", workflow)
        self.assertIn("--max-tasks 20 --max-output-tokens 8192", workflow)
        self.assertIn("scripts/graphwalks_model_capabilities.py", workflow)
        # The source audit explicitly refuses any preexisting output directory.
        # The independent metadata receipt must not create that directory first.
        self.assertIn(
            "--out .runs/private/graphwalks-model-capabilities.json", workflow,
        )
        self.assertNotIn(
            "--out .runs/private/graphwalks-live/model-capabilities.json", workflow,
        )
        self.assertIn("scripts/graphwalks_select_gemini_secret.py", workflow)
        self.assertNotIn("--execute-paid", workflow)
        self.assertNotIn("execute-graphwalks", workflow)
        self.assertNotIn("generate-graphwalks", workflow)
        allowed = workflow.split("name: Upload strictly redacted token-count evidence", 1)[1]
        self.assertIn("token-plan.json", allowed)
        self.assertIn("model-capabilities.json", allowed)
        for forbidden in ("bfs-reference-index.jsonl", "graphwalks_256k_to_1mil.parquet",
                          "pilot-responses.jsonl", "pilot-run"):
            self.assertNotIn(forbidden, allowed)


if __name__ == "__main__":
    unittest.main()
