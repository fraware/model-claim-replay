"""Exercise the OpenAI diagnostic with injected transport and fixture source."""
from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from model_claim_replay.core import ReplayError, sha256_bytes
from model_claim_replay.openai_graphwalks import APPROVAL, MODEL, PREFLIGHT, TASK, diagnostic, reservation, authorization, dispatch_mode


class OpenAIDiagnosticTests(unittest.TestCase):
    def test_authorization(self):
        for approval,budget in [("NO","5"),(APPROVAL,"0"),(APPROVAL,"NaN"),(APPROVAL,"101")]:
            with self.assertRaises(ReplayError):
                authorization(approval,budget)
        self.assertEqual(reservation(355124, 65536), Decimal("2.758660"))

    def test_default_preflight_never_generates_even_when_within_budget(self):
        self.assertEqual(dispatch_mode(PREFLIGHT, "5"), (False, Decimal("5")))
        self.assertEqual(dispatch_mode(APPROVAL, "5"), (True, Decimal("5")))
        for mode in ("NO", "", "true", "paid"):
            with self.assertRaises(ReplayError):
                dispatch_mode(mode, "5")
        with self.assertRaises(ReplayError):
            authorization(PREFLIGHT, "5")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "index.jsonl"
            prompt = "fixture"
            index.write_text(json.dumps({"id": TASK, "prompt_sha256": sha256_bytes(prompt.encode()),
                                         "answer_nodes": ["a"]}) + "\n")
            for tokens, budget, expected in (
                (355124, "5", "preflight_ready"),
                (355124, "1", "preflight_blocked"),
                (950000, "100", "preflight_blocked"),
            ):
                with self.subTest(tokens=tokens, budget=budget):
                    calls = []
                    def request(path, payload, key):
                        calls.append(path)
                        if path.startswith("/v1/models/"):
                            return {"id": MODEL}
                        if path == "/v1/responses/input_tokens":
                            return {"object": "response.input_tokens", "input_tokens": tokens}
                        self.fail("Preflight reached generation endpoint")
                    out = root / f"preflight-{tokens}-{budget}"
                    result = diagnostic(root / "unused", index, out, approval=PREFLIGHT,
                                        budget=budget, environ={"OPENAI_API_KEY": "fixture"},
                                        request=request, source_reader=lambda *_: {TASK: prompt})
                    self.assertEqual(result["status"], expected)
                    self.assertFalse(result["generation_performed"])
                    self.assertNotIn("grade", result)
                    self.assertEqual(calls, ["/v1/models/" + MODEL, "/v1/responses/input_tokens"])
                    self.assertFalse((out / "public/intent.json").exists())
                    self.assertFalse((out / "private").exists())
                    plan = json.loads((out / "public/plan.json").read_text())
                    self.assertIsNone(plan["authorized_ceiling_usd"])

    def test_invalid_dispatch_never_reads_source_or_contacts_provider(self):
        def forbidden(*args):
            self.fail("Invalid approval reached source or provider")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ReplayError):
                diagnostic(root / "unused", root / "unused", root / "out",
                           approval="NO", budget="0", environ={},
                           request=forbidden, source_reader=forbidden)
            self.assertFalse((root / "out").exists())

    def test_one_request_and_redacted_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "index.jsonl"
            prompt = "fixture prompt"
            index.write_text(json.dumps({"id":TASK,"prompt_sha256":sha256_bytes(prompt.encode()),"answer_nodes":["a"]})+"\n")
            calls = []
            def request(path,payload,key):
                calls.append(path)
                self.assertEqual(key,"fixture-key")
                if path.startswith("/v1/models/"):
                    return {"id":MODEL}
                if path.endswith("input_tokens"):
                    self.assertEqual(payload["input"],prompt)
                    return {"object":"response.input_tokens","input_tokens":355124}
                self.assertEqual(payload["input"],prompt)
                self.assertFalse(payload["store"])
                self.assertEqual(payload["tools"],[])
                self.assertEqual(payload["truncation"],"disabled")
                self.assertEqual(payload["service_tier"],"default")
                self.assertEqual(payload["prompt_cache_options"],{"mode":"explicit","ttl":"30m"})
                self.assertTrue((root/"out/public/intent.json").is_file())
                return {"status":"completed","model":MODEL,"service_tier":"default",
                        "usage":{"input_tokens":355124,"output_tokens":10,"total_tokens":355134},
                        "output":[{"type":"message","role":"assistant","status":"completed",
                                   "content":[{"type":"output_text","text":"Final Answer: [a]"}]}]}
            kw = dict(approval=APPROVAL,budget="5",environ={"OPENAI_API_KEY":"fixture-key"},
                      request=request,source_reader=lambda *_:{TASK:prompt})
            result = diagnostic(root/"unused",index,root/"out",**kw)
            self.assertEqual(result["grade"]["f1"],1)
            self.assertFalse(result["published_claim_reproduced"])
            self.assertEqual(calls.count("/v1/responses"),1)
            self.assertNotIn("Final Answer", (root/"out/public/outcome.json").read_text())
            with self.assertRaises(ReplayError):
                diagnostic(root/"unused",index,root/"out",**kw)
            self.assertEqual(calls.count("/v1/responses"),1)

    def test_budget_context_and_uncertain_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root/"index.jsonl"
            prompt = "fixture"
            index.write_text(json.dumps({"id":TASK,"prompt_sha256":sha256_bytes(prompt.encode()),"answer_nodes":["a"]})+"\n")
            for tokens,budget,paid in [(950000,"100",False),(355124,"1",False),(355124,"5",True)]:
                out = root/f"out-{budget}-{tokens}"
                calls = []
                def request(path,payload,key):
                    calls.append(path)
                    if path.startswith("/v1/models/"): return {"id":MODEL}
                    if path.endswith("input_tokens"): return {"object":"response.input_tokens","input_tokens":tokens}
                    raise ReplayError("ambiguous")
                with self.assertRaises(ReplayError):
                    diagnostic(root/"unused",index,out,approval=APPROVAL,budget=budget,
                               environ={"OPENAI_KEY":"fixture"},request=request,source_reader=lambda *_:{TASK:prompt})
                self.assertEqual("/v1/responses" in calls,paid)
                if paid:
                    self.assertEqual(json.loads((out/"public/outcome.json").read_text())["status"],"generation_or_accounting_uncertain")
                else:
                    self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
