"""Network-isolated checks for a one-request portable chat-completions adapter."""

from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from model_claim_replay.cli import api_completion
from model_claim_replay.core import ReplayError


class _WireHandler(BaseHTTPRequestHandler):
    received = 0
    behavior = "success"

    def do_POST(self) -> None:
        self.__class__.received += 1
        length = int(self.headers["Content-Length"])
        self.rfile.read(length)
        behavior = self.__class__.behavior
        if behavior in ("redirect-302", "redirect-307"):
            self.send_response(302 if behavior == "redirect-302" else 307)
            self.send_header("Location", "/v1/chat/completions")
            self.end_headers()
            return
        finish_reason = {
            "success": "stop",
            "truncated": "length",
            "filtered": "content_filter",
            "tool_call": "tool_calls",
            "pending": None,
        }.get(behavior, "stop")
        choice = {"message": {"content": "alpha"}}
        if behavior != "missing_finish_reason":
            choice["finish_reason"] = finish_reason
        payload = json.dumps({"choices": [choice], "usage": {"total_tokens": 23}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_: object) -> None:
        pass


class NoRedirectOrIncompleteScoringTests(unittest.TestCase):
    def check(self, behavior: str, *, succeeds: bool = False) -> None:
        class Handler(_WireHandler):
            pass
        Handler.received = 0
        Handler.behavior = behavior
        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            kwargs = dict(
                base_url=f"http://127.0.0.1:{server.server_port}/v1",
                api_key="test-only-local-secret", model="fake", messages=[{"role": "user", "content": "hi"}],
                temperature=0, max_tokens=20, timeout=3,
            )
            if succeeds:
                actual, usage = api_completion(**kwargs)
                self.assertEqual(actual, "alpha")
                self.assertEqual(usage, {"total_tokens": 23})
            else:
                with self.assertRaises(ReplayError) as cm:
                    api_completion(**kwargs)
                self.assertNotIn("test-only-local-secret", str(cm.exception))
            self.assertEqual(Handler.received, 1, "A single call triggered multiple HTTP requests")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_completed_response(self) -> None:
        self.check("success", succeeds=True)

    def test_302_does_not_follow(self) -> None:
        self.check("redirect-302")

    def test_307_does_not_follow_or_resubmit_body(self) -> None:
        self.check("redirect-307")

    def test_truncated_output_not_scored(self) -> None:
        self.check("truncated")

    def test_filtered_output_not_scored(self) -> None:
        self.check("filtered")

    def test_tool_call_not_scored_as_text_completion(self) -> None:
        self.check("tool_call")

    def test_pending_output_not_scored(self) -> None:
        self.check("pending")

    def test_missing_finish_reason_not_scored(self) -> None:
        self.check("missing_finish_reason")


if __name__ == "__main__":
    unittest.main()
