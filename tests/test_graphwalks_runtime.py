"""Offline adversarial tests for GraphWalks source matching and billable-call gates."""

from __future__ import annotations

import hashlib
import datetime as dt
import inspect
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

    def test_budget_plan_expiration_blocks_paid_execution(self):
        for created in (
            (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)).isoformat(),
            (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)).isoformat(),
        ):
            with self.subTest(created=created):
                plan = self._plan(max_tasks=1)
                plan["created_utc"] = created
                with self.assertRaisesRegex(ReplayError, "stale or future-dated"):
                    self._run(plan, lambda *_: self.fail("Paid request sent with expired plan"))
                (self.root / "plan.json").unlink()

    def test_invalid_plan_pricing_blocks_paid_execution(self):
        plan = self._plan(max_tasks=1)
        plan["pricing"]["tier"] = "priority"
        with self.assertRaisesRegex(ReplayError, "pricing differs"):
            self._run(plan, lambda *_: self.fail("Paid request sent with wrong tier"))

    def test_official_google_sdk_supports_token_counting(self):
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            self.skipTest("Optional Google SDK is absent")
        client = genai.Client(
            api_key="offline-contract-test-key",
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1)
            ),
        )
        try:
            signature = inspect.signature(client.models.count_tokens)
            self.assertIn("model", signature.parameters)
            self.assertIn("contents", signature.parameters)
        finally:
            client.close()

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

    def test_provider_zero_count_and_oversized_requested_cohort_are_refused(self):
        with self.assertRaisesRegex(ReplayError, "zero input tokens"):
            self._plan(max_tasks=1, count=lambda _: 0)
        with self.assertRaisesRegex(ReplayError, "exceeds the verified reference cohort"):
            self._plan(max_tasks=201)

    def test_tampered_plan_aggregate_cannot_authorize_execution(self):
        for key, bad_value in (
            ("planned_count", 200),
            ("maximum_reserved_cost_usd", "0"),
            ("blocked_for_context", 200),
            ("context_limit", 100),
            ("comparison_status", "reproduced"),
        ):
            with self.subTest(key=key):
                plan = self._plan(max_tasks=1)
                plan[key] = bad_value
                with self.assertRaises(ReplayError):
                    self._run(plan, lambda *_: self.fail("No request with forged plan"))
                (self.root / "plan.json").unlink()

    def test_completed_generation_without_usage_is_not_a_scored_success(self):
        plan = self._plan(max_tasks=1)
        result = self._run(
            plan,
            lambda *_: SimpleNamespace(
                status="completed", output_text="Final Answer: [node-0]", usage=None,
            ),
        )
        self.assertEqual(result["successful_attempts"], 0)
        stored = json.loads(
            (self.root / "private-run" / "attempts" / "bfs-row-000000.result.json").read_text()
        )
        self.assertEqual(stored["status"], "error")
        self.assertNotIn("output", stored)

    def test_stratified_task_selection_prevents_short_context_only_pilot(self):
        plan = self._plan(max_tasks=20)
        task_ids = [task["id"] for task in plan["planned_tasks"]]
        self.assertEqual(plan["selection_policy"], rt.SELECTION_POLICY)
        self.assertEqual(plan["selection_counts"], {
            "short_context": 10, "long_context": 10,
        })
        self.assertEqual(task_ids, [
            *[f"bfs-row-{i:06d}" for i in range(0, 100, 10)],
            *[f"bfs-row-{i:06d}" for i in range(100, 200, 10)],
        ])
        compact = self._plan(max_tasks=5)
        self.assertEqual(compact["selection_counts"], {
            "short_context": 3, "long_context": 2,
        })
        self.assertEqual(
            [task["id"] for task in compact["planned_tasks"]],
            ["bfs-row-000000", "bfs-row-000033", "bfs-row-000066",
             "bfs-row-000100", "bfs-row-000150"],
        )

    def test_tampered_balanced_cohort_is_not_executable(self):
        for modify in (
            lambda plan: plan["planned_tasks"].__setitem__(
                1, dict(plan["planned_tasks"][0])
            ),
            lambda plan: plan.__setitem__("selection_policy", "arbitrary"),
            lambda plan: plan["selection_counts"].__setitem__("long_context", 0),
        ):
            plan = self._plan(max_tasks=2)
            modify(plan)
            with self.assertRaises(ReplayError):
                self._run(plan, lambda *_: self.fail("Modified cohort sent to provider"))
            (self.root / "plan.json").unlink()

    def test_context_overflow_is_marked_and_blocks_execution(self):
        plan = self._plan(max_tasks=2, count=lambda _: rt.CONTEXT_LIMIT, max_output_tokens=512)
        self.assertEqual(plan["blocked_for_context"], 2)
        with self.assertRaisesRegex(ReplayError, "out-of-context"):
            self._run(plan, lambda *_: 1/0)

    def test_invalid_max_output_and_fake_counts_blocked(self):
        for output in (True, 0, -1, 65537, 1000000):
            with self.subTest(output=output):
                with self.assertRaises(ReplayError):
                    self._plan(max_output_tokens=output)
        for value in (1.2, -1, True, None):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ReplayError, "token count"):
                    self._plan(count=lambda _: value)

    def test_foreground_provider_limit_is_explicitly_reserved(self):
        plan = self._plan(max_tasks=1, max_output_tokens=65536)
        self.assertEqual(plan["max_output_tokens"], 65536)
        self.assertEqual(
            plan["planned_tasks"][0]["maximum_reserved_cost_usd"],
            str(rt._usd(100, 65536)),
        )
        self.assertEqual(plan["blocked_for_context"], 0)

    def test_journal_creation_is_atomic_and_never_overwrites(self):
        """Interrupted persistence must not publish truncated intent files."""
        attempts = self.root / "private-run" / "attempts"
        attempts.mkdir(parents=True)
        intent = attempts / "bfs-row-000000.intent.json"
        first = {"id": "bfs-row-000000", "status": "intended"}

        # Failure before the hard-link publication leaves no journal entry
        # for the independent auditor to mistake for a billable request.
        with patch.object(rt.os, "link", side_effect=OSError("injected publish failure")):
            with self.assertRaisesRegex(OSError, "injected publish"):
                rt._write_exclusive(intent, first)
        self.assertFalse(intent.exists())
        self.assertEqual(list(attempts.iterdir()), [])
        self.assertEqual(list(attempts.parent.glob(".graphwalks-journal-*")), [])

        # A fatal interruption during serialization leaves the same state.
        with patch.object(rt, "canonical_json", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                rt._write_exclusive(intent, first)
        self.assertFalse(intent.exists())
        self.assertEqual(list(attempts.parent.glob(".graphwalks-journal-*")), [])

        rt._write_exclusive(intent, first)
        original = intent.read_bytes()
        self.assertEqual(json.loads(original), first)

        # A duplicate request or result is rejected without changing bytes.
        with self.assertRaises(FileExistsError):
            rt._write_exclusive(intent, {"id": "bfs-row-000000", "status": "replay"})
        self.assertEqual(intent.read_bytes(), original)
        self.assertEqual(list(attempts.parent.glob(".graphwalks-journal-*")), [])

    def test_second_paid_runner_for_same_output_fails_closed(self):
        """A second runner cannot advance another task during an active run."""
        if rt.os.name != "posix":
            self.skipTest("POSIX advisory locking is needed for paid runs")
        plan = self._plan(max_tasks=2)
        out = self.root / "private-run"
        with rt._exclusive_paid_run(out):
            with self.assertRaisesRegex(ReplayError, "already active"):
                self._run(
                    plan, lambda *_: self.fail("Duplicate runner sent an API call"),
                    out=out,
                )
            self.assertFalse((out / "attempts").exists())

        # A released lock permits the originally authorized run to proceed.
        result = self._run(
            plan,
            lambda *_: SimpleNamespace(
                status="completed", output_text="Final Answer: [node-0]",
                usage=SimpleNamespace(
                    total_input_tokens=100, total_output_tokens=8,
                ),
            ),
            out=out,
        )
        self.assertEqual(result["new_requests"], 2)
        self.assertTrue((out / "attempts" / "bfs-row-000000.intent.json").is_file())

    def test_paid_runner_lock_is_released_after_abrupt_interruption(self):
        """Crash-style BaseException does not strand a persistent lock."""
        if rt.os.name != "posix":
            self.skipTest("POSIX advisory locking is needed for paid runs")
        out = self.root / "private-run"
        with self.assertRaises(KeyboardInterrupt):
            with rt._exclusive_paid_run(out):
                raise KeyboardInterrupt("simulated termination")
        with rt._exclusive_paid_run(out):
            self.assertFalse(out.exists())

    def test_resumption_audits_corrupt_prior_results_before_new_calls(self):
        """No extra paid task follows an invalid previous provider result."""
        plan = self._plan(max_tasks=2)
        one_request_budget = plan["planned_tasks"][0]["maximum_reserved_cost_usd"]
        self._run(
            plan,
            lambda *_: SimpleNamespace(
                status="completed", output_text="Final Answer: [node-0]",
                usage=SimpleNamespace(
                    total_input_tokens=100, total_output_tokens=10,
                ),
            ),
            budget=one_request_budget,
        )
        result_path = (
            self.root / "private-run" / "attempts"
            / "bfs-row-000000.result.json"
        )
        result = json.loads(result_path.read_text())
        result["usage"].pop("total_input_tokens")
        result_path.write_text(json.dumps(result))

        attempted = []
        with self.assertRaisesRegex(ReplayError, "lacks provider usage"):
            self._run(
                plan, lambda *args: attempted.append(args), budget="1",
            )
        self.assertEqual(attempted, [])
        self.assertFalse(
            (self.root / "private-run" / "attempts"
             / "bfs-row-000100.intent.json").exists()
        )

    def test_resumption_refuses_extraneous_journal_files(self):
        """Unexpected prior artifacts cannot be ignored when billing resumes."""
        plan = self._plan(max_tasks=2)
        one_request_budget = plan["planned_tasks"][0]["maximum_reserved_cost_usd"]
        self._run(plan, lambda *_: 1 / 0, budget=one_request_budget)
        extra = self.root / "private-run" / "attempts" / "untracked.json"
        extra.write_text("{}")
        with self.assertRaisesRegex(ReplayError, "unexpected attempt artifact"):
            self._run(
                plan, lambda *_: self.fail("Paid request bypassed audit"),
                budget="1",
            )
        self.assertFalse(
            (self.root / "private-run" / "attempts"
             / "bfs-row-000100.intent.json").exists()
        )

    def test_abrupt_request_interruption_preserves_auditable_intent(self):
        from model_claim_replay.graphwalks_audit import audit_graphwalks_run

        plan = self._plan(max_tasks=2)
        def interrupt(*_):
            raise KeyboardInterrupt("simulated abrupt process stop")

        # A BaseException interrupts the command after its intent was created,
        # but before a result was persisted. No API is contacted by this test.
        with self.assertRaises(KeyboardInterrupt):
            self._run(plan, interrupt)
        intent = self.root / "private-run" / "attempts" / "bfs-row-000000.intent.json"
        result = self.root / "private-run" / "attempts" / "bfs-row-000000.result.json"
        self.assertTrue(intent.is_file())
        self.assertFalse(result.exists())

        with patch.object(rt, "INDEX_SHA256", self.index_sha), patch.object(
            rt, "DATASET_SHA256", self.source_sha,
        ):
            audit = audit_graphwalks_run(
                self.root / "plan.json", self.index, self.root / "private-run",
            )
        self.assertEqual(
            (audit["attempted"], audit["unresolved"], audit["not_attempted"]),
            (1, 1, 1),
        )
        self.assertEqual(audit["entries"][0]["status"], "unresolved")
        self.assertNotIn("Synthetic GraphWalks", json.dumps(audit))
        self.assertNotIn("answer_nodes", json.dumps(audit))

        calls = []
        def next_task_only(prompt, *_):
            calls.append(prompt)
            return SimpleNamespace(
                status="completed", output_text="Final Answer: [node-100]",
                usage=SimpleNamespace(total_input_tokens=100, total_output_tokens=9),
            )
        resumed = self._run(plan, next_task_only)
        self.assertEqual(resumed["new_requests"], 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], "Synthetic GraphWalks task 100")
        self.assertEqual(resumed["unresolved_attempts_without_results"], 1)

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
            return SimpleNamespace(
                status="completed",
                output_text=f"Final Answer: [node-{index}]",
                usage=SimpleNamespace(total_input_tokens=100, total_output_tokens=12),
            )
        self._run(plan, generate)
        responses=self.root/"recorded.jsonl"
        with patch.object(rt, "INDEX_SHA256", self.index_sha), patch.object(rt, "DATASET_SHA256", self.source_sha):
            rt.export_private_responses(self.root/"plan.json",self.index,self.root/"private-run",responses)
        report=score_recorded_bfs(self.index,responses,expected_index_sha256=self.index_sha,
                                  dataset_revision=rt.DATASET_REVISION)
        self.assertEqual(report["graded"],2)
        self.assertEqual(report["missing"],198)
        self.assertIsNone(report["mean_f1"])
        self.assertEqual(report["scored_subset_mean_f1_diagnostic"],1)
        with self.assertRaisesRegex(ReplayError,"already exists"):
            with patch.object(rt, "INDEX_SHA256", self.index_sha), patch.object(rt, "DATASET_SHA256", self.source_sha):
                rt.export_private_responses(self.root/"plan.json",self.index,self.root/"private-run",responses)

if __name__ == "__main__":
    unittest.main()
