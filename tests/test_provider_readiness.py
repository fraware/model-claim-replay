"""Offline validation of provider metadata readiness and safe fallbacks."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from provider_readiness import (  # noqa: E402
    GEMINI_CLAIM_MODEL, ProviderProbeError, _metadata_get, main, probe_providers,
)


class ProviderReadinessTests(unittest.TestCase):
    """Inject metadata responses; tests never contact a provider or read keys."""

    def test_gemini_target_metadata_is_preferred(self):
        calls = []
        def get(host, path, headers):
            calls.append((host, path, dict(headers)))
            return (200, {"name": "models/" + GEMINI_CLAIM_MODEL})
        out = probe_providers(
            {"GEMINI_API_KEY": "secret-gemini", "OPENAI_API_KEY": "secret-openai"},
            request=get,
        )
        self.assertEqual(out["selected"], "gemini")
        self.assertEqual(out["gemini"]["status"], "model_metadata_available")
        self.assertEqual(out["openai"]["status"], "not_checked")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], "/v1beta/models/" + GEMINI_CLAIM_MODEL)
        self.assertEqual(calls[0][2]["x-goog-api-key"], "secret-gemini")
        self.assertNotIn("secret-gemini", json.dumps(out))
        self.assertNotIn("secret-openai", json.dumps(out))

    def test_gemini_404_falls_back_to_openai_metadata(self):
        calls = []
        def get(host, path, headers):
            calls.append(host)
            if "googleapis.com" in host:
                return 404, {"error": "forbidden content must never be logged"}
            return 200, {"object": "list", "data": [{"id": "unrelated-model"}]}
        out = probe_providers(
            {"GOOGLE_API_KEY": "secret-google", "OPENAI_API_KEY": "secret-openai"},
            request=get,
        )
        self.assertEqual(out["selected"], "openai")
        self.assertEqual(out["gemini"], {"status": "http_error", "http_status": 404})
        self.assertEqual(out["openai"]["status"], "model_catalog_available")
        self.assertEqual(len(calls), 2)
        self.assertNotIn("forbidden content", json.dumps(out))
        self.assertFalse(out["generative_request_performed"])
        self.assertFalse(out["benchmark_claim_reproduced"])

    def test_malformed_gemini_and_openai_fallback(self):
        def get(host, path, headers):
            if "googleapis.com" in host:
                return 200, {"name": "models/not-the-claim-model"}
            return 200, {"data": [{"id": "accessible"}]}
        out = probe_providers(
            {"GEMINI_API_KEY": "g", "OPENAI_KEY": "o"}, request=get,
        )
        self.assertEqual(out["selected"], "openai")
        self.assertEqual(out["gemini"]["status"], "unexpected_model_metadata")

    def test_stale_gemini_secret_alias_does_not_hide_valid_alternate(self):
        attempts = []
        def get(host, path, headers):
            attempts.append(headers["x-goog-api-key"])
            return (401, None) if len(attempts) == 1 else (
                200, {"name": "models/" + GEMINI_CLAIM_MODEL},
            )
        out = probe_providers(
            {"GEMINI_API_KEY": "expired", "GOOGLE_API_KEY": "valid",
             "OPENAI_API_KEY": "unused"},
            request=get,
        )
        self.assertEqual(attempts, ["expired", "valid"])
        self.assertEqual(out["selected"], "gemini")
        self.assertEqual(out["openai"]["status"], "not_checked")
        self.assertNotIn("expired", json.dumps(out))
        self.assertNotIn("valid", json.dumps(out))

    def test_stale_openai_secret_alias_does_not_hide_valid_alternate(self):
        attempts = []
        def get(host, path, headers):
            token = headers["Authorization"]
            attempts.append(token)
            return (403, None) if len(attempts) == 1 else (
                200, {"data": [{"id": "available"}]},
            )
        out = probe_providers(
            {"OPENAI_API_KEY": "expired", "OPENAI_KEY": "valid"}, request=get,
        )
        self.assertEqual(out["selected"], "openai")
        self.assertEqual(len(attempts), 2)
        self.assertEqual(out["gemini"]["status"], "credential_missing")
        self.assertNotIn("expired", json.dumps(out))
        self.assertNotIn("valid", json.dumps(out))

    def test_transport_failure_falls_back_to_openai(self):
        def get(host, path, headers):
            if "googleapis.com" in host:
                raise ProviderProbeError("internal")
            return 200, {"data": [{"id": "model"}]}
        out = probe_providers(
            {"GEMINI_API_KEY": "g", "OPENAI_API_KEY": "o"}, request=get,
        )
        self.assertEqual(out["selected"], "openai")
        self.assertEqual(out["gemini"]["status"], "transport_or_response_error")
        self.assertNotIn("internal", json.dumps(out))

    def test_missing_gemini_only_openai_key(self):
        out = probe_providers(
            {"OPENAI_API_KEY": "valid"},
            request=lambda host, path, headers: (200, {"data": [{"id": "model"}]}),
        )
        self.assertEqual(out["selected"], "openai")
        self.assertEqual(out["gemini"]["status"], "credential_missing")

    def test_no_credentials_fail_without_network(self):
        out = probe_providers({}, request=lambda *_: self.fail("network request"))
        self.assertIsNone(out["selected"])
        self.assertEqual(out["gemini"]["status"], "credential_missing")
        self.assertEqual(out["openai"]["status"], "credential_missing")

    def test_openai_key_not_used_if_gemini_succeeds(self):
        def get(host, path, headers):
            self.assertNotIn("Authorization", headers)
            return 200, {"name": "models/" + GEMINI_CLAIM_MODEL}
        out = probe_providers(
            {"GEMINI_API_KEY": "valid", "OPENAI_API_KEY": "fallback"}, request=get,
        )
        self.assertEqual(out["selected"], "gemini")

    def test_openai_invalid_catalog_is_not_marked_usable(self):
        for catalog in ({}, {"data": []}, {"data": [{"id": 123}]}):
            with self.subTest(catalog=catalog):
                out = probe_providers(
                    {"OPENAI_API_KEY": "valid"},
                    request=lambda *_: (200, catalog),
                )
                self.assertIsNone(out["selected"])
                self.assertEqual(out["openai"]["status"], "unexpected_model_catalog")

    def test_probe_no_redirects_and_does_not_decode_error_body(self):
        class Response:
            status = 302
            def read(self, *_args):
                raise AssertionError("Never read provider error or redirect bodies")
        class Connection:
            def __init__(self, host, *, timeout):
                self.assertHost = host
                self.timeout = timeout
                self.called = []
            def request(self, method, path, headers):
                self.called.append((method, path, headers))
            def getresponse(self):
                return Response()
            def close(self):
                pass
        with patch("provider_readiness.http.client.HTTPSConnection", Connection):
            code, payload = _metadata_get(
                "api.openai.com", "/v1/models", {"Authorization": "Bearer secret"},
            )
        self.assertEqual(code, 302)
        self.assertIsNone(payload)

    def test_cli_writes_only_redacted_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "status.json"
            with patch("provider_readiness.os.environ", {"OPENAI_API_KEY": "s3cr3t"}):
                with patch("provider_readiness._metadata_get", return_value=(
                    200, {"data": [{"id": "model"}]},
                )):
                    with patch.object(sys, "argv", ["provider_readiness", "--out", str(out)]):
                        self.assertEqual(main(), 0)
            receipt = out.read_text()
            self.assertNotIn("s3cr3t", receipt)
            self.assertEqual(json.loads(receipt)["selected"], "openai")
            with patch.object(sys, "argv", ["provider_readiness", "--out", str(out)]):
                with self.assertRaises(SystemExit):
                    main()


if __name__ == "__main__":
    unittest.main()
