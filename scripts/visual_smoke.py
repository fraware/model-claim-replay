"""Browser-level checks for the actual static website and its local data.

Run after installing Playwright and Chromium:
    python -m pip install playwright
    python -m playwright install chromium
    python scripts/visual_smoke.py --site website --out .runs/previews

The temporary HTTP server binds only to loopback. Chromium fetches the
unmodified HTML, CSS, JS and both JSON receipts as a normal browser would.
No external network service, model endpoint or paid inference is contacted.
"""

from __future__ import annotations

import argparse
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class _QuietFileHandler(SimpleHTTPRequestHandler):
    """Serve local test assets without polluting CI logs with access lines."""

    def log_message(self, *_: object) -> None:
        return


def run(site: Path, out: Path, browser_path: str | None = None) -> None:
    """Exercise desktop/mobile website behavior over a real loopback origin."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Install playwright to run browser QA") from exc

    site = site.resolve(strict=True)
    required = (
        "index.html", "app.js", "style.css", "graphwalks.html",
        "graphwalks.js", "graphwalks.css", "graphwalks-audit.json",
        "graphwalks-control.json", "graphwalks-gemini-feasibility.json",
    )
    for filename in required:
        if not (site / filename).is_file():
            raise FileNotFoundError(f"Missing website asset: {filename}")
    out.mkdir(parents=True, exist_ok=True)

    handler = partial(_QuietFileHandler, directory=str(site))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        with sync_playwright() as api:
            options: dict[str, object] = {
                "headless": True, "args": ["--no-sandbox"],
            }
            if browser_path:
                options["executable_path"] = browser_path
            browser = api.chromium.launch(**options)
            try:
                for label, width, height in (
                    ("desktop", 1440, 900),
                    ("mobile", 390, 844),
                ):
                    for name in ("index", "graphwalks"):
                        page = browser.new_page(
                            viewport={"width": width, "height": height},
                            reduced_motion="reduce",
                        )
                        errors: list[str] = []
                        page.on("pageerror", lambda e: errors.append(str(e)))
                        try:
                            response = page.goto(
                                f"{origin}/{name}.html", wait_until="load",
                                timeout=30_000,
                            )
                            assert response is not None and response.status == 200

                            if name == "graphwalks":
                                page.wait_for_function(
                                    "document.querySelectorAll('button.task-dot').length === 200"
                                )
                                assert page.locator("button.task-dot").count() == 200
                                page.locator('button.filter[data-filter="long"]').click()
                                assert page.locator("button.task-dot").count() == 100
                                page.locator('button.filter[data-filter="short"]').click()
                                assert page.locator("button.task-dot").count() == 100
                                page.locator('button.filter[data-filter="all"]').click()
                                page.locator("button.task-dot").first.click()
                                assert "SELECTED SOURCE RECORD" in page.locator("#record").inner_text()

                                # This test used to mock both JSON fetches with
                                # the audit data, silently skipping actual control
                                # rendering. Verify the real control receipt.
                                page.locator(".control-task").wait_for()
                                control = page.locator(".control-task").inner_text()
                                assert "F1 1.000" in control
                                assert "NOT A MODEL SCORE" in control

                                # Wait for the third real, source-bound receipt
                                # and verify the task-level context verdict.
                                page.wait_for_function(
                                    "document.querySelector('#record')?.textContent?.includes('GEMINI INPUT TOKENS / LIVE PROVIDER')"
                                )
                                self_report = page.locator("#record").inner_text()
                                assert "355,124" in self_report
                                assert "WITHIN INPUT LIMIT" in self_report
                                assert "100 prompts fit." in page.locator("#provider").inner_text()

                                page.locator('button.filter[data-filter="long"]').click()
                                page.locator("button.task-dot").first.click()
                                long_text = page.locator("#record").inner_text()
                                assert "1,419,783" in long_text
                                assert "EXCEEDS INPUT LIMIT" in long_text
                                page.locator('button.filter[data-filter="all"]').click()

                                page.locator("#task-search").fill("bfs-row-000100")
                                assert page.locator("button.task-dot").count() == 1
                                page.locator("#task-search").fill("")
                                assert page.locator("button.task-dot").count() == 200
                            else:
                                page.wait_for_function(
                                    "document.querySelectorAll('.claim-row').length === 3"
                                )
                                page.locator(".claim-row").nth(1).click()
                                assert page.locator("#claim-detail").is_visible()
                                page.locator(".filter[data-filter='published']").click()
                                assert page.locator(".claim-row").count() == 2
                                page.locator(".filter[data-filter='all']").click()

                                page.locator("#next-step").click()
                                assert "PASS" in page.locator("#verdict").inner_text()
                                page.locator("#next-step").click()
                                page.locator("#next-step").click()
                                assert "FAIL" in page.locator("#verdict").inner_text()
                                page.locator("#reset-demo").click()
                                assert "0 of 3" in page.locator("#assessed-display").inner_text()

                                page.locator('button.scenario[data-scenario="judge"]').click()
                                assert "COMPARISON BLOCKED" in page.locator("#pair-status-label").inner_text()
                                page.locator('button.scenario[data-scenario="matched"]').click()
                                assert "PAIRED DIAGNOSTIC" in page.locator("#pair-status-label").inner_text()

                            assert not errors, f"{name} browser errors: {errors}"
                            overflow = page.evaluate(
                                "document.documentElement.scrollWidth - innerWidth"
                            )
                            assert overflow <= 1, (
                                f"{name} {label} horizontal overflow: {overflow}px"
                            )
                            page.evaluate("window.scrollTo(0, 0)")
                            page.screenshot(
                                path=str(out / f"{name}-{label}.png"),
                                full_page=True,
                            )
                            print(
                                f"{name} {label}: browser interactions and data "
                                "receipts passed, no JS errors or overflow"
                            )
                        except BaseException:
                            page.screenshot(
                                path=str(out / f"{name}-{label}-failure.png"),
                                full_page=True,
                            )
                            raise
                        finally:
                            page.close()
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def main() -> None:
    """CLI entry point with explicit local paths and optional Chromium binary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=Path("website"))
    parser.add_argument("--out", type=Path, default=Path(".runs/previews"))
    parser.add_argument("--chromium", default=None,
                        help="Optional local Chromium executable path")
    args = parser.parse_args()
    run(args.site, args.out, args.chromium)


if __name__ == "__main__":
    main()
