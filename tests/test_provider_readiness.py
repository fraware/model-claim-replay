"""Offline tests of OpenAI-only readiness, exact model identity and key hygiene."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from provider_readiness import DEFAULT_MODEL, ProviderProbeError, _metadata_get, main, probe_providers


class ProviderReadinessTests(unittest.TestCase):
    def test_openai_only_with_both_keys(self):
        calls = []
        def get(host, path, headers):
            calls.append((host, path, headers))
            return 200, {"id": DEFAULT_MODEL}
        out = probe_providers({"OPENAI_API_KEY": "fixture-o", "GEMINI_API_KEY": "fixture-g"}, request=get)
        self.assertEqual(out["selected"], "openai")
        self.assertIsNone(out["fallback"])
        self.assertEqual(out["gemini"]["status"], "not_checked")
        self.assertEqual(calls, [("api.openai.com", "/v1/models/" + DEFAULT_MODEL,
                                 {"Authorization": "Bearer fixture-o", "Accept": "application/json"})])
        self.assertNotIn("fixture-o", json.dumps(out))
        self.assertNotIn("fixture-g", json.dumps(out))
        self.assertFalse(out["generative_request_performed"])

    def test_missing_openai_never_contacts_gemini(self):
        out = probe_providers({"GEMINI_API_KEY": "fixture-g"}, request=lambda *_: self.fail("network"))
        self.assertIsNone(out["selected"])
        self.assertEqual(out["openai"]["status"], "credential_missing")

    def test_alias_retry_metadata_only(self):
        calls = []
        def get(host, path, headers):
            self.assertEqual(host, "api.openai.com")
            calls.append(headers["Authorization"])
            return (401, None) if len(calls) == 1 else (200, {"id": DEFAULT_MODEL})
        out = probe_providers({"OPENAI_API_KEY": "stale", "OPENAI_KEY": "valid"}, request=get)
        self.assertEqual(calls, ["Bearer stale", "Bearer valid"])
        self.assertEqual(out["selected"], "openai")

    def test_wrong_model_and_transport_failure(self):
        out = probe_providers({"OPENAI_API_KEY": "key"}, request=lambda *_: (200, {"id": "wrong"}))
        self.assertIsNone(out["selected"])
        self.assertEqual(out["openai"]["status"], "unexpected_model_metadata")
        def fail(*_):
            raise ProviderProbeError("sensitive")
        out = probe_providers({"OPENAI_API_KEY": "key"}, request=fail)
        self.assertIsNone(out["selected"])
        self.assertNotIn("sensitive", json.dumps(out))

    def test_no_redirects_and_no_error_body(self):
        class Response:
            status = 302
            def read(self, *_):
                raise AssertionError("Never read error or redirect body")
        class Connection:
            def __init__(self, host, *, timeout): pass
            def request(self, method, path, headers): pass
            def getresponse(self): return Response()
            def close(self): pass
        with patch("provider_readiness.http.client.HTTPSConnection", Connection):
            self.assertEqual(_metadata_get("api.openai.com", "/v1/models", {}), (302, None))

    def test_cli_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "receipt.json"
            with patch("provider_readiness.os.environ", {"OPENAI_API_KEY": "secret"}), patch(
                "provider_readiness._metadata_get", return_value=(200, {"id": DEFAULT_MODEL})
            ), patch.object(sys, "argv", ["provider_readiness", "--out", str(path)]):
                self.assertEqual(main(), 0)
                self.assertNotIn("secret", path.read_text())
                with self.assertRaises(SystemExit):
                    main()


if __name__ == "__main__":
    unittest.main()
