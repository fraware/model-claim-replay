"""Wire-level, zero-credential integration tests for one-hop Gemini REST requests."""

from __future__ import annotations

import http.client
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from model_claim_replay.core import ReplayError
from model_claim_replay.gemini_rest import (
    API_PATH, API_REVISION, MAX_ONE_HOP_OUTPUT, ProviderStatusError,
    single_interaction,
)


class _Handler(BaseHTTPRequestHandler):
    requests: list[dict] = []
    status_code = 200
    response_body: bytes = b""

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.__class__.requests.append({
            "path": self.path, "headers": dict(self.headers.items()),
            "body": body,
        })
        self.send_response(self.__class__.status_code)
        self.send_header("Content-Type", "application/json")
        if self.__class__.status_code == 302:
            self.send_header("Location", "https://example.org/a-secret")
        self.send_header("Content-Length", str(len(self.__class__.response_body)))
        self.end_headers()
        self.wfile.write(self.__class__.response_body)

    def log_message(self, *_: object) -> None:
        pass


def response(*, status: str = "completed", output: str = "Final Answer: [node-1]", model: str = "gemini-4-neon") -> bytes:
    return json.dumps({
        "id": "test-interaction-id", "status": status,
        "model": model,
        "usage": {"total_input_tokens": 100, "total_output_tokens": 25,
                  "total_thought_tokens": 6},
        "steps": [{"type": "thought", "signature": "private-thought"},
                  {"type": "model_output", "content": [{"type": "text", "text": output}]}],
    }).encode("utf-8")


class GeminiRESTContractTests(unittest.TestCase):
    def setUp(self) -> None:
        _Handler.requests = []
        _Handler.status_code = 200
        _Handler.response_body = response()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def _call(self, max_output_tokens: int = 4096):
        def connect(host: str, *, timeout: int):
            self.assertEqual(host, "generativelanguage.googleapis.com")
            return http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=timeout)
        return single_interaction("One synthetic GraphWalks question", api_key="test-not-secret",
                                  model="gemini-4-neon", max_output_tokens=max_output_tokens,
                                  thinking_level="xhigh", _connect=connect)

    def test_single_post_and_exact_generation_contract(self):
        result = self._call()
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.output_text, "Final Answer: [node-1]")
        self.assertEqual(result.usage.total_input_tokens, 100)
        self.assertEqual(len(_Handler.requests), 1)
        message = _Handler.requests[0]
        self.assertEqual(message["path"], API_PATH)
        headers = {key.lower(): value for key, value in message["headers"].items()}
        self.assertEqual(headers["api-revision"], API_REVISION)
        self.assertEqual(headers["x-goog-api-key"], "test-not-secret")
        payload = json.loads(message["body"])
        self.assertEqual(payload, {
            "model": "gemini-4-neon", "input": "One synthetic GraphWalks question",
            "generation_config": {"thinking_level": "xhigh", "max_output_tokens": 4096},
            "background": False, "stream": False, "store": False,
            "service_tier": "standard",
        })

    def test_model_documented_foreground_output_limit_is_accepted(self):
        result = self._call(max_output_tokens=MAX_ONE_HOP_OUTPUT)
        self.assertEqual(result.status, "completed")
        self.assertEqual(len(_Handler.requests), 1)
        payload = json.loads(_Handler.requests[0]["body"])
        self.assertEqual(
            payload["generation_config"]["max_output_tokens"], 65536,
        )

    def test_429_error_does_not_retry_or_expose_response(self):
        _Handler.status_code = 429
        _Handler.response_body = b'{"error":"secret server response"}'
        with self.assertRaisesRegex(ProviderStatusError, "HTTP 429") as ctx:
            self._call()
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertNotIn("secret", str(ctx.exception))
        self.assertEqual(len(_Handler.requests), 1)

    def test_redirect_does_not_trigger_followup_request(self):
        _Handler.status_code = 302
        with self.assertRaisesRegex(ProviderStatusError, "HTTP 302"):
            self._call()
        self.assertEqual(len(_Handler.requests), 1)

    def test_continuation_is_not_a_completed_result(self):
        _Handler.response_body = response(status="requires_continuation", output="PRIVATE PARTIAL ANSWER")
        result = self._call()
        self.assertEqual(result.status, "requires_continuation")
        self.assertIsNone(result.output_text)
        self.assertEqual(len(_Handler.requests), 1)

    def test_mismatched_model_is_rejected_after_single_request(self):
        _Handler.response_body = response(model="some-other-model")
        with self.assertRaisesRegex(ReplayError, "model does not match"):
            self._call()
        self.assertEqual(len(_Handler.requests), 1)

    def test_missing_model_output_is_not_silently_scored(self):
        broken = json.loads(response())
        broken["steps"] = [{"type": "thought", "signature": "not-output"}]
        _Handler.response_body = json.dumps(broken).encode()
        with self.assertRaisesRegex(ReplayError, "exactly one"):
            self._call()
        self.assertEqual(len(_Handler.requests), 1)

    def test_missing_usage_blocks_scored_success(self):
        broken = json.loads(response())
        broken.pop("usage")
        _Handler.response_body = json.dumps(broken).encode()
        with self.assertRaisesRegex(ReplayError, "lacks token accounting"):
            self._call()

    def test_negative_or_boolean_usage_is_rejected(self):
        for invalid in (-2, True):
            with self.subTest(value=invalid):
                broken = json.loads(response())
                broken["usage"]["total_input_tokens"] = invalid
                _Handler.response_body = json.dumps(broken).encode()
                with self.assertRaisesRegex(ReplayError, "token count"):
                    self._call()

    def test_invalid_parameter_rejected_before_network_activity(self):
        for invalid in (0, MAX_ONE_HOP_OUTPUT + 1, True):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ReplayError, "one-hop"):
                    def connect(*_, **__):
                        self.fail("Attempted a request with an invalid output limit")
                    single_interaction("test", api_key="test-not-secret", model="gemini-4-neon",
                                       max_output_tokens=invalid, thinking_level="xhigh", _connect=connect)


if __name__ == "__main__":
    unittest.main()
