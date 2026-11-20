"""Catch accidentally committed connector placeholders and broken public paths."""
from __future__ import annotations

import unittest
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = "The requested file reference is not currently visible."


class RepositoryIntegrityTests(unittest.TestCase):
    def test_no_placeholder_file_replaced_actual_source(self):
        for directory in (ROOT / "website", ROOT / "scripts", ROOT / "src", ROOT / "docs"):
            for path in directory.rglob("*"):
                if path.is_file() and path.suffix in (".html", ".css", ".js", ".json", ".py", ".md", ".xml"):
                    with self.subTest(path=path):
                        self.assertNotIn(PLACEHOLDER, path.read_text(encoding="utf-8"))

    def test_sitemap_links_to_actual_site_pages(self):
        root = ElementTree.parse(ROOT / "website" / "sitemap.xml").getroot()
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [x.text for x in root.findall("s:url/s:loc", ns)]
        self.assertEqual(locs, [
            "https://fraware.github.io/model-claim-replay/",
            "https://fraware.github.io/model-claim-replay/graphwalks.html",
        ])
        self.assertTrue((ROOT / "website" / "graphwalks.html").is_file())

if __name__ == "__main__":
    unittest.main()
