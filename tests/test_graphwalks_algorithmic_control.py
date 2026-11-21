"""Offline algorithmic graph-control tests on source-format synthetic prompts."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from model_claim_replay.core import ReplayError
from model_claim_replay.graphwalks import grade_response

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from graphwalks_algorithmic_control import solve_bfs_prompt  # noqa: E402


class DeterministicControlTests(unittest.TestCase):
    def source(self, edges: str, instruction: str, examples: str = "") -> str:
        return (
            "You will be given a graph as a list of directed edges.\n"
            + examples
            + "The graph has the following edges:\n"
            + edges
            + "\nOperation:\n" + instruction + "\n"
        )

    def test_exact_depth_with_no_revisits_and_directed_edges(self):
        prompt = self.source(
            "a -> b\na -> c\nb -> d\nc -> d\nd -> a\nd -> e",
            "Perform a BFS from node a with depth 2.",
        )
        response, audit = solve_bfs_prompt(prompt)
        self.assertEqual(grade_response(response, ["d"])["f1"], 1.0)
        self.assertEqual(audit["depth"], 2)
        self.assertEqual(audit["edge_count"], 6)

    def test_example_edges_do_not_contaminate_actual_graph(self):
        example = (
            "<begin example>\nThe graph has the following edges:\n"
            "a -> z\nOperation:\nPerform a BFS from node a with depth 1.\n"
            "<end example>\n"
        )
        prompt = self.source("a -> b\nb -> c", "Perform a BFS from node a with depth 1.", example)
        response, _ = solve_bfs_prompt(prompt)
        self.assertEqual(grade_response(response, ["b"])["f1"], 1.0)

    def test_corrected_2026_exact_depth_instruction(self):
        prompt = self.source(
            "a -> b\nb -> c\nc -> a",
            "Perform a BFS from node a and return only the nodes at exactly depth 2 (not nodes at intermediate depths).",
        )
        response, _ = solve_bfs_prompt(prompt)
        self.assertEqual(grade_response(response, ["c"])["f1"], 1.0)

    def test_depth_zero_empty_frontier_rule(self):
        prompt = self.source("a -> b", "Perform a BFS from node a with depth 0.")
        response, _ = solve_bfs_prompt(prompt)
        self.assertEqual(grade_response(response, [])["f1"], 0.0)
        self.assertIn("Final Answer: [a]", response)

    def test_reject_ambiguous_or_partial_graph(self):
        cases = [
            self.source("a -> b\nUNEXPECTED LINE", "Perform a BFS from node a with depth 1."),
            self.source("a -> b", "Perform BFS from a"),
            self.source("a -> b", "Perform a BFS from node z with depth 1."),
            self.source("a -> b", "Perform a BFS from node a with depth 1.\nOperation:\nPerform a BFS from node a with depth 2."),
        ]
        for prompt in cases:
            with self.subTest(prompt=prompt[-50:]), self.assertRaises(ReplayError):
                solve_bfs_prompt(prompt)


if __name__ == "__main__":
    unittest.main()