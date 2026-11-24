"""No-network contract tests for provider model-capability evidence."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from graphwalks_model_capabilities import main, read_model_capabilities  # noqa: E402
from graphwalks_gemini_metadata import GEMINI_CLAIM_MODEL, ProviderProbeError  # noqa: E402


class ProviderCapabilityEvidenceTests(unittest.TestCase):
    """Never send model prompts, provider requests or secret values to network."""

    def test_exact_model_metadata_limits_are_extracted_only_from_allowlist(self) -> None:
        def request(host, path, headers):
            self.assertEqual(host, "generativelanguage.googleapis.com")
            self.assertEqual(path, "/v1beta/models/" + GEMINI_CLAIM_MODEL)
            self.assertEqual(headers["x-goog-api-key"], "synthetic-private-secret")
            return 200, {
                "name": "models/" + GEMINI_CLAIM_MODEL,
                "inputTokenLimit": 1_048_576,
                "outputTokenLimit": 65_536,
                "untrusted": "synthetic-private-secret",
                "description": "untrusted provider-provided text",
            }

        result = read_model_capabilities(
            "synthetic-private-secret", request=request,
        )
        self.assertEqual(result["metadata_status"], "model_metadata_available")
        self.assertEqual(result["provider_input_token_limit"], 1_048_576)
        self.assertEqual(result["provider_output_token_limit"], 65_536)
        self.assertTrue(result["declared_input_limit_matches_provider"])
        self.assertTrue(result["declared_output_limit_within_provider"])
        self.assertFalse(result["generation_performed"])
        self.assertNotIn("synthetic-private-secret", json.dumps(result))
        self.assertNotIn("untrusted provider-provided text", json.dumps(result))

    def test_mismatched_limits_are_reported_without_reinterpretation(self) -> None:
        result = read_model_capabilities(
            "key",
            request=lambda *_: (200, {
                "name": "models/" + GEMINI_CLAIM_MODEL,
                "inputTokenLimit": 512_000,
                "outputTokenLimit": 8_192,
            }),
        )
        self.assertEqual(result["provider_input_token_limit"], 512_000)
        self.assertEqual(result["provider_output_token_limit"], 8_192)
        self.assertFalse(result["declared_input_limit_matches_provider"])
        self.assertFalse(result["declared_output_limit_within_provider"])

    def test_missing_or_invalid_limit_never_claims_verified_limit(self) -> None:
        invalid = (True, -1, 0, "1048576", None)
        for value in invalid:
            with self.subTest(value=value):
                result = read_model_capabilities(
                    "key", request=lambda *_: (200, {
                        "name": "models/" + GEMINI_CLAIM_MODEL,
                        "inputTokenLimit": value,
                        "outputTokenLimit": value,
                    }),
                )
                self.assertIsNone(result["provider_input_token_limit"])
                self.assertIsNone(result["provider_output_token_limit"])
                self.assertIsNone(result["declared_input_limit_matches_provider"])
                self.assertIsNone(result["declared_output_limit_within_provider"])

    def test_transport_or_model_identity_failure_cannot_claim_capabilities(self) -> None:
        for request, status in (
            (lambda *_: (404, {"error": "secret information"}), "http_error"),
            (lambda *_: (200, {"name": "models/another"}), "unexpected_model_metadata"),
        ):
            result = read_model_capabilities("key", request=request)
            self.assertEqual(result["metadata_status"], status)
            self.assertIsNone(result["provider_input_token_limit"])
            self.assertNotIn("secret information", json.dumps(result))

        def crash(*_):
            raise ProviderProbeError("hidden metadata response")
        result = read_model_capabilities("key", request=crash)
        self.assertEqual(result["metadata_status"], "transport_or_response_error")
        self.assertNotIn("hidden metadata response", json.dumps(result))

    def test_cli_writes_only_safe_capability_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "limits.json"
            output = io.StringIO()
            with patch.dict(os.environ, {"GEMINI_API_KEY": "fixture-private-key"}, clear=True):
                with patch("graphwalks_model_capabilities._metadata_get",
                           return_value=(200, {
                               "name": "models/" + GEMINI_CLAIM_MODEL,
                               "inputTokenLimit": 1_048_576,
                               "outputTokenLimit": 65_536,
                               "raw": "fixture-private-key",
                           })):
                    with patch.object(sys, "argv", ["limits", "--out", str(path)]):
                        with redirect_stdout(output):
                            self.assertEqual(main(), 0)
            data = json.loads(path.read_text())
            self.assertEqual(data["provider_input_token_limit"], 1_048_576)
            self.assertNotIn("fixture-private-key", path.read_text())
            self.assertNotIn("fixture-private-key", output.getvalue())


if __name__ == "__main__":
    unittest.main()
