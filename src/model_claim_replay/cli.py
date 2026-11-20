"""Command-line entry point for inspecting, executing and auditing claim recipes."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .core import (
    ReplayError, canonical_json, evaluate_records, load_claim, read_bytes,
    read_jsonl, sha256_bytes, task_data, verify_bundle, write_jsonl,
)


def claim_listing(directory: Path) -> list[dict[str, str]]:
    """Inspect claim metadata; do not silently skip broken manifests."""
    if not directory.is_dir():
        raise ReplayError(f"No claim registry at {directory}")
    claims = []
    for path in sorted(directory.glob("*.json")):
        claim = load_claim(path)
        claims.append({"id": claim["id"], "kind": claim["kind"], "title": claim["title"], "path": str(path)})
    return claims


def api_completion(*, base_url: str, api_key: str | None, model: str, messages: list[dict[str, str]], temperature: float, max_tokens: int, timeout: float) -> tuple[str, dict[str, Any] | None]:
    """Call an OpenAI-compatible chat-completions endpoint once, without retries.

    A provider may implement these fields differently. This adapter provides
    a useful portable baseline, not equivalence to a provider's official harness.
    """
    parsed = urllib.parse.urlsplit(base_url)
    local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
        raise ReplayError("API base URL must use HTTPS (HTTP only for loopback tests)")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ReplayError("API base URL cannot include credentials, query, or fragment")
    if parsed.path not in ("", "/", "/v1", "/v1/"):
        raise ReplayError("API base URL must be the API origin or /v1")
    endpoint = base_url.rstrip("/") + ("" if parsed.path.rstrip("/") == "/v1" else "/v1") + "/chat/completions"
    payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(endpoint, data=canonical_json(payload), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if int(response.headers.get("Content-Length", "0")) > 1024 * 1024:
                raise ReplayError("Provider response exceeded size limit")
            raw = response.read(1024 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        raise ReplayError(f"Provider HTTP {exc.code}; response body excluded to avoid secret leakage") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ReplayError(f"Provider connection failed ({type(exc).__name__})") from exc
    if len(raw) > 1024 * 1024:
        raise ReplayError("Provider response exceeded 1 MiB")
    try:
        body = json.loads(raw)
        output = body["choices"][0]["message"]["content"]
        if not isinstance(output, str):
            raise ValueError("content is not text")
        usage = body.get("usage")
        return output, usage if isinstance(usage, dict) else None
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ReplayError("Provider returned an incompatible chat-completions response") from exc


def save_run(*, claim_path: Path, tasks_path: Path, claim: dict[str, Any], results: list[dict[str, Any]], directory: Path, model: str, run_kind: str) -> None:
    """Commit self-reported run files in a new directory, without overwriting."""
    if directory.exists():
        raise ReplayError(f"Output path already exists: {directory}")
    directory.mkdir(parents=True, exist_ok=False)
    write_jsonl(directory / "results.jsonl", results)
    metadata = {
        "schema_version": "1",
        "claim_id": claim["id"],
        "manifest_sha256": sha256_bytes(read_bytes(claim_path)),
        "tasks_sha256": sha256_bytes(read_bytes(tasks_path)),
        "results_sha256": sha256_bytes(read_bytes(directory / "results.jsonl")),
        "model": model,
        "run_kind": run_kind,
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "provenance": "self_reported_unattested",
    }
    (directory / "run.json").write_bytes(canonical_json(metadata) + b"\n")


def _report_page(claim: dict[str, Any], summary: dict[str, Any]) -> str:
    """Render an offline, self-contained report with escaped external strings."""
    esc = lambda value: html.escape(str(value), quote=True)
    observed = summary["observed_score"]
    observed_text = f"{100 * observed:.1f}%" if observed is not None else "No graded results"
    interval = summary["wilson_95"]
    interval_text = f"{100 * interval[0]:.1f}–{100 * interval[1]:.1f}%" if interval else "Unavailable"
    rows = "".join(
        f"<tr><td><code>{esc(item['id'])}</code></td><td>{esc(item['status'])}</td></tr>"
        for item in summary["task_results"]
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(claim['title'])} — Model Claim Replay</title><style>
:root{{font-family:Inter,system-ui,-apple-system,sans-serif;color:#192923;background:#f8f8f3}}
*{{box-sizing:border-box}}body{{margin:0}}main{{max-width:960px;margin:0 auto;padding:42px 24px 96px}}
a{{color:inherit}}header{{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #d8ddd5;padding-bottom:20px}}
.logo{{font-weight:800;letter-spacing:-.04em}}.eyebrow{{font-size:12px;text-transform:uppercase;letter-spacing:.12em;color:#476458;font-weight:700;margin-top:72px}}
h1{{font:normal clamp(34px,6vw,66px)/1.06 Georgia,serif;letter-spacing:-.035em;max-width:860px;margin:16px 0 24px}}
.subtitle{{color:#61736c;line-height:1.6;max-width:650px}}.metrics{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:44px 0}}
.metric{{border:1px solid #d8ddd5;background:#fff;padding:26px}}.metric span{{display:block;color:#63756b;font-size:13px}}.metric strong{{display:block;font-size:clamp(30px,6vw,56px);letter-spacing:-.045em;margin:10px 0}}
section{{border-top:1px solid #d8ddd5;padding-top:24px;margin-top:32px}}h2{{font:normal 28px Georgia,serif}}p{{line-height:1.65}}table{{width:100%;border-collapse:collapse}}td,th{{padding:13px;text-align:left;border-bottom:1px solid #d8ddd5}}th{{font-size:12px;text-transform:uppercase;letter-spacing:.1em;color:#61736c}}
.status{{padding:14px 18px;border-left:3px solid #997441;background:#efeee6}}small{{color:#62736c}}@media(max-width:620px){{.metrics{{grid-template-columns:1fr}}main{{padding:24px 18px}}}}
</style></head><body><main><header><div class="logo">MCR / EVIDENCE REPORT</div><small>Local, self-reported artifact</small></header>
<div class="eyebrow">Claim {esc(claim['id'])} · {esc(claim['kind'])}</div><h1>{esc(claim['title'])}</h1>
<p class="subtitle">Source: <a href="{esc(claim['source']['url'])}" rel="noopener noreferrer">{esc(claim['source']['url'])}</a><br>
Evaluated model label: {esc(summary['model'])} · Evidence origin: {esc(summary['run_kind'])}</p>
<div class="metrics"><div class="metric"><span>Publisher-reported result</span><strong>{100 * summary['reported_score']:.1f}%</strong><small>As reported; not independently validated here</small></div>
<div class="metric"><span>Observed in this run</span><strong>{esc(observed_text)}</strong><small>{summary['assessed']} graded / {summary['total_tasks']} total tasks</small></div></div>
<section><h2>Interpretation</h2><p class="status">{esc(summary['comparison_status'])}</p><p>{esc(summary['comparison_explanation'])}</p>
<p>95% Wilson interval: <strong>{esc(interval_text)}</strong>. This interval assumes independent Bernoulli tasks; correlated benchmarks, repeated trials, and selection effects invalidate a naive interpretation.</p></section>
<section><h2>Task accounting</h2><p>{summary['successes']} passed · {summary['failures']} failed · {summary['errors']} execution errors · {summary['attempted']} attempted.</p>
<table><thead><tr><th>Task</th><th>Outcome</th></tr></thead><tbody>{rows}</tbody></table></section>
<section><h2>Trust boundary</h2><p>SHA-256 checks bind local artifacts to this report. They do not authenticate the executor, provider response, benchmark licensing, model version, or publication conditions. This report is not an independent audit or a claim of benchmark-wide replication.</p></section>
<footer><small>Generated by Model Claim Replay · Offline HTML · No tracking or third-party scripts</small></footer></main></body></html>"""


def build_parser() -> argparse.ArgumentParser:
    """Create the stable v0.1 CLI parser."""
    p = argparse.ArgumentParser(prog="claim-replay", description="Source-anchored AI model claim experiments")
    sub = p.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", help="List the claim registry")
    listing.add_argument("--claims-dir", type=Path, default=Path("claims"))
    inspect = sub.add_parser("inspect", help="Inspect a claim and its reproduction blockers")
    inspect.add_argument("claim", type=Path)
    inspect.add_argument("--json", action="store_true", help="Emit the validated manifest")
    evaluate = sub.add_parser("evaluate", help="Ingest outputs from an external model run")
    evaluate.add_argument("--claim", required=True, type=Path)
    evaluate.add_argument("--tasks", required=True, type=Path)
    evaluate.add_argument("--responses", required=True, type=Path)
    evaluate.add_argument("--model", required=True)
    evaluate.add_argument("--out", required=True, type=Path)
    run = sub.add_parser("run", help="Run a portable-text claim via a chat-completions API")
    run.add_argument("--claim", required=True, type=Path)
    run.add_argument("--tasks", required=True, type=Path)
    run.add_argument("--model", required=True)
    run.add_argument("--base-url", default="https://api.openai.com/v1")
    run.add_argument("--api-key-env", default="OPENAI_API_KEY")
    run.add_argument("--limit", type=int, default=None)
    run.add_argument("--timeout", type=float, default=45.0)
    run.add_argument("--out", required=True, type=Path)
    verify = sub.add_parser("verify", help="Validate local run artifacts and recompute scoring")
    verify.add_argument("run_dir", type=Path)
    verify.add_argument("--claim", required=True, type=Path)
    verify.add_argument("--tasks", required=True, type=Path)
    report = sub.add_parser("report", help="Write offline HTML or JSON evidence report")
    report.add_argument("run_dir", type=Path)
    report.add_argument("--claim", required=True, type=Path)
    report.add_argument("--tasks", required=True, type=Path)
    report.add_argument("--format", choices=("html", "json"), default="html")
    report.add_argument("--output", required=True, type=Path)
    return p


def main(argv: list[str] | None = None) -> int:
    """Run CLI, emitting actionable errors and nonzero exit status on failure."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "list":
            for item in claim_listing(args.claims_dir):
                print(f"{item['kind']:<10} {item['id']:<44} {item['title']}")
        elif args.command == "inspect":
            claim = load_claim(args.claim)
            if args.json:
                print(json.dumps(claim, indent=2, ensure_ascii=False))
            else:
                print(f"{claim['title']}\nClaim: {claim['id']} ({claim['kind']})\nPublished score: {100*claim['reported_score']:.1f}%")
                print(f"Source: {claim['source']['url']}\nProtocol: {claim['protocol']['mode']}")
                print(f"Dataset pinned: {'yes' if claim['benchmark'].get('sha256') else 'NO — execution blocked'}")
                print("Status: no reproduction evidence is implied by this manifest")
        elif args.command in ("evaluate", "run"):
            claim = load_claim(args.claim)
            tasks = task_data(claim, args.tasks)
            if args.command == "evaluate":
                imported = read_jsonl(args.responses)
                results = [{"id": row["id"], "status": row.get("status", "ok"), **({"output": row["output"]} if "output" in row else {})} for row in imported]
                kind = "imported"
            else:
                if args.limit is not None and args.limit <= 0:
                    raise ReplayError("--limit must be positive")
                if args.timeout <= 0:
                    raise ReplayError("--timeout must be positive")
                results = []
                chosen = tasks[: args.limit] if args.limit else tasks
                protocol = claim["protocol"]
                for index, task in enumerate(chosen, 1):
                    messages = []
                    if protocol.get("system_prompt") is not None:
                        messages.append({"role": "system", "content": protocol["system_prompt"]})
                    messages.append({"role": "user", "content": task["prompt"]})
                    try:
                        output, usage = api_completion(
                            base_url=args.base_url, api_key=os.getenv(args.api_key_env),
                            model=args.model, messages=messages,
                            temperature=protocol.get("temperature", 0),
                            max_tokens=protocol.get("max_tokens", 128), timeout=args.timeout,
                        )
                        result: dict[str, Any] = {"id": task["id"], "status": "ok", "output": output}
                        if usage is not None:
                            result["usage"] = usage
                    except ReplayError as exc:
                        result = {"id": task["id"], "status": "error", "error_type": str(exc)}
                    results.append(result)
                    print(f"[{index}/{len(chosen)}] {task['id']}: {result['status']}", file=sys.stderr)
                kind = "api"
            # Reject unknown IDs before writing the bundle.
            evaluate_records(claim, tasks, results, model=args.model, run_kind=kind)
            save_run(claim_path=args.claim, tasks_path=args.tasks, claim=claim, results=results, directory=args.out, model=args.model, run_kind=kind)
            print(f"Saved local evidence bundle: {args.out}")
        elif args.command == "verify":
            print(json.dumps(verify_bundle(args.claim, args.tasks, args.run_dir), indent=2))
        elif args.command == "report":
            summary = verify_bundle(args.claim, args.tasks, args.run_dir)
            claim = load_claim(args.claim)
            output = (_report_page(claim, summary) if args.format == "html" else json.dumps(summary, indent=2) + "\n")
            args.output.write_text(output, encoding="utf-8")
            print(f"Verified bundle and wrote {args.output}")
    except (ReplayError, OSError) as exc:
        print(f"claim-replay: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
