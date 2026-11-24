"""Check prespecified selection, full denominator and no-generation contract."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

from model_claim_replay.core import ReplayError, sha256_bytes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from openai_graphwalks_campaign_preflight import count_campaign, selected_tasks, validate_manifest


class CampaignPreflightTests(unittest.TestCase):
    def test_selection_matches_frozen_issue(self):
        source = json.loads((ROOT / "website/graphwalks-audit.json").read_text())
        index = [{**row, "prompt_chars_actual": row["prompt_chars"]} for row in source["tasks"]]
        manifest = json.loads((ROOT / "evidence/graphwalks/openai-campaign-v1.json").read_text())
        validate_manifest(manifest, index)
        self.assertEqual(selected_tasks(index), manifest["tasks"])
        self.assertEqual(len(manifest["tasks"]), 16)
        self.assertEqual([r["band"] for r in manifest["tasks"]], ["short"] * 8 + ["long"] * 8)
        self.assertNotIn("bfs-row-000100", [r["id"] for r in manifest["tasks"]])
        tampered = {**manifest, "tasks": list(reversed(manifest["tasks"]))}
        with self.assertRaises(ReplayError):
            validate_manifest(tampered, index)

    def test_all_tasks_counted_once_and_failures_distinct(self):
        prompts = {f"task-{n}": f"fixture {n}" for n in range(16)}
        manifest = {"tasks": [{"id": k, "prompt_chars": len(v),
                              "prompt_sha256": sha256_bytes(v.encode()),
                              "band": "short" if n < 8 else "long"}
                             for n, (k, v) in enumerate(prompts.items())]}
        calls = []
        def request(path, payload, key):
            self.assertEqual(path, "/v1/responses/input_tokens")
            self.assertEqual(payload["truncation"], "disabled")
            self.assertEqual(payload["reasoning"]["effort"], "xhigh")
            calls.append(payload["input"])
            n = int(payload["input"].split()[-1])
            if n == 15:
                raise ReplayError("OpenAI HTTP 400")
            return {"object": "response.input_tokens", "input_tokens": 255598 if n < 8 else 1020000}
        result = count_campaign(manifest, prompts, key="fixture", request=request)
        self.assertEqual(calls, list(prompts.values()))
        self.assertEqual((result["feasible"], result["context_blocked"], result["count_failed"]), (8, 7, 1))
        self.assertEqual(result["selected_tasks"], 16)
        self.assertFalse(result["all_counts_observed"])
        self.assertFalse(result["paid_authorization"])
        self.assertFalse(result["generation_performed"])
        self.assertNotIn("grade", result)
        self.assertIsNone(result["tasks"][-1]["input_tokens"])
        self.assertEqual(result["tasks"][-1]["count_error"], "OpenAI HTTP 400")
        forbidden = Mock()
        with self.assertRaises(ReplayError):
            count_campaign(manifest, {**prompts, "task-15": "changed"}, key="fixture", request=forbidden)
        forbidden.assert_not_called()

    def test_workflow_is_nongenerative_and_main_scoped(self):
        workflow = (ROOT / ".github/workflows/graphwalks-openai-campaign-preflight.yml").read_text()
        self.assertIn("branches:\n      - main", workflow)
        self.assertIn("python scripts/openai_graphwalks_campaign_preflight.py", workflow)
        for forbidden in ("AUTHORIZE_PAID_OPENAI", "workflow_dispatch:", "pull_request:", "schedule:", "GEMINI_API_KEY"):
            self.assertNotIn(forbidden, workflow)
        self.assertIn("path: .runs/campaign/preflight.json", workflow)


if __name__ == "__main__":
    unittest.main()
