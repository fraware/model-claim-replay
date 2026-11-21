"""Standalone, privacy-preserving HTML for verified public GraphWalks receipts.

A public HTML report is a *view* of three locally consistent, self-reported
JSON receipts. It does not authenticate the model provider, source dataset,
private outputs, publisher's evaluation conditions, or the score itself.
"""

from __future__ import annotations

import json
import os
import tempfile
from html import escape
from pathlib import Path
from string import Template
from typing import Any

from .core import ReplayError, read_bytes, sha256_bytes
from .graphwalks_public import verify_public_graphwalks_receipts


_HTML = Template(r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src 'none'; connect-src 'none'; base-uri 'none'; form-action 'none'">
<meta name="color-scheme" content="light">
<title>GraphWalks / Evidence record — Model Claim Replay</title>
<style>
:root{font-family:ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#1c2528;background:#f7f5ef}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;line-height:1.55}a{color:#275345;text-underline-offset:3px}
header,main,footer{max-width:1110px;margin:0 auto;padding-left:28px;padding-right:28px}
header{padding-top:27px;padding-bottom:20px;display:flex;justify-content:space-between;gap:18px;border-bottom:1px solid #bdc4bd}
.brand,.meta,small,.eyebrow,.caption,.number,.chip,button{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.brand{font-size:14px;letter-spacing:.015em;font-weight:750}
.meta,.eyebrow,.caption{font-size:12px;text-transform:uppercase;letter-spacing:.075em;color:#50605b}
.hero{padding:64px 0 42px}.eyebrow{display:flex;align-items:center;gap:12px}.eyebrow:before{content:"";background:#ac4d35;width:22px;height:3px;display:inline-block}
h1{font:normal clamp(40px,6vw,74px)/1.06 Georgia,"Times New Roman",serif;letter-spacing:-.045em;margin:18px 0 24px;max-width:850px}
.lead{max-width:790px;color:#45514e;font-size:17px;line-height:1.68}
.disclosure{border-left:4px solid #aa4a35;background:#eee8df;padding:18px 23px;font-size:15px;line-height:1.7;margin-top:34px}
.disclosure strong{display:block;font-family:ui-monospace,monospace;font-size:12px;letter-spacing:.045em;margin-bottom:5px}
.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border:1px solid #c1c9c0;background:#fff;margin:26px 0 42px}
.metric{padding:26px 26px 30px}.metric+.metric{border-left:1px solid #c1c9c0}
.metric .value{font-size:clamp(37px,4.5vw,60px);font-weight:650;letter-spacing:-.065em;line-height:1.25;margin:8px 0}
.metric p{font-size:13px;line-height:1.55;color:#51605b;margin:0}
section{padding:24px 0 40px;border-top:1px solid #bdc4bd}
h2{font:normal 32px/1.25 Georgia,"Times New Roman",serif;letter-spacing:-.025em;margin:14px 0}
.section-intro{color:#50605b;max-width:850px}
.accounting{display:flex;height:22px;width:100%;border:1px solid #c1c9c0;background:#ecece5;overflow:hidden;margin:24px 0 18px}
.accounting span{height:100%;display:block;min-width:0}
.accounting .graded{background:#386754}.accounting .error{background:#ae473b}
.accounting .unresolved{background:#c08a38}.accounting .planned{background:#819598}
.accounting .outside{background:#e4e5de}
.breakdown{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}
.breakdown p{font-size:13px;color:#52605b;margin:4px 0}
.breakdown strong{font-size:25px;letter-spacing:-.035em}
.dot{width:9px;height:9px;display:inline-block;margin-right:6px;background:#386754}
.dot.error{background:#ae473b}.dot.unresolved{background:#c08a38}.dot.planned{background:#819598}.dot.outside{background:#d5d7cf}
.filter-bar{display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin:24px 0}
.filter{cursor:pointer;padding:9px 13px;color:#28322e;background:transparent;border:1px solid #b6bfb8;font-size:12px}
.filter[aria-pressed="true"]{background:#1c2823;color:#fff;border-color:#1c2823}
.filter:focus-visible{outline:3px solid #ab643f;outline-offset:2px}
#shown{font-size:12px;color:#52605b;margin-left:auto}
.table-wrap{overflow-x:auto;border:1px solid #c4cbc5;background:#fff}
table{width:100%;border-collapse:collapse;min-width:650px;font-size:14px}
th{text-align:left;color:#52605b;text-transform:uppercase;letter-spacing:.07em;font-size:11px;padding:15px 17px;background:#f0f1eb;border-bottom:1px solid #c4cbc5}
td{padding:11px 17px;border-bottom:1px solid #e5e9e4}tr:last-child td{border-bottom:none}
tbody tr:hover{background:#f5f6f1}tr[hidden]{display:none}
.number{font-size:12px}.chip{display:inline-block;font-size:11px;border:1px solid #c8d0c9;padding:3px 8px;color:#365e51}
.chip.error{color:#8e4236;border-color:#d9b2a8}.chip.unresolved{color:#7e5c21;border-color:#e4cc9e}
.chip.planned{color:#536771}.chip.outside{color:#707871;border-color:#ddd}
.hashes{display:grid;grid-template-columns:220px minmax(0,1fr);gap:8px 22px;margin:22px 0}
.hashes dt{font-size:12px;color:#50605b}.hashes dd{font:12px/1.65 ui-monospace,monospace;overflow-wrap:anywhere;margin:0}
.note{font-size:14px;color:#52605b;max-width:870px}
footer{border-top:1px solid #bdc4bd;padding-top:20px;padding-bottom:60px;font-size:12px;color:#52605b;display:flex;flex-wrap:wrap;justify-content:space-between;gap:18px}
@media(max-width:760px){header,main,footer{padding-left:18px;padding-right:18px}.hero{padding-top:44px}.metrics{grid-template-columns:1fr}.metric+.metric{border-left:0;border-top:1px solid #c1c9c0}.breakdown{grid-template-columns:repeat(2,minmax(0,1fr))}.hashes{grid-template-columns:1fr}.hashes dd{margin-bottom:10px}#shown{margin-left:0}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
</style>
</head>
<body>
<header><span class="brand">M/CR &nbsp; / &nbsp; EVIDENCE RECORD</span><span class="meta">GRAPHWALKS · SELF-REPORTED</span></header>
<main>
<div class="hero">
<div class="eyebrow">01 / SOURCE-TO-EVIDENCE AUDIT</div>
<h1>What the model run actually recorded.</h1>
<p class="lead">An offline report of a declared Gemini 4 Neon diagnostic on the candidate public GraphWalks BFS dataset. The receipts were cross-checked for internal consistency. Provider execution and the original benchmark conditions have not been independently established.</p>
<div class="disclosure" role="note">
<strong>STATUS / NOT COMPARABLE TO THE PUBLISHED CLAIM</strong>
Local receipts are internally consistent. This does not certify the provider, original prompt delivery, reference answers, score calculation from raw model text, actual billing, or Google's evaluated cohort. A jointly fabricated receipt set could also pass verification.
</div>
</div>
<div class="metrics" aria-label="Reported and recorded scores">
<div class="metric"><div class="caption">Published claim / Google</div><div class="value">95.2%</div><p>Google-reported GraphWalks BFS F1. <a href="https://deepmind.google/models/model-cards/gemini-4-neon/">Original model card</a>. Not independently reproduced.</p></div>
<div class="metric"><div class="caption">This run / graded subset</div><div class="value">$SCORE</div><p>$GRADED graded responses out of $TOTAL reference tasks. Selection is diagnostic; the subset score is not an estimate of the publisher's result.</p></div>
<div class="metric"><div class="caption">Complete 200-task mean</div><div class="value">$FULL_SCORE</div><p>$FULL_NOTE</p></div>
</div>
<section aria-labelledby="coverage-heading">
<div class="eyebrow">02 / DENOMINATOR</div><h2 id="coverage-heading">Account for every task.</h2>
<p class="section-intro">$PLANNED tasks in this declared pilot; $ATTEMPTED request intents; $COMPLETED recorded completed generations. Every task outside the pilot, incomplete request, and recorded failure is distinguished from scored output.</p>
<div class="accounting" role="img" aria-label="$BAR_LABEL">$BAR</div>
<div class="breakdown">
<div><span class="dot"></span><span class="caption">Completed / graded</span><div><strong>$COMPLETED</strong></div></div>
<div><span class="dot error"></span><span class="caption">Recorded errors</span><div><strong>$ERRORS</strong></div></div>
<div><span class="dot unresolved"></span><span class="caption">Unresolved requests</span><div><strong>$UNRESOLVED</strong></div></div>
<div><span class="dot planned"></span><span class="caption">Planned, not attempted</span><div><strong>$UNATTEMPTED</strong></div></div>
<div><span class="dot outside"></span><span class="caption">Outside pilot</span><div><strong>$OUTSIDE</strong></div></div>
</div>
<p class="note">Only completed responses appear as graded. An error or missing response is excluded from the scored-subset mean. No full-cohort score is published for a partial cohort.</p>
</section>
<section aria-labelledby="tasks-heading">
<div class="eyebrow">03 / TASK-BY-TASK RECORD</div><h2 id="tasks-heading">200 source identities. No hidden exclusions.</h2>
<p class="section-intro">The table reports only redacted task identities, local journal status and F1. Original prompts, answer lists and model response text are excluded. The table does not independently recalculate F1 from private outputs.</p>
<div class="filter-bar" role="group" aria-label="Filter task table">
<button type="button" class="filter" data-filter="all" aria-pressed="true">All 200</button>
<button type="button" class="filter" data-filter="pilot" aria-pressed="false">Declared pilot</button>
<button type="button" class="filter" data-filter="graded" aria-pressed="false">Graded only</button>
<button type="button" class="filter" data-filter="problems" aria-pressed="false">Errors / unresolved</button>
<span id="shown" aria-live="polite">Showing $TOTAL tasks</span>
</div>
<div class="table-wrap"><table><thead><tr><th scope="col">Task ID</th><th scope="col">Journal state</th><th scope="col">Scorer state</th><th scope="col">Recorded F1</th></tr></thead><tbody>$ROWS</tbody></table></div>
</section>
<section aria-labelledby="evidence-heading">
<div class="eyebrow">04 / EVIDENCE AND ORIGIN</div><h2 id="evidence-heading">Trace the exact receipt bytes.</h2>
<p class="section-intro">SHA-256 binds this report to the three supplied self-reported files. The original dataset bytes, task answers, raw provider exchanges and billing records were not supplied to this public verification step.</p>
<dl class="hashes">
<dt>Declared model</dt><dd>$MODEL</dd>
<dt>Token plan created</dt><dd>$CREATED</dd>
<dt>Candidate dataset revision</dt><dd>$REVISION</dd>
<dt>Candidate source Parquet SHA-256</dt><dd>$SOURCE_HASH</dd>
<dt>BFS reference index SHA-256</dt><dd>$INDEX_HASH</dd>
<dt>Token plan SHA-256</dt><dd>$PLAN_HASH</dd>
<dt>Journal audit SHA-256</dt><dd>$AUDIT_HASH</dd>
<dt>Task-level grades SHA-256</dt><dd>$GRADES_HASH</dd>
<dt>Declared maximum cost reservation</dt><dd>USD $RESERVATION (not observed billing)</dd>
<dt>Thinking setting</dt><dd>$THINKING</dd>
<dt>Output allowance</dt><dd>$OUTPUT tokens (reasoning plus response)</dd>
</dl>
<p class="note">Verification state: internally_consistent_self_reported_only. Comparison state: not_comparable. No independent authentication, provider invoice validation, or publisher-cohort equivalence was performed. The publisher's percentage above is contextual and is never subtracted from a partial or unverified score.</p>
</section>
</main>
<footer><span>MODEL CLAIM REPLAY / OFFLINE EVIDENCE</span><span>No external scripts, network requests or tracking · <a href="https://github.com/fraware/model-claim-replay">Open-source methodology</a></span></footer>
<script>
(function () {
  "use strict";
  const rows = Array.from(document.querySelectorAll("tbody tr"));
  const buttons = Array.from(document.querySelectorAll("button[data-filter]"));
  const shown = document.getElementById("shown");
  for (const button of buttons) {
    button.addEventListener("click", function () {
      const filter = button.getAttribute("data-filter");
      let count = 0;
      for (const row of rows) {
        const state = row.getAttribute("data-journal");
        const include = filter === "all" ||
          (filter === "pilot" && state !== "outside") ||
          (filter === "graded" && state === "completed") ||
          (filter === "problems" && (state === "error" || state === "unresolved"));
        row.hidden = !include;
        if (include) count += 1;
      }
      for (const other of buttons) {
        other.setAttribute("aria-pressed", String(other === button));
      }
      shown.textContent = "Showing " + count + " tasks";
    });
  }
}());
</script>
</body>
</html>
""")


def _percent(value: Any) -> str:
    """Format a validated [0,1] metric, or show an absent measurement."""
    return "—" if value is None else f"{100 * value:.1f}%"


def _render(plan: dict[str, Any], audit: dict[str, Any],
            scores: dict[str, Any], receipt: dict[str, Any]) -> str:
    """Build the redacted report after receipt verification has succeeded."""
    statuses = {entry["id"]: entry["status"] for entry in audit["entries"]}
    labels = {
        "completed": "Completed",
        "error": "Recorded error",
        "unresolved": "Unresolved",
        "not_attempted": "Not attempted",
        "outside": "Outside pilot",
    }
    table_rows = []
    for result in scores["results"]:
        ident = result["id"]
        journal = statuses.get(ident, "outside")
        grade = result["status"]
        value = _percent(result["f1"]) if grade == "graded" else "—"
        table_rows.append(
            f'<tr data-journal="{journal}"><td class="number">{escape(ident)}</td>'
            f'<td><span class="chip {journal}">{labels[journal]}</span></td>'
            f'<td>{escape(grade)}</td><td class="number">{value}</td></tr>'
        )
    totals = {
        "graded": receipt["graded"],
        "error": receipt["failed"],
        "unresolved": receipt["unresolved"],
        "planned": receipt["planned"] - receipt["attempted"],
        "outside": receipt["task_count"] - receipt["planned"],
    }
    bar = "".join(
        '<span class="{cls}" style="width:{width:.6f}%"></span>'.format(
            cls=key, width=100.0 * count / receipt["task_count"],
        )
        for key, count in totals.items() if count
    )
    full = scores["mean_f1"]
    fields = {
        "SCORE": _percent(receipt["scored_subset_mean_f1_diagnostic"]),
        "FULL_SCORE": _percent(full),
        "FULL_NOTE": (
            "All 200 source tasks graded locally. Publisher comparability and provider "
            "authentication remain unestablished."
            if full is not None else
            "Unavailable: the 200-task reference cohort is incomplete. "
            "Missing and failed tasks are never silently excluded."
        ),
        "GRADED": str(receipt["graded"]),
        "TOTAL": str(receipt["task_count"]),
        "PLANNED": str(receipt["planned"]),
        "ATTEMPTED": str(receipt["attempted"]),
        "COMPLETED": str(receipt["completed"]),
        "ERRORS": str(receipt["failed"]),
        "UNRESOLVED": str(receipt["unresolved"]),
        "UNATTEMPTED": str(totals["planned"]),
        "OUTSIDE": str(totals["outside"]),
        "BAR_LABEL": escape(
            ", ".join(f"{value} {key}" for key, value in totals.items())
        ),
        "BAR": bar,
        "ROWS": "".join(table_rows),
        "MODEL": escape(plan["model"]),
        "CREATED": escape(plan["created_utc"]),
        "REVISION": escape(plan["dataset_revision"]),
        "SOURCE_HASH": escape(plan["parquet_sha256"]),
        "INDEX_HASH": escape(plan["index_sha256"]),
        "PLAN_HASH": escape(receipt["input_sha256"]["token_plan"]),
        "AUDIT_HASH": escape(receipt["input_sha256"]["execution_audit"]),
        "GRADES_HASH": escape(receipt["input_sha256"]["score_report"]),
        "RESERVATION": escape(plan["maximum_reserved_cost_usd"]),
        "THINKING": escape(plan["thinking_level"]),
        "OUTPUT": str(plan["max_output_tokens"]),
    }
    return _HTML.substitute(fields)


def generate_graphwalks_public_html(
    plan_path: Path, audit_path: Path, grades_path: Path, output: Path,
) -> dict[str, Any]:
    """Verify all three receipts, then write a single offline HTML report.

    The report is never emitted for inconsistent or missing receipts.
    Rehash all rendered inputs against the verifier's exact byte commitments
    to detect changes during this two-step read. Preserve previous output.
    """
    receipt = verify_public_graphwalks_receipts(plan_path, audit_path, grades_path)
    paths = (plan_path, audit_path, grades_path)
    expected = (
        receipt["input_sha256"]["token_plan"],
        receipt["input_sha256"]["execution_audit"],
        receipt["input_sha256"]["score_report"],
    )
    values = []
    for path, digest in zip(paths, expected):
        raw = read_bytes(path)
        if sha256_bytes(raw) != digest:
            raise ReplayError("Public GraphWalks receipts changed during HTML generation")
        values.append(json.loads(raw))
    if output.exists() or output.is_symlink():
        raise ReplayError(f"Output path already exists: {output}")
    rendered = _render(values[0], values[1], values[2], receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=".graphwalks-report-", suffix=".html", dir=output.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(rendered)
        try:
            os.link(temporary, output)
        except FileExistsError as exc:
            raise ReplayError(f"Output path already exists: {output}") from exc
    finally:
        Path(temporary).unlink(missing_ok=True)
    return receipt
