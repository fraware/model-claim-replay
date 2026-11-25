"""Check the public GitHub Pages deployment against the source revision.

Only the fixed public site is contacted. No credentials or model calls.
Screenshots are evidence of the deployed browser view, not third-party review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.request import Request, urlopen

ORIGIN = "https://fraware.github.io/model-claim-replay/"
ASSETS = (
    "index.html", "graphwalks.html", "check.html",
    "base.css", "style.css", "app.js", "graphwalks.css", "graphwalks.js",
    "check.css", "check.js", "graphwalks-audit.json",
    "graphwalks-control.json", "graphwalks-gemini-feasibility.json",
    "graphwalks-openai-preflight.json", "graphwalks-openai-result.json",
    "graphwalks-openai-campaign.json", "graphwalks-input-feasibility.svg",
    "fonts/IBMPlexSans-Regular.woff2", "fonts/IBMPlexSans-Medium.woff2", "fonts/IBMPlexSans-SemiBold.woff2", "fonts/IBMPlexSans-Bold.woff2", "fonts/IBMPlexMono-Regular.woff2", "fonts/IBMPlexMono-Bold.woff2",
    "fonts/LICENSE.txt", "fonts/NOTICE.txt",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_bytes(site: Path, revision: str) -> dict[str, str]:
    """Check exact response bytes, allowing bounded CDN propagation time."""
    expected = {name: (site / name).read_bytes() for name in ASSETS}
    last_error = None
    for attempt in range(8):
        try:
            result = {}
            for name, local in expected.items():
                url = f"{ORIGIN}{name}?revision={revision}"
                request = Request(url, headers={
                    "Accept-Encoding": "identity",
                    "Cache-Control": "no-cache",
                    "User-Agent": "ModelClaimReplay-DeploymentCheck/1",
                })
                with urlopen(request, timeout=15) as response:
                    if response.geturl() != url or response.status != 200:
                        raise RuntimeError(f"Unexpected HTTP response for {name}")
                    raw = response.read(len(local) + 1)
                if raw != local:
                    raise RuntimeError(f"Published bytes differ for {name}")
                result[name] = sha256(raw)
            return result
        except (OSError, RuntimeError) as exc:
            last_error = exc
            if attempt < 7:
                time.sleep(15)
    raise RuntimeError("Public deployment did not match source revision") from last_error


def run(site: Path, out: Path, revision: str) -> None:
    """Verify deployed bytes, then exercise actual public pages in Chromium."""
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError("Expected a full lowercase Git commit SHA")
    out.mkdir(parents=True, exist_ok=True)
    hashes = check_bytes(site, revision)
    (out / "published-assets.json").write_text(json.dumps({
        "revision": revision, "origin": ORIGIN, "sha256": hashes,
    }, indent=2) + "\n", encoding="utf-8")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as api:
        browser = api.chromium.launch(headless=True)
        try:
            for label, width, height in (("desktop", 1440, 900), ("mobile", 390, 844)):
                for name, target in (
                    ("index", "#campaign-evidence"),
                    ("graphwalks", "#openai-campaign"),
                    ("check", "#bundle-form"),
                ):
                    page = browser.new_page(viewport={"width": width, "height": height})
                    errors: list[str] = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    try:
                        response = page.goto(f"{ORIGIN}{name}.html?revision={revision}",
                                             wait_until="load", timeout=30_000)
                        assert response is not None and response.status == 200
                        page.locator(target).wait_for(state="visible")
                        assert page.evaluate("""async () => {
                            await document.fonts.ready;
                            const faces = await document.fonts.load('400 16px "IBM Plex Sans"');
                            return faces.length > 0 && faces.every(face => face.status === "loaded");
                        }""")
                        if name == "graphwalks":
                            text = page.locator(target).inner_text()
                            assert "0.875" in text
                            assert "8 graded / 16 selected" in text
                            assert "No full-cohort mean" in text
                            page.locator(target).screenshot(path=str(out / f"campaign-{label}.png"))
                        elif name == "index":
                            assert "8 graded of 16 selected" in page.locator(target).inner_text()
                        assert not errors, errors
                        assert page.evaluate("document.documentElement.scrollWidth - innerWidth") <= 1
                        page.evaluate("window.scrollTo(0, 0)")
                        page.screenshot(path=str(out / f"{name}-{label}.png"))
                        print(f"Public {name} {label}: passed")
                    except BaseException:
                        page.screenshot(path=str(out / f"{name}-{label}-failure.png"))
                        raise
                    finally:
                        page.close()
        finally:
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    run(args.site, args.out, args.revision)


if __name__ == "__main__":
    main()
