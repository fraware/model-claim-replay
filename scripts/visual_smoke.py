"""Offline Chromium interaction smoke tests for the two static product pages.

Use: python -m pip install playwright
     python scripts/visual_smoke.py --site website --out .runs/previews

The test uses Chromium installed on the host; no website network navigation or
third-party services are needed. It injects the committed source-data receipt
into fetch for deterministic testing. This is browser UI QA, not provider QA.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def run(site: Path, out: Path, browser_path: str | None = None) -> None:
    """Exercise the real local JS/CSS on desktop and mobile, collecting screenshots."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Install playwright to run browser QA") from exc
    site = site.resolve(strict=True)
    out.mkdir(parents=True, exist_ok=True)
    graph_data = json.loads((site / "graphwalks-audit.json").read_text(encoding="utf-8"))
    with sync_playwright() as api:
        args = ["--no-sandbox"]
        settings = {"headless": True, "args": args}
        if browser_path:
            settings["executable_path"] = browser_path
        browser = api.chromium.launch(**settings)
        try:
            for label, width, height in (("desktop", 1440, 900), ("mobile", 390, 844)):
                for name in ("index", "graphwalks"):
                    page = browser.new_page(viewport={"width": width, "height": height})
                    errors: list[str] = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.set_content((site / f"{name}.html").read_text(encoding="utf-8"))
                    stylesheet = "style.css" if name == "index" else "graphwalks.css"
                    script = "app.js" if name == "index" else "graphwalks.js"
                    page.add_style_tag(content=(site / stylesheet).read_text(encoding="utf-8"))
                    if name == "graphwalks":
                        page.evaluate(
                            "(data) => { window.fetch = async () => ({ok: true, json: async () => data}); }",
                            graph_data,
                        )
                    page.add_script_tag(content=(site / script).read_text(encoding="utf-8"))
                    if name == "graphwalks":
                        page.wait_for_function("document.querySelectorAll('button.task-dot').length === 200")
                        assert page.locator("button.task-dot").count() == 200
                        page.locator('button.filter[data-filter="long"]').click()
                        assert page.locator("button.task-dot").count() == 100
                        page.locator('button.filter[data-filter="short"]').click()
                        assert page.locator("button.task-dot").count() == 100
                        page.locator('button.filter[data-filter="all"]').click()
                        page.locator("button.task-dot").first.click()
                        assert "SELECTED SOURCE RECORD" in page.locator("#record").inner_text()
                        page.locator("#task-search").fill("bfs-row-000100")
                        assert page.locator("button.task-dot").count() == 1
                        page.locator("#task-search").fill("")
                        assert page.locator("button.task-dot").count() == 200
                    else:
                        assert page.locator(".claim-row").count() == 3
                        page.locator(".claim-row").nth(1).click()
                        assert page.locator("#claim-detail").is_visible()
                        page.locator(".filter[data-filter='published']").click()
                        assert page.locator(".claim-row").count() == 2
                        page.locator(".filter[data-filter='all']").click()
                    assert not errors, f"{name} browser errors: {errors}"
                    overflow = page.evaluate("document.documentElement.scrollWidth - innerWidth")
                    assert overflow <= 1, f"{name} {label} horizontal overflow: {overflow}px"
                    page.evaluate("window.scrollTo(0, 0)")
                    page.screenshot(path=str(out / f"{name}-{label}.png"), full_page=True)
                    print(f"{name} {label}: browser interactions passed, no JS errors or overflow")
                    page.close()
        finally:
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=Path("website"))
    parser.add_argument("--out", type=Path, default=Path(".runs/previews"))
    parser.add_argument("--chromium", default=None, help="Optional local Chromium executable path")
    args = parser.parse_args()
    run(args.site, args.out, args.chromium)

if __name__ == "__main__":
    main()
