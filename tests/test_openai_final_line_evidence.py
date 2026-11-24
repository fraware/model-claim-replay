"""Exercise opt-in publication and independent offline score recomputation."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from model_claim_replay.core import ReplayError, canonical_json, sha256_bytes
from model_claim_replay.openai_graphwalks import (
    APPROVAL, MODEL, PREFLIGHT, PUBLISH_FINAL_LINE, REDACTED_ONLY, TASK,
    diagnostic, public_final_line,
)
from model_claim_replay.openai_graphwalks_verify import verify

NODE = "0123456789"


class FinalLineEvidenceTests(unittest.TestCase):
    def test_exact_line_policy(self):
        self.assertEqual(public_final_line("earlier reasoning\nFinal Answer: [" + NODE + "]"),
                         "Final Answer: [" + NODE + "]")
        self.assertEqual(public_final_line("Final Answer: [" + NODE + "]\n"), "")
        self.assertIsNone(public_final_line("Final Answer: [private prose]"))
        self.assertIsNone(public_final_line("unrelated text"))
        self.assertIsNone(public_final_line("Final Answer: [" + NODE + "]\r"))

    def test_preflight_or_invalid_publication_never_reaches_source(self):
        def forbidden(*_):
            self.fail("Invalid publication reached source or network")
        for approval, publication in ((PREFLIGHT, PUBLISH_FINAL_LINE), (APPROVAL, "unknown")):
            with self.subTest(approval=approval), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                with self.assertRaises(ReplayError):
                    diagnostic(root/"unused", root/"unused", root/"out", approval=approval,
                               budget="5", environ={}, request=forbidden, source_reader=forbidden,
                               publication=publication)
                self.assertFalse((root/"out").exists())

    def test_export_and_verify_exact_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prompt = "public fixture"
            index = root/"index.jsonl"
            index.write_bytes(canonical_json({"id": TASK, "problem_type": "bfs",
                "prompt_sha256": sha256_bytes(prompt.encode()), "answer_nodes": [NODE]}) + b"\n")
            digest = sha256_bytes(index.read_bytes())
            for n, (answer, mode, status, score) in enumerate((
                ("earlier text\nFinal Answer: [" + NODE + "]", PUBLISH_FINAL_LINE, "final_line_exported", 1.0),
                ("Final Answer: [" + NODE + "]\n", PUBLISH_FINAL_LINE, "final_line_exported", 0.0),
                ("Final Answer: [arbitrary text]", PUBLISH_FINAL_LINE, "withheld_noncanonical_final_line", 0.0),
                ("Final Answer: [" + NODE + "]", REDACTED_ONLY, "withheld_by_policy", 1.0),
            )):
                with self.subTest(n=n):
                    out = root/str(n)
                    def request(path, payload, key):
                        if path.startswith("/v1/models/"):
                            return {"id": MODEL}
                        if path == "/v1/responses/input_tokens":
                            return {"object": "response.input_tokens", "input_tokens": 255598}
                        return {"status": "completed", "model": MODEL, "service_tier": "default",
                                "usage": {"input_tokens": 255598, "output_tokens": 12, "total_tokens": 255610},
                                "output": [{"type": "message", "role": "assistant", "status": "completed",
                                            "content": [{"type": "output_text", "text": answer}]}]}
                    with patch("model_claim_replay.openai_graphwalks.INDEX_SHA256", digest):
                        result = diagnostic(root/"unused", index, out, approval=APPROVAL, budget="5",
                                            environ={"OPENAI_KEY": "fixture"}, request=request,
                                            publication=mode, source_reader=lambda *_: {TASK: prompt})
                    self.assertEqual(result["scoring_evidence_status"], status)
                    self.assertEqual(result["grade"]["f1"], score)
                    public = out/"public"
                    evidence = public/"scoring-evidence.json"
                    if status != "final_line_exported":
                        self.assertFalse(evidence.exists())
                        continue
                    self.assertNotIn("earlier text", evidence.read_text())
                    verified = verify(public, index, expected_index_sha256=digest)
                    self.assertEqual(verified["grade"], result["grade"])
                    self.assertFalse(verified["provider_execution_authenticated"])
                    self.assertFalse(verified["full_answer_extraction_verified"])
                    old = evidence.read_bytes()
                    evidence.write_bytes(old + b" ")
                    with self.assertRaises(ReplayError):
                        verify(public, index, expected_index_sha256=digest)
                    evidence.write_bytes(old)
                    outcome = public/"outcome.json"
                    tampered = json.loads(outcome.read_bytes())
                    tampered["grade"]["f1"] = 0.5
                    outcome.write_bytes(canonical_json(tampered))
                    with self.assertRaises(ReplayError):
                        verify(public, index, expected_index_sha256=digest)


if __name__ == "__main__":
    unittest.main()
