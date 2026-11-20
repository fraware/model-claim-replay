"""Registry regression tests for externally published model claims.

They verify source records, not any alleged model performance.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from model_claim_replay.cli import claim_listing
from model_claim_replay.core import ReplayError, load_claim, task_data

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "claims" / "gemini-4-neon-graphwalks-bfs-long.json"


class PublishedClaimRegistryTests(unittest.TestCase):
    def test_public_model_claim_registry_includes_graphwalks(self):
        registry = claim_listing(ROOT / "claims")
        self.assertIn("gemini-4-neon-graphwalks-bfs-long",
                      {entry["id"] for entry in registry})

    def test_graphwalks_claim_is_source_registered_and_not_executable(self):
        claim = load_claim(CANDIDATE)
        self.assertEqual(claim["reported_score"], 0.952)
        self.assertEqual(claim["benchmark"]["expected_tasks"], 200)
        self.assertEqual(claim["kind"], "published")
        self.assertEqual(claim["protocol"]["mode"], "external")
        self.assertIsNone(claim["benchmark"]["sha256"])
        with self.assertRaisesRegex(ReplayError, "no pinned dataset digest"):
            task_data(claim, ROOT / "examples" / "demo-tasks.jsonl")


if __name__ == "__main__":
    unittest.main()
