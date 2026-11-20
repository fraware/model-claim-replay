"""Optional smoke test with the *real* Inspect AI runtime and mock model.

The runtime test runs only with the inspect extra installed. It generates a tiny
synthetic Inspect `.eval` log and checks our log-API importer end to end. This
never evaluates a published benchmark or a real frontier model.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from model_claim_replay.inspect_evidence import import_inspect_bundle, verify_inspect_bundle

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec("inspect_ai") is not None, "optional inspect-ai dependency not installed")
class RealInspectRuntimeTests(unittest.TestCase):
    def test_mock_inspect_log_roundtrip(self):
        from inspect_ai import Task, eval, task
        from inspect_ai.dataset import Sample
        from inspect_ai.scorer import Score, Scorer, Target, mean, scorer
        from inspect_ai.solver import TaskState, generate

        @scorer(metrics={"accuracy": [mean()]})
        def golden_answer_scorer() -> Scorer:
            async def grade(state: TaskState, target: Target) -> Score:
                return Score(value={"accuracy": 1.0}, metadata={"result": "pass"})
            return grade

        @task
        def chartography() -> Task:
            return Task(dataset=[Sample(id="synthetic1", input="Name one planet.", target="Mars"),
                                 Sample(id="synthetic2", input="Name one star.", target="Sun")],
                        solver=generate(), scorer=golden_answer_scorer())

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            logs = eval(chartography(), model="mockllm/model", log_dir=str(root / "logs"),
                        display="none", log_samples=True, epochs=1)
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0].status, "success")
            log_path = Path(logs[0].location)
            self.assertTrue(log_path.is_file())
            out = root / "import"
            summary = import_inspect_bundle(ROOT / "claims/claude-fable-5-2-chartography.json", log_path, out)
            self.assertEqual(summary["attempted"], 2)
            self.assertEqual(summary["successes"], 2)
            self.assertEqual(summary["comparison_status"], "not_comparable")
            verified = verify_inspect_bundle(ROOT / "claims/claude-fable-5-2-chartography.json", out,
                                             source_log=log_path)
            self.assertEqual(verified["attempted"], 2)
            self.assertTrue(verified["source_log_checked"])


if __name__ == "__main__":
    unittest.main()
