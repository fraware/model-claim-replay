"""Exercise the offline journal verifier against the frozen public preflight."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from model_claim_replay.core import ReplayError, canonical_json, sha256_bytes
from model_claim_replay.openai_graphwalks import MODEL, PUBLISH_FINAL_LINE
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from openai_graphwalks_campaign_paid import evaluate_response, summarize
from verify_openai_campaign import verify_journal, independent_grade, MANIFEST, ARCHIVE, MANIFEST_SHA256, ARCHIVE_SHA256, INDEX_SHA256

NODE = "0123456789"


class CampaignVerificationTests(unittest.TestCase):
    def test_independent_grade(self):
        self.assertEqual(independent_grade("Final Answer: [" + NODE + "]", [NODE])["f1"], 1)
        self.assertEqual(independent_grade("", [])["f1"], 0)
        self.assertEqual(independent_grade("Final Answer: []", [])["f1"], 1)
        self.assertEqual(independent_grade("Final Answer: [" + NODE + ", " + NODE + "]", [NODE])["predicted_nodes"], 1)
        self.assertAlmostEqual(independent_grade("Final Answer: [" + NODE + "]", [NODE, "1111111111"])["f1"], 2/3)

    def fixture(self, root: Path, mode: str):
        bundle = root / "public"
        bundle.mkdir()
        manifest = json.loads(MANIFEST.read_bytes())
        with zipfile.ZipFile(ARCHIVE) as z:
            frozen = json.loads(z.read("preflight.json"))
        fresh = {k:v for k,v in frozen.items() if k not in ("manifest_sha256","reference_index_sha256")}
        index = root / "index.jsonl"
        index.write_bytes(b"".join(canonical_json({
            "id": t["id"], "problem_type": "bfs", "prompt_sha256": t["prompt_sha256"],
            "prompt_chars_actual": t["prompt_chars"], "answer_nodes": [NODE],
        }) + b"\n" for t in manifest["tasks"]))
        def write(name, value):
            (bundle/name).write_bytes(canonical_json(value) + b"\n")
        plan = {
            "schema_version": "graphwalks-openai-paid-campaign-plan-v1",
            "frozen_preflight_archive_sha256": ARCHIVE_SHA256,
            "manifest_sha256": MANIFEST_SHA256, "reference_index_sha256": INDEX_SHA256,
            "model": MODEL, "reasoning_effort": "xhigh", "max_output_tokens": 65536,
            "service_tier": "default", "prompt_cache_options": {"mode": "explicit", "ttl": "30m"},
            "authorized_ceiling_usd": "25", "publication": PUBLISH_FINAL_LINE,
            "fresh_preflight": fresh, "published_claim_reproduced": False,
        }
        write("plan.json", plan)
        digest = sha256_bytes((bundle/"plan.json").read_bytes())
        rows = []
        for n, src in enumerate(fresh["tasks"],1):
            row = {**src,"generation_attempted":False,"plan_sha256":digest}
            prefix = f"task-{n:02d}"
            if src["status"] == "feasible":
                if mode == "uncertain" and n > 2:
                    row["status"] = "unattempted"
                else:
                    write(prefix+"-intent.json",{"status":"generation_intent","id":src["id"],
                          "plan_sha256":digest,"reservation_usd":src["reservation_usd"]})
                    if mode == "uncertain" and n == 2:
                        row.update(status="generation_or_accounting_uncertain",generation_attempted=True,retry_permitted=False)
                    else:
                        inp = src["input_tokens"]
                        text = "malformed" if mode == "withheld" and n == 1 else "Final Answer: ["+NODE+"]"
                        response = {"model":MODEL,"status":"completed","service_tier":"default",
                                    "usage":{"input_tokens":inp,"output_tokens":20,"total_tokens":inp+20},
                                    "output":[{"type":"message","role":"assistant","status":"completed",
                                               "content":[{"type":"output_text","text":text}]}]}
                        row.update(evaluate_response(response,src,[NODE],PUBLISH_FINAL_LINE))
            write(prefix+"-outcome.json",row)
            rows.append(row)
        write("summary.json",{"schema_version":"graphwalks-openai-paid-campaign-result-v1",
                              "status":"stopped_uncertain" if mode=="uncertain" else "finished",
                              "plan_sha256":digest,"tasks":rows,**summarize(rows)})
        return bundle,index,sha256_bytes(index.read_bytes())

    def test_complete_and_partial_graded_evidence(self):
        for mode, disclosed, withheld, attempted in (("complete",8,0,8),("withheld",7,1,8),("uncertain",1,0,2)):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                b,i,d = self.fixture(Path(tmp),mode)
                result = verify_journal(b,i,expected_index_sha256=d)
                self.assertEqual(result["disclosed_scores_recomputed"],disclosed)
                self.assertEqual(result["withheld_scores_not_recomputed"],withheld)
                self.assertEqual(result["attempted"],attempted)
                self.assertIsNone(result["bands"]["overall"]["full_selected_mean_f1"])
                self.assertFalse(result["provider_execution_authenticated"])
                self.assertFalse(result["external_third_party_review"])

    def test_reject_missing_tampered_and_wrong_index(self):
        for mode in ("missing","grade","intent","index","extra","cost"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                b,i,d = self.fixture(Path(tmp),"complete")
                if mode == "missing":
                    (b/"task-01-outcome.json").unlink()
                elif mode == "index":
                    i.write_bytes(i.read_bytes()+b" ")
                elif mode == "extra":
                    (b/"unexpected.json").write_text("{}")
                else:
                    path=b/("task-01-intent.json" if mode=="intent" else "task-01-outcome.json")
                    row=json.loads(path.read_bytes())
                    if mode=="grade": row["grade"]["f1"]=0.5
                    if mode=="intent": row["reservation_usd"]="0"
                    if mode=="cost": row["upper_usage_cost_usd"]="0"
                    path.write_bytes(canonical_json(row)+b"\n")
                with self.assertRaises((ReplayError,KeyError)):
                    verify_journal(b,i,expected_index_sha256=d)


if __name__ == "__main__":
    unittest.main()
