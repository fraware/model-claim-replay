"""Offline data-audit schema and digest validations (without pyarrow dependency)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from graphwalks_data_audit import DataAuditError, make_reference_record, validate_source  # noqa: E402


class GraphWalksDataAuditTests(unittest.TestCase):
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
