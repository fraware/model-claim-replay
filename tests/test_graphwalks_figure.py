"""Check the shareable figure against the pinned provider receipt."""
from __future__ import annotations

import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "website"
NS = {"s": "http://www.w3.org/2000/svg"}


class GraphWalksFigureTests(unittest.TestCase):
    def test_geometry_and_labels_match_original_receipt(self) -> None:
        receipt = json.loads((ROOT / "graphwalks-gemini-feasibility.json").read_bytes())
        tree = ET.parse(ROOT / "graphwalks-input-feasibility.svg")
        counts = receipt["input_token_counts_in_pinned_index_order"]
        limit = receipt["provider_input_token_limit"]
        self.assertEqual(len(counts), 200)
        self.assertFalse(receipt["model_generation_performed"])
        self.assertFalse(receipt["published_claim_reproduced"])

        def x(token_count: int | float) -> float:
            return 90 + 1020 * token_count / 1_500_000

        threshold = tree.find(".//s:line[@id='input-limit']", NS)
        self.assertIsNotNone(threshold)
        for field in ("x1", "x2"):
            self.assertAlmostEqual(float(threshold.attrib[field]), x(limit), places=3)
        self.assertIn(f"{limit:,}", tree.find(".//s:text[@id='limit-label']", NS).text)
        for index, band in enumerate((
            [n for n in counts if n <= limit],
            [n for n in counts if n > limit],
        )):
            with self.subTest(group=index):
                group = tree.find(f".//s:g[@id='group-{index}']", NS)
                self.assertIsNotNone(group)
                self.assertEqual(int(group.attrib["data-count"]), len(band))
                self.assertEqual(int(group.attrib["data-min"]), min(band))
                self.assertEqual(int(group.attrib["data-max"]), max(band))
                interval = group.find("s:line[@class='range']", NS)
                self.assertAlmostEqual(float(interval.attrib["x1"]), x(min(band)), places=3)
                self.assertAlmostEqual(float(interval.attrib["x2"]), x(max(band)), places=3)
                self.assertAlmostEqual(float(group.find("s:circle", NS).attrib["cx"]),
                                       x((min(band) + max(band)) / 2), places=3)
                self.assertIn(f"{min(band):,}–{max(band):,}", "".join(group.itertext()))
        text = "".join(tree.getroot().itertext())
        self.assertIn("100 of 200 candidate prompts", text)
        self.assertIn("No model generation", text)
        self.assertIn("publisher-selected cohort is unverified", text)
        self.assertIn("neither confirmed nor refuted", text)
        self.assertIn(receipt["provider_run"].split("https://", 1)[1], text)


if __name__ == "__main__":
    unittest.main()
