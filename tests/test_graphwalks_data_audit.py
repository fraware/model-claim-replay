"""Offline data-audit schema and digest validations (without pyarrow dependency)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from graphwalks_data_audit import DataAuditError, main, make_reference_record, validate_source  # noqa: E402


class GraphWalksDataAuditTests(unittest.TestCase):
    def test_optional_retained_source_is_not_part_of_the_default_export(self):
        # Source retrieval and parsing are controlled fixtures. No network access.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for retain in (False, True):
                with self.subTest(retain=retain):
                    output = root / ("retained" if retain else "temporary")
                    verified_paths = []
                    def fake_download(target, **kwargs):
                        verified_paths.append(target)
                        target.write_bytes(b"SYNTHETIC ONLY")
                    record = make_reference_record(
                        0, {
                            "problem_type": "bfs", "prompt": "PUBLIC TEST PROMPT",
                            "answer_nodes": ["node-1"], "prompt_chars": 18,
                        },
                    )
                    args = [
                        "graphwalks_data_audit.py", "--revision", "a"*40,
                        "--sha256", "b"*64, "--size-bytes", "14",
                        "--out", str(output),
                    ] + (["--retain-parquet"] if retain else [])
                    with patch.object(sys, "argv", args), patch(
                        "graphwalks_data_audit.download_checked_parquet",
                        side_effect=fake_download,
                    ), patch(
                        "graphwalks_data_audit.audit_parquet",
                        return_value=([record], {"total_rows": 1, "row_groups": 1}),
                    ):
                        self.assertEqual(main(), 0)
                    self.assertEqual(len(verified_paths), 1)
                    self.assertTrue((output / "graphwalks-bfs-reference-index.jsonl").exists())
                    self.assertTrue((output / "manifest.json").exists())
                    self.assertEqual(
                        (output / "graphwalks_256k_to_1mil.parquet").exists(), retain,
                    )

    def test_manual_workflow_never_uploads_source_or_invokes_generation(self):
        workflow = (ROOT / ".github" / "workflows" /
                    "graphwalks-token-preflight.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}", workflow)
        self.assertIn("--retain-parquet", workflow)
        self.assertIn("claim-replay plan-graphwalks", workflow)
        self.assertNotIn("execute-graphwalks", workflow)
        self.assertIn("path: .runs/private/graphwalks-preflight/token-plan.json", workflow)

    def test_valid_pinned_source(self):
        validate_source("a" * 40, "b" * 64, 296903814)

    def test_bad_revision_and_checksum(self):
        with self.assertRaisesRegex(DataAuditError, "revision"):
            validate_source("main", "b" * 64, 296903814)
        with self.assertRaisesRegex(DataAuditError, "digest"):
            validate_source("a" * 40, "bad", 296903814)

    def test_size_bound(self):
        for size in (0, -1, True, 500_000_000):
            with self.subTest(size=size):
                with self.assertRaisesRegex(DataAuditError, "size"):
                    validate_source("a" * 40, "b" * 64, size)

    def test_bfs_id_and_prompt_identity(self):
        example={"prompt":"PUBLIC SYNTHETIC PROMPT", "answer_nodes":["a"],
                 "problem_type":"bfs", "prompt_chars":23}
        row=make_reference_record(17,example)
        self.assertEqual(row["id"],"bfs-row-000017")
        self.assertEqual(row["answer_nodes"],["a"])
        self.assertEqual(row["prompt_chars_actual"],23)
        self.assertRegex(row["prompt_sha256"],r"^[0-9a-f]{64}$")
        self.assertNotIn("PUBLIC SYNTHETIC PROMPT",str(row))

    def test_parent_problem_is_excluded(self):
        example={"prompt":"prompt","answer_nodes":[],"problem_type":"parents","prompt_chars":6}
        self.assertIsNone(make_reference_record(0,example))

    def test_invalid_node_types_are_rejected(self):
        example={"prompt":"prompt","answer_nodes":[1],"problem_type":"bfs"}
        with self.assertRaisesRegex(DataAuditError, "answer_nodes"):
            make_reference_record(0,example)

    def test_unknown_task_type_rejected(self):
        example={"prompt":"prompt","answer_nodes":[],"problem_type":"dfs"}
        with self.assertRaisesRegex(DataAuditError, "task type"):
            make_reference_record(0,example)


if __name__ == "__main__":
    unittest.main()
