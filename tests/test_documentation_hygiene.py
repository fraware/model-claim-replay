"""Keep repository-relative documentation references and inventory consistent."""
from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\]\(([^)\s]+)\)")


def markdown_targets(text: str):
    """Yield ordinary inline link/image destinations outside fenced code.

    The repository uses inline Markdown links. This deliberately avoids
    pretending to be a complete Markdown parser or external HTTP validator.
    """
    fence = None
    for line in text.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is None:
            yield from (m.group(1) for m in LINK.finditer(line))


class DocumentationHygieneTests(unittest.TestCase):
    def test_local_inline_links_resolve(self):
        paths = sorted(ROOT.glob("*.md")) + sorted((ROOT/"docs").rglob("*.md"))
        paths += sorted((ROOT/"evidence").rglob("*.md"))
        for path in paths:
            for target in markdown_targets(path.read_text(encoding="utf-8")):
                uri = urlsplit(target)
                if uri.scheme or uri.netloc or not uri.path:
                    continue
                with self.subTest(document=str(path.relative_to(ROOT)), target=target):
                    dest = (path.parent / unquote(uri.path)).resolve()
                    self.assertTrue(dest.is_relative_to(ROOT), "Link escapes repository")
                    self.assertTrue(dest.exists(), "Missing local link target")

    def test_workflow_inventory_is_complete(self):
        inventory = (ROOT/"docs/WORKFLOWS.md").read_text()
        listed = set(re.findall(r"\.\./\.github/workflows/([\w.-]+\.yml)\)", inventory))
        actual = {p.name for p in (ROOT/".github/workflows").glob("*.yml")}
        self.assertEqual(listed, actual)

    def test_readme_stays_focused(self):
        readme = (ROOT/"README.md").read_bytes()
        self.assertLess(len(readme), 8000)
        self.assertIn(b"claim-replay demo", readme)
        self.assertIn(b"No publisher aggregate has been reproduced", readme)


if __name__ == "__main__":
    unittest.main()
