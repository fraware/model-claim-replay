"""Offline adversarial tests for GraphWalks source matching and billable-call gates."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from model_claim_replay.core import ReplayError, canonical_json, sha256_bytes
from model_claim_replay.graphwalks import score_recorded_bfs
from model_claim_replay import graphwalks_runtime as rt


class RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "candidate.parquet"
        self.source.write_bytes(b"fixture public Parquet bytes")
        self.source_sha = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.index = self.root / "candidate.jsonl"
        self.source_rows = []
        self.items = []
        for i in range(200):
            prompt = f"Synthetic GraphWalks task {i}"
            answer = [f"node-{i}"]
            self.source_rows.append({"prompt": prompt, "answer_nodes": answer, "problem_type": "bfs"})
            self.items.append({
                "id": f"bfs-row-{i:06d}", "source_row_index": i,
                "problem_type": "bfs", "answer_nodes": answer,
                "prompt_chars_actual": len(prompt),
                "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
            })
        self.index.write_bytes(b"".join(canonical_json(item) + b"\n" for item in self.items))
        self.index_sha = sha256_bytes(self.index.read_bytes())
        self.row_source = lambda _: iter(self.source_rows)
        self.prompts = rt.verified_prompts(
            self.source, self.index,
            expected_parquet_sha256=self.source_sha,
            expected_index_sha256=self.index_sha,
            source_rows=self.row_source,
        )

    def _plan(self, *, max_tasks: int = 2, count=lambda _: 100,
              max_output_tokens: int = 512) -> dict:
        return rt.build_token_plan(
            self.index, self.prompts, count_tokens=count,
            max_tasks=max_tasks, max_output_tokens=max_output_tokens,
            expected_index_sha256=self.index_sha,
            expected_parquet_sha256=self.source_sha,
        )

    def _run(self, plan: dict, generate, *, budget: str = "1.00", out=None):
        plan_path = self.root / "plan.json"
        if not plan_path.exists():
            rt.save_plan(plan, plan_path)
        out = out or self.root / "private-run"
        with patch.object(rt, "INDEX_SHA256", self.index_sha), patch.object(rt, "DATASET_SHA256", self.source_sha):
            return rt.execute_token_plan(
                plan_path, self.source, self.index, out, generate=generate,
                allow_paid=True, budget_usd=budget, source_rows=self.row_source,
                recount_tokens=lambda _: 100,
            )

    def test_gemini_interaction_is_stateless_and_single_response(self):
        calls = []
        def fake_create(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(status="completed", output_text="Final Answer: [node-0]")
        client = SimpleNamespace(interactions=SimpleNamespace(create=fake_create))
        result = rt.request_gemini_interaction(
            client, "Synthetic prompt", rt.MODEL, 16384, "xhigh",
        )
        self.assertEqual(result.status, "completed")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], {
            "model": rt.MODEL,
            "input": "Synthetic prompt",
            "generation_config": {
                "thinking_level": "xhigh",
                "max_output_tokens": 16384,
            },
            "background": False,
            "stream": False,
            "store": False,
            "automatic_continuation": False,
        })
        with self.assertRaises(ReplayError):
            rt.request_gemini_interaction(client, "p", "other-model", 16384, "xhigh")
        with self.assertRaises(ReplayError):
            rt.request_gemini_interaction(client, "p", rt.MODEL, True, "xhigh")
        self.assertEqual(len(calls), 1)

    def test_continuation_required_does_not_become_scored_success(self):
        # Explicit one-hop requests must never treat partial decodes as answers.
        plan = self._plan(max_tasks=1)
        report = self._run(
            plan,
            lambda *_: SimpleNamespace(
                status="requires_continuation",
                output_text="Final Answer: [node-0]",
                continuation_token="PRIVATE_CONTINUATION_TOKEN",
                usage=SimpleNamespace(total_input_tokens=100, total_output_tokens=512),
            ),
        )
        self.assertEqual(report["new_requests"], 1)
        self.assertEqual(report["successful_attempts"], 0)
        result = json.loads(
            (self.root / "private-run" / "attempts" / "bfs-row-000000.result.json").read_text()
        )
        self.assertEqual(result["status"], "error")
        self.assertNotIn("output", result)
        self.assertNotIn("PRIVATE_CONTINUATION_TOKEN", json.dumps(result))
        again = self._run(plan, lambda *_: self.fail("Repeated a billable call"))
        self.assertEqual(again["new_requests"], 0)

    def test_actual_pyarrow_parquet_roundtrip(self):
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow not installed locally")
        target = self.root / "real-synthetic.parquet"
        pq.write_table(pa.Table.from_pylist(self.source_rows), target)
        parsed = rt.verified_prompts(
            target, self.index, expected_parquet_sha256=rt.sha256_file(target),
            expected_index_sha256=self.index_sha,
        )
        self.assertEqual(parsed, self.prompts)

    def test_source_bytes_are_bound_to_prompt_and_answers(self):
        self.assertEqual(len(self.prompts), 200)
        changed = [dict(row) for row in self.source_rows]
        changed[2]["prompt"] = "altered prompt"
        with self.assertRaisesRegex(ReplayError, "disagree"):
            rt.verified_prompts(
                self.source, self.index, expected_parquet_sha256=self.source_sha,
                expected_index_sha256=self.index_sha, source_rows=lambda _: iter(changed),
            )
        changed = [dict(row) for row in self.source_rows]
        changed[10]["answer_nodes"] = ["different"]
        with self.assertRaisesRegex(ReplayError, "disagree"):
            rt.verified_prompts(
                self.source, self.index, expected_parquet_sha256=self.source_sha,
                expected_index_sha256=self.index_sha, source_rows=lambda _: iter(changed),
            )

    def test_source_hash_failure_precedes_row_parsing(self):
        with self.assertRaisesRegex(ReplayError, "SHA-256"):
            rt.verified_prompts(self.source, self.index,
                                expected_parquet_sha256="0"*64,
                                expected_index_sha256=self.index_sha,
                                source_rows=lambda _: 1/0)

    def test_token_counts_are_actual_callable_results(self):
        seen = []
        plan = self._plan(max_tasks=3, count=lambda text: seen.append(text) or 123)
        self.assertEqual(plan["planned_count"], 3)
        self.assertEqual(len(seen), 3)
        self.assertEqual(plan["planned_tasks"][0]["input_tokens"], 123)
        self.assertEqual(plan["blocked_for_context"], 0)
        self.assertEqual(plan["maximum_reserved_cost_usd"], str(rt._usd(369, 1536)))
        self.assertNotIn("Synthetic GraphWalks", json.dumps(plan))
        self.assertIn("not_comparable", json.dumps(plan))

    def test_context_overflow_is_marked_and_blocks_execution(self):
        plan = self._plan(max_tasks=2, count=lambda _: rt.CONTEXT_LIMIT, max_output_tokens=512)
        self.assertEqual(plan["blocked_for_context"], 2)
        with self.assertRaisesRegex(ReplayError, "out-of-context"):
            self._run(plan, lambda *_: 1/0)

    def test_invalid_max_output_and_fake_counts_blocked(self):
        for output in (True, 0, -1, 65537):
            with self.subTest(output=output):
                with self.assertRaises(ReplayError):
                    self._plan(max_output_tokens=output)
        for value in (1.2, -1, True, None):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ReplayError, "token count"):
                    self._plan(count=lambda _: value)

    def test_budget_prevents_second_billable_request(self):
        plan = self._plan()
        per_task = float(plan["planned_tasks"][0]["maximum_reserved_cost_usd"])
        seen = []
        def generate(prompt, model, max_tokens, thinking):
            seen.append((prompt, model, max_tokens, thinking))
            return SimpleNamespace(
                status="completed", output_text="Final Answer: [node-0]",
                usage=SimpleNamespace(total_input_tokens=100,
                                      total_output_tokens=1,
                                      total_thought_tokens=10),
            )
        report = self._run(plan, generate, budget=f"{per_task:.8f}")
        self.assertEqual(report["new_requests"], 1)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][1:], ("gemini-4-neon", 512, "xhigh"))
        self.assertFalse(any("prompt" in x for x in json.loads((self.root/"private-run"/"run.json").read_text())))
        report2 = self._run(plan, generate, budget="1")
        self.assertEqual(report2["new_requests"], 1)
        self.assertEqual(len(seen), 2)
        self.assertEqual(report2["successful_attempts"], 2)
        report3 = self._run(plan, generate, budget="1")
        self.assertEqual(report3["new_requests"], 0)
        self.assertEqual(len(seen), 2)

    def test_interrupted_request_is_not_repeated(self):
        plan = self._plan(max_tasks=1)
        self._run(plan, lambda *_: SimpleNamespace(status="completed", output_text="Final Answer: [node-0]", usage=None))
        prior = self.root / "private-run" / "attempts" / "bfs-row-000000.result.json"
        prior.unlink()  # Simulates process interruption after provider received request.
        def fail(*_):
            raise AssertionError("Duplicate paid call attempted")
        result = self._run(plan, fail)
        self.assertEqual(result["new_requests"], 0)
        self.assertEqual(result["unresolved_attempts_without_results"], 1)

    def test_errors_consume_budget_and_remain_unscored(self):
        plan = self._plan(max_tasks=1)
        self._run(plan, lambda *_: 1/0)
        result = json.loads((self.root / "private-run" / "attempts" / "bfs-row-000000.result.json").read_text())
        self.assertEqual(result["status"], "error")
        self.assertNotIn("output", result)
        with self.assertRaisesRegex(ReplayError, "reservations exceed"):
            self._run(plan, lambda *_: 1/0, budget="0.000001")

    def test_budget_is_a_strict_positive_decimal(self):
        for amount in ("NaN", "Infinity", "0", "-1", "broken"):
            with self.subTest(amount=amount):
                with self.assertRaises(ReplayError):
                    self._run(self._plan(max_tasks=1), lambda *_: 1/0, budget=amount)

    def test_paid_generation_requires_explicit_authorization(self):
        plan=self._plan(max_tasks=1)
        path=self.root/"plan.json"
        rt.save_plan(plan,path)
        with self.assertRaisesRegex(ReplayError,"--execute-paid"):
            rt.execute_token_plan(path,self.source,self.index,self.root/"private-run",
                                  generate=lambda *_: 1/0,recount_tokens=lambda _: 100,
                                  allow_paid=False,budget_usd="100")

    def test_recount_mismatch_fails_before_paid_request(self):
        plan = self._plan(max_tasks=1)
        plan_path=self.root/"plan.json"
        rt.save_plan(plan,plan_path)
        with patch.object(rt,"INDEX_SHA256",self.index_sha), patch.object(rt,"DATASET_SHA256",self.source_sha):
            with self.assertRaisesRegex(ReplayError,"differs from the approved plan"):
                rt.execute_token_plan(plan_path,self.source,self.index,self.root/"private-run",
                    generate=lambda *_: 1/0,recount_tokens=lambda _: 999,
                    allow_paid=True,budget_usd="1",source_rows=self.row_source)
        self.assertFalse((self.root/"private-run"/"attempts"/"bfs-row-000000.intent.json").exists())

    def test_private_export_preserves_raw_response_for_offline_grade(self):
        plan=self._plan(max_tasks=2)
        def generate(prompt, *_):
            index=int(prompt.split()[-1])
            return SimpleNamespace(status="completed", output_text=f"Final Answer: [node-{index}]",usage=None)
        self._run(plan, generate)
        responses=self.root/"recorded.jsonl"
        rt.export_private_responses(self.root/"plan.json",self.root/"private-run",responses)
        report=score_recorded_bfs(self.index,responses,expected_index_sha256=self.index_sha,
                                  dataset_revision=rt.DATASET_REVISION)
        self.assertEqual(report["graded"],2)
        self.assertEqual(report["missing"],198)
        self.assertIsNone(report["mean_f1"])
        self.assertEqual(report["scored_subset_mean_f1_diagnostic"],1)
        with self.assertRaisesRegex(ReplayError,"already exists"):
            rt.export_private_responses(self.root/"plan.json",self.root/"private-run",responses)

if __name__ == "__main__":
    unittest.main()
