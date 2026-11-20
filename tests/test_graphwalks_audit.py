"""Adversarial tests of the private execution-journal integrity gate."""

from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from model_claim_replay import graphwalks_runtime as rt
from model_claim_replay.core import ReplayError, canonical_json, sha256_bytes
from model_claim_replay.graphwalks_audit import audit_graphwalks_run


class GraphWalksJournalAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "fake.parquet"
        self.source.write_bytes(b"only a synthetic local data fixture")
        self.source_sha = sha256_bytes(self.source.read_bytes())
        self.index = self.root / "index.jsonl"
        self.source_rows = []
        records = []
        for i in range(200):
            prompt = f"Artificial question {i}"
            nodes = [f"node-{i}"]
            self.source_rows.append({"prompt": prompt, "problem_type": "bfs", "answer_nodes": nodes})
            records.append({"id": f"bfs-row-{i:06d}", "source_row_index": i,
                            "problem_type": "bfs", "prompt_sha256": sha256_bytes(prompt.encode()),
                            "prompt_chars_actual": len(prompt), "answer_nodes": nodes})
        self.index.write_bytes(b"".join(canonical_json(row) + b"\n" for row in records))
        self.index_sha = sha256_bytes(self.index.read_bytes())
        self.plan_path = self.root / "plan.json"
        prompts = rt.verified_prompts(
            self.source, self.index, expected_parquet_sha256=self.source_sha,
            expected_index_sha256=self.index_sha, source_rows=lambda _: iter(self.source_rows),
        )
        plan = rt.build_token_plan(
            self.index, prompts, count_tokens=lambda _: 80, max_tasks=2,
            max_output_tokens=512, expected_index_sha256=self.index_sha,
            expected_parquet_sha256=self.source_sha,
        )
        rt.save_plan(plan, self.plan_path)
        self.run_dir = self.root / "run"
        self.patch_index = patch.object(rt, "INDEX_SHA256", self.index_sha)
        self.patch_data = patch.object(rt, "DATASET_SHA256", self.source_sha)
        self.patch_index.start()
        self.patch_data.start()
        self.addCleanup(self.patch_index.stop)
        self.addCleanup(self.patch_data.stop)

    def generate(self, prompt: str, *_: object) -> SimpleNamespace:
        idx = int(prompt.split()[-1])
        return SimpleNamespace(
            status="completed", output_text=f"Final Answer: [node-{idx}]",
            usage=SimpleNamespace(total_input_tokens=80, total_output_tokens=12),
        )

    def execute_fixture(self) -> None:
        rt.execute_token_plan(
            self.plan_path, self.source, self.index, self.run_dir,
            generate=self.generate, recount_tokens=lambda _: 80,
            allow_paid=True, budget_usd="1", source_rows=lambda _: iter(self.source_rows),
        )

    def audit(self) -> dict:
        return audit_graphwalks_run(self.plan_path, self.index, self.run_dir)

    def change_json(self, path: Path, **changes: object) -> None:
        obj = json.loads(path.read_text())
        obj.update(changes)
        path.write_bytes(canonical_json(obj) + b"\n")

    def test_valid_two_task_journal_is_private_and_self_reported(self) -> None:
        self.execute_fixture()
        audit = self.audit()
        self.assertEqual((audit["planned"], audit["attempted"], audit["completed"]), (2, 2, 2))
        self.assertEqual(audit["unresolved"], 0)
        self.assertFalse(audit["execution_authenticated"])
        self.assertEqual(audit["responses_missing_usage"], 0)
        self.assertTrue(all(len(e["result_sha256"]) == 64 for e in audit["entries"]))
        text = json.dumps(audit)
        self.assertNotIn("Final Answer", text)
        self.assertNotIn("Artificial question", text)
        self.assertNotIn("node-0", text)

    def test_missing_result_is_retained_as_unresolved(self) -> None:
        self.execute_fixture()
        (self.run_dir / "attempts" / "bfs-row-000001.result.json").unlink()
        audit = self.audit()
        self.assertEqual((audit["completed"], audit["unresolved"]), (1, 1))
        self.assertEqual(audit["attempted"], 2)

    def test_result_without_intent_is_rejected(self) -> None:
        self.execute_fixture()
        (self.run_dir / "attempts" / "bfs-row-000000.intent.json").unlink()
        with self.assertRaisesRegex(ReplayError, "without an attempt intent"):
            self.audit()

    def test_modified_intent_or_result_is_rejected(self) -> None:
        self.execute_fixture()
        intent = self.run_dir / "attempts" / "bfs-row-000000.intent.json"
        self.change_json(intent, input_sha256="f" * 64)
        with self.assertRaisesRegex(ReplayError, "intent fails plan binding"):
            self.audit()
        self.run_dir.joinpath("attempts", "bfs-row-000000.intent.json").write_bytes(
            canonical_json({**json.loads(intent.read_text()), "input_sha256":
                json.loads(self.plan_path.read_text())["planned_tasks"][0]["prompt_sha256"]}) + b"\n"
        )
        result = self.run_dir / "attempts" / "bfs-row-000000.result.json"
        self.change_json(result, status="ok", output=123)
        with self.assertRaisesRegex(ReplayError, "lacks valid text"):
            self.audit()

    def test_completed_journal_missing_usage_is_rejected(self) -> None:
        self.execute_fixture()
        path = self.run_dir / "attempts" / "bfs-row-000000.result.json"
        self.change_json(path, usage={})
        with self.assertRaisesRegex(ReplayError, "lacks provider usage"):
            self.audit()

    def test_invalid_usage_and_unexpected_artifacts_are_rejected(self) -> None:
        self.execute_fixture()
        path = self.run_dir / "attempts" / "bfs-row-000000.result.json"
        self.change_json(path, usage={"total_input_tokens": True})
        with self.assertRaisesRegex(ReplayError, "Invalid provider token usage"):
            self.audit()
        self.change_json(path, usage={"total_input_tokens": 80, "total_output_tokens": 12})
        (self.run_dir / "attempts" / "secret-extra-result.json").write_text("{}")
        with self.assertRaisesRegex(ReplayError, "unexpected attempt artifact"):
            self.audit()

    def test_plan_tampering_is_detected(self) -> None:
        self.execute_fixture()
        plan = json.loads(self.plan_path.read_text())
        plan["planned_tasks"][0]["input_tokens"] += 1
        self.plan_path.write_bytes(canonical_json(plan) + b"\n")
        with self.assertRaises(ReplayError):
            self.audit()

    def test_cli_audit_writes_a_score_free_report(self) -> None:
        from model_claim_replay.cli import main
        self.execute_fixture()
        output = self.root / "published-audit.json"
        self.assertEqual(main([
            "audit-graphwalks", "--plan", str(self.plan_path),
            "--index", str(self.index), "--run-dir", str(self.run_dir),
            "--out", str(output),
        ]), 0)
        data = json.loads(output.read_text())
        self.assertEqual(data["completed"], 2)
        self.assertFalse(data["execution_authenticated"])
        self.assertNotIn("Final Answer", output.read_text())
        self.assertNotIn("Artificial question", output.read_text())
        self.assertEqual(main([
            "audit-graphwalks", "--plan", str(self.plan_path),
            "--index", str(self.index), "--run-dir", str(self.run_dir),
            "--out", str(output),
        ]), 2)  # no silent overwrite of prior evidence

    def test_export_rejects_inconsistent_journal(self) -> None:
        self.execute_fixture()
        result_path = self.run_dir / "attempts" / "bfs-row-000000.result.json"
        self.change_json(result_path, id="bfs-row-000123")
        output = self.root / "private-answers.jsonl"
        with self.assertRaisesRegex(ReplayError, "Malformed or unbound"):
            rt.export_private_responses(self.plan_path, self.index, self.run_dir, output)
        self.assertFalse(output.exists())

    def test_old_unchanged_journal_is_auditable(self) -> None:
        self.execute_fixture()
        current = dt.datetime.now(dt.timezone.utc)
        real_datetime = dt.datetime
        # A historical run remains verifiable even if its payment plan expired.
        with patch.object(rt.dt, "datetime") as clock:
            clock.now.return_value = current + dt.timedelta(days=4)
            clock.fromisoformat.side_effect = real_datetime.fromisoformat
            report = self.audit()
        self.assertEqual(report["completed"], 2)


if __name__ == "__main__":
    unittest.main()
