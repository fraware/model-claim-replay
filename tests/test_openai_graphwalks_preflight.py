"""Regression tests for the independent no-generation workflow boundary."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from model_claim_replay.core import ReplayError
from model_claim_replay.openai_graphwalks import MODEL, PREFLIGHT

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from openai_graphwalks_preflight import count_only_request, main


class OpenAILivePreflightTests(unittest.TestCase):
    def test_endpoint_guard(self):
        transport = Mock(return_value={"fixture": True})
        for path, payload in (
            ("/v1/responses", {"model": MODEL}),
            ("/v1/chat/completions", {}),
            ("/v1/models/" + MODEL, {}),
            ("/v1/responses/input_tokens", None),
            ("/v1/models/other-model", None),
        ):
            with self.subTest(path=path, payload=payload), self.assertRaises(ReplayError):
                count_only_request(path, payload, "fixture", transport=transport)
        transport.assert_not_called()
        for path, payload in (
            ("/v1/models/" + MODEL, None),
            ("/v1/responses/input_tokens", {"model": MODEL, "input": "fixture"}),
        ):
            self.assertEqual(count_only_request(path, payload, "fixture", transport=transport),
                             {"fixture": True})
        self.assertEqual(transport.call_count, 2)

    def test_cli_uses_fixed_nonpaid_mode_and_guard(self):
        args = ["preflight", "--parquet", "source", "--index", "index", "--out", "out"]
        result = {"status": "preflight_ready", "generation_performed": False,
                  "input_tokens": 123, "reservation_usd": "1"}
        with patch.object(sys, "argv", args), patch(
            "openai_graphwalks_preflight.diagnostic", return_value=result
        ) as run:
            self.assertEqual(main(), 0)
        self.assertEqual(run.call_args.kwargs["approval"], PREFLIGHT)
        self.assertEqual(run.call_args.kwargs["budget"], "5")
        self.assertIs(run.call_args.kwargs["request"], count_only_request)

    def test_workflow_scope_and_allowlisted_artifact(self):
        workflow = (ROOT / ".github/workflows/graphwalks-openai-preflight.yml").read_text()
        self.assertIn("branches:\n      - main", workflow)
        self.assertIn("paths:\n      - '.github/workflows/graphwalks-openai-preflight.yml'", workflow)
        for forbidden in ("workflow_dispatch:", "pull_request:", "schedule:",
                          "AUTHORIZE_PAID_OPENAI", "secrets.GEMINI_API_KEY"):
            self.assertNotIn(forbidden, workflow)
        self.assertIn("python scripts/openai_graphwalks_preflight.py", workflow)
        upload = workflow.split("name: Retain score-free preflight evidence", 1)[1]
        self.assertIn(".runs/openai-preflight/public/plan.json", upload)
        self.assertIn(".runs/openai-preflight/public/outcome.json", upload)
        self.assertNotIn("/private/", upload)
        self.assertNotIn("intent.json", upload)
        self.assertNotIn("response.json", upload)


if __name__ == "__main__":
    unittest.main()
