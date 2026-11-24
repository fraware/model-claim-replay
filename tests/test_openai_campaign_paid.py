"""Test paid campaign accounting and stop rules with injected transports."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path

from model_claim_replay.core import ReplayError, sha256_bytes
from model_claim_replay.openai_graphwalks import MODEL, PUBLISH_FINAL_LINE, REDACTED_ONLY

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from openai_graphwalks_campaign_paid import (
    APPROVAL, load_frozen_preflight, run_campaign, evaluate_response,
)
from openai_graphwalks_campaign_preflight import count_campaign, MANIFEST

NODE = "0123456789"


class PaidCampaignTests(unittest.TestCase):
    def test_original_preflight_archive(self):
        frozen = load_frozen_preflight()
        manifest = json.loads(MANIFEST.read_bytes())
        self.assertEqual((frozen["selected_tasks"], frozen["feasible"],
                          frozen["context_blocked"], frozen["count_failed"]), (16, 8, 8, 0))
        self.assertEqual(frozen["total_feasible_reservation_usd"], "20.699335")
        for task, row in zip(manifest["tasks"], frozen["tasks"]):
            self.assertEqual(task, {k: row[k] for k in task})

    def test_complete_stop_and_changed_preflight(self):
        prompts = {f"task-{n}": f"fixture {n}" for n in range(16)}
        manifest = {"tasks": [{"id": k, "prompt_chars": len(v),
                               "prompt_sha256": sha256_bytes(v.encode()),
                               "band": "short" if n < 8 else "long"}
                              for n, (k, v) in enumerate(prompts.items())]}
        references = {k: [NODE] for k in prompts}
        def count(path, payload, key):
            n = int(payload["input"].split()[-1])
            return {"object": "response.input_tokens", "input_tokens": 255598 if n < 8 else 1022000}
        frozen = count_campaign(manifest, prompts, key="fixture", request=count)
        for mode in ("complete", "uncertain", "changed", "unauthorized"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "run"
                calls = []
                paid = []
                def request(path, payload, key):
                    calls.append(path)
                    if path.startswith("/v1/models/"):
                        return {"id": MODEL}
                    if path == "/v1/responses/input_tokens":
                        response = count(path, payload, key)
                        if mode == "changed":
                            response["input_tokens"] += 1
                        return response
                    self.assertEqual(path, "/v1/responses")
                    self.assertEqual(calls.count("/v1/responses/input_tokens"), 16)
                    n = len(paid)
                    paid.append(payload["input"])
                    self.assertTrue((out/"public"/f"task-{n+1:02d}-intent.json").is_file())
                    if mode == "uncertain" and n == 1:
                        raise ReplayError("transport failure")
                    return {"model": MODEL, "status": "completed", "service_tier": "default",
                            "usage": {"input_tokens": 255598, "output_tokens": 20, "total_tokens": 255618},
                            "output": [{"type": "message", "role": "assistant", "status": "completed",
                                        "content": [{"type": "output_text", "text": "Final Answer: ["+NODE+"]"}]}]}
                kwargs = dict(approval=APPROVAL if mode != "unauthorized" else "NO", budget="25",
                              publication=PUBLISH_FINAL_LINE, environ={"OPENAI_KEY": "fixture"}, request=request)
                if mode == "unauthorized":
                    with self.assertRaises(ReplayError):
                        run_campaign(manifest,prompts,references,frozen,out,**kwargs)
                    self.assertEqual(calls, [])
                    continue
                result = run_campaign(manifest,prompts,references,frozen,out,**kwargs)
                self.assertEqual(result["overall"]["selected"], 16)
                self.assertEqual(result["overall"]["statuses"]["context_blocked"], 8)
                self.assertIsNone(result["overall"]["full_selected_mean_f1"])
                self.assertIsNone(result["long"]["conditional_mean_f1"])
                self.assertEqual(len(list((out/"public").glob("task-*-outcome.json"))), 16)
                if mode == "complete":
                    self.assertEqual(len(paid), 8)
                    self.assertEqual(result["short"]["conditional_mean_f1"], 1)
                    self.assertEqual(result["short"]["full_selected_mean_f1"], 1)
                    self.assertTrue(result["all_attempted_usage_accounted"])
                elif mode == "uncertain":
                    self.assertEqual(len(paid), 2)
                    self.assertEqual(result["overall"]["statuses"]["unattempted"], 6)
                    self.assertFalse(result["all_attempted_usage_accounted"])
                else:
                    self.assertEqual(paid, [])
                    self.assertEqual(result["overall"]["statuses"]["unattempted"], 8)
                with self.assertRaises(ReplayError):
                    run_campaign(manifest,prompts,references,frozen,out,**kwargs)

    def test_noncompleted_and_malformed_are_not_conflated(self):
        row = {"input_tokens": 255598, "reservation_usd": "2.58871"}
        response = {"model": MODEL, "status": "incomplete", "service_tier": "default",
                    "usage": {"input_tokens": 255598, "output_tokens": 20, "total_tokens": 255618}}
        self.assertEqual(evaluate_response(response,row,[NODE],REDACTED_ONLY)["status"], "incomplete")
        response.update(status="completed", output=[{"type":"message","role":"assistant","status":"completed",
                          "content":[{"type":"refusal","refusal":"private"}]}])
        self.assertEqual(evaluate_response(response,row,[NODE],REDACTED_ONLY)["status"], "refused")
        response["output"][0]["content"] = [{"type":"output_text","text":"malformed"}]
        result = evaluate_response(response,row,[NODE],PUBLISH_FINAL_LINE)
        self.assertEqual(result["grade"]["f1"], 0)
        self.assertTrue(result["grade"]["parse_failed"])
        self.assertNotIn("final_line",result)
        response["usage"]["total_tokens"] += 1
        with self.assertRaises(ReplayError):
            evaluate_response(response,row,[NODE],REDACTED_ONLY)


if __name__ == "__main__":
    unittest.main()
