"""Run the frozen campaign with fresh counts and separate paid authorization.

All 16 selected records receive outcomes. An ambiguous paid request stops
further generation, and the run is never resumed. The only published model
content is an explicitly authorized canonical final line.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from model_claim_replay.core import ReplayError, canonical_json, read_jsonl, sha256_bytes
from model_claim_replay.graphwalks import grade_response
from model_claim_replay.graphwalks_runtime import verified_prompts, INDEX_SHA256
from model_claim_replay.openai_graphwalks import (
    MODEL, OUTPUT_LIMIT, REDACTED_ONLY, PUBLISH_FINAL_LINE, _request,
    _write, _int, choose_key, public_final_line, reservation,
)
from openai_graphwalks_preflight import count_only_request
from openai_graphwalks_campaign_preflight import MANIFEST, validate_manifest, count_campaign

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "evidence/graphwalks/openai-campaign-preflight-2026-11-24.zip"
ARCHIVE_SHA256 = "622dc133c231e7f14562037f4d2094916054aae991b43fd83ab31dcbf27ac853"
APPROVAL = "AUTHORIZE_OPENAI_CAMPAIGN"
CEILING = Decimal("25")


def authorize(approval: str, budget: str, publication: str) -> None:
    if approval != APPROVAL or budget != str(CEILING):
        raise ReplayError("Separate campaign approval and exact USD 25 reservation required")
    if publication not in (REDACTED_ONLY, PUBLISH_FINAL_LINE):
        raise ReplayError("Invalid publication selection")


def load_frozen_preflight() -> dict[str, Any]:
    if sha256_bytes(ARCHIVE.read_bytes()) != ARCHIVE_SHA256:
        raise ReplayError("Original campaign preflight archive digest mismatch")
    with zipfile.ZipFile(ARCHIVE) as z:
        if z.namelist() != ["preflight.json"]:
            raise ReplayError("Unexpected preflight archive members")
        frozen = json.loads(z.read("preflight.json"))
    if (frozen.get("manifest_sha256") != sha256_bytes(MANIFEST.read_bytes())
            or frozen.get("reference_index_sha256") != INDEX_SHA256
            or frozen.get("generation_performed") is not False
            or frozen.get("paid_authorization") is not False):
        raise ReplayError("Original preflight does not bind the frozen source protocol")
    return frozen


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def band_stats(subset: list[dict[str, Any]]) -> dict[str, Any]:
        graded = [r["grade"]["f1"] for r in subset if r["status"] == "graded"]
        statuses = Counter(r["status"] for r in subset)
        return {
            "selected": len(subset), "statuses": dict(statuses),
            "graded": len(graded),
            "conditional_mean_f1": sum(graded) / len(graded) if graded else None,
            "full_selected_mean_f1": sum(graded) / len(subset)
                if subset and len(graded) == len(subset) else None,
            "parse_failures": sum(r["grade"]["parse_failed"] for r in subset
                                  if r["status"] == "graded"),
        }
    known = [r for r in rows if "upper_usage_cost_usd" in r]
    return {
        "overall": band_stats(rows),
        "short": band_stats([r for r in rows if r["band"] == "short"]),
        "long": band_stats([r for r in rows if r["band"] == "long"]),
        "generation_attempted": sum(r.get("generation_attempted", False) for r in rows),
        "known_usage_records": len(known),
        "known_usage_cost_estimate_usd": str(sum(
            (Decimal(r["upper_usage_cost_usd"]) for r in known), Decimal(0))),
        "all_attempted_usage_accounted": len(known) == sum(
            r.get("generation_attempted", False) for r in rows),
        "published_claim_reproduced": False,
    }


def evaluate_response(response: dict[str, Any], row: dict[str, Any],
                      reference: list[str], publication: str) -> dict[str, Any]:
    """Separate validated usage from completion, refusal and answer scoring."""
    usage = response.get("usage")
    if not isinstance(usage, dict):
        raise ReplayError("Missing usage")
    inp = _int(usage.get("input_tokens"), "actual input tokens")
    output = _int(usage.get("output_tokens"), "actual output tokens")
    total = _int(usage.get("total_tokens"), "actual total tokens")
    cost = reservation(inp, output)
    if (inp != row["input_tokens"] or total != inp + output or output > OUTPUT_LIMIT
            or cost > Decimal(row["reservation_usd"])):
        raise ReplayError("Accounting mismatch")
    if response.get("model") != MODEL or response.get("service_tier") != "default":
        raise ReplayError("Unexpected returned model or service tier")
    result = {
        "generation_attempted": True, "returned_model": MODEL,
        "input_tokens_actual": inp, "output_tokens_actual": output,
        "upper_usage_cost_usd": str(cost),
        "response_sha256": sha256_bytes(canonical_json(response) + b"\n"),
        "scoring_evidence_status": "not_graded",
    }
    if response.get("status") == "incomplete":
        return {**result, "status": "incomplete"}
    if response.get("status") != "completed":
        raise ReplayError("Unexpected response status")
    items = response.get("output")
    if not isinstance(items, list):
        raise ReplayError("Missing response output")
    texts = []
    refusals = False
    for item in items:
        if not isinstance(item, dict):
            raise ReplayError("Invalid response item")
        if item.get("type") == "reasoning":
            continue
        if (item.get("type") != "message" or item.get("role") != "assistant"
                or item.get("status") != "completed" or not isinstance(item.get("content"), list)):
            raise ReplayError("Unexpected message")
        for part in item["content"]:
            if not isinstance(part, dict):
                raise ReplayError("Invalid content")
            if part.get("type") == "refusal":
                refusals = True
            elif part.get("type") == "output_text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
            else:
                raise ReplayError("Unexpected content")
    if refusals:
        return {**result, "status": "refused"}
    if len(texts) != 1:
        raise ReplayError("Expected one answer text")
    text = texts[0]
    result.update(status="graded", grade=grade_response(text, reference),
                  answer_sha256=sha256_bytes(text.encode()),
                  scoring_evidence_status="withheld_by_policy")
    if publication == PUBLISH_FINAL_LINE:
        line = public_final_line(text)
        if line is None:
            result["scoring_evidence_status"] = "withheld_noncanonical_final_line"
        else:
            result.update(scoring_evidence_status="final_line_exported", final_line=line,
                          final_line_sha256=sha256_bytes(line.encode()))
    return result


def run_campaign(manifest: dict[str, Any], prompts: dict[str, str],
                 references: dict[str, list[str]], frozen: dict[str, Any],
                 out: Path, *, approval: str, budget: str, publication: str,
                 environ: dict[str, str], request: Callable = _request) -> dict[str, Any]:
    authorize(approval, budget, publication)
    if out.exists() or out.is_symlink():
        raise ReplayError("Output exists; never resume a paid campaign")
    if set(references) != {r["id"] for r in manifest["tasks"]}:
        raise ReplayError("Reference set differs from frozen campaign")
    # Metadata and all counting requests pass a separate no-generation guard.
    def safe_count(path, payload, key):
        return count_only_request(path, payload, key, transport=request)
    key = choose_key(environ, safe_count)
    fresh = count_campaign(manifest, prompts, key=key, request=safe_count)
    out.mkdir(parents=True, exist_ok=False)
    public = out / "public"
    public.mkdir()
    plan = {
        "schema_version": "graphwalks-openai-paid-campaign-plan-v1",
        "frozen_preflight_archive_sha256": ARCHIVE_SHA256,
        "manifest_sha256": sha256_bytes(MANIFEST.read_bytes()),
        "reference_index_sha256": INDEX_SHA256,
        "model": MODEL, "reasoning_effort": "xhigh", "max_output_tokens": OUTPUT_LIMIT,
        "service_tier": "default", "prompt_cache_options": {"mode": "explicit", "ttl": "30m"},
        "authorized_ceiling_usd": str(CEILING), "publication": publication,
        "fresh_preflight": fresh, "published_claim_reproduced": False,
    }
    _write(public / "plan.json", plan)
    digest = sha256_bytes((public / "plan.json").read_bytes())
    fresh_rows = fresh["tasks"]
    # Fail closed on any change in count, feasibility, order or reservation.
    permitted = (fresh_rows == frozen["tasks"] and fresh["all_counts_observed"]
                 and Decimal(fresh["total_feasible_reservation_usd"]) <= CEILING)
    rows = []
    stopped = not permitted
    for number, source in enumerate(fresh_rows, 1):
        row = {**source, "generation_attempted": False, "plan_sha256": digest}
        prefix = f"task-{number:02d}"
        if source["status"] == "feasible":
            if stopped:
                row["status"] = "unattempted"
            else:
                _write(public / (prefix + "-intent.json"), {
                    "status": "generation_intent", "id": source["id"],
                    "plan_sha256": digest, "reservation_usd": source["reservation_usd"],
                })
                try:
                    response = request("/v1/responses", {
                        "model": MODEL, "input": prompts[source["id"]],
                        "reasoning": {"effort": "xhigh"}, "truncation": "disabled",
                        "max_output_tokens": OUTPUT_LIMIT, "store": False,
                        "service_tier": "default", "tools": [],
                        "prompt_cache_options": {"mode": "explicit", "ttl": "30m"},
                    }, key)
                    row.update(evaluate_response(response, source,
                                                 references[source["id"]], publication))
                except (ReplayError, OSError, ValueError, TypeError, KeyError):
                    row.update(status="generation_or_accounting_uncertain",
                               generation_attempted=True, retry_permitted=False)
                    stopped = True
        _write(public / (prefix + "-outcome.json"), row)
        rows.append(row)
    report = {
        "schema_version": "graphwalks-openai-paid-campaign-result-v1",
        "status": "preflight_changed_or_over_budget" if not permitted else
                  ("stopped_uncertain" if stopped else "finished"),
        "plan_sha256": digest, "tasks": rows, **summarize(rows),
        "limitations": "Conditional scores on one fixed public candidate cohort; "
                       "no publisher reproduction, external authentication or invoice verification.",
    }
    _write(public / "summary.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--approval", required=True)
    parser.add_argument("--budget", required=True)
    parser.add_argument("--publication", required=True)
    args = parser.parse_args()
    try:
        authorize(args.approval, args.budget, args.publication)
        frozen = load_frozen_preflight()
        manifest = json.loads(MANIFEST.read_bytes())
        prompts = verified_prompts(args.parquet, args.index)
        index = read_jsonl(args.index)
        validate_manifest(manifest, index)
        selected = {r["id"] for r in manifest["tasks"]}
        refs = {r["id"]: r["answer_nodes"] for r in index if r["id"] in selected}
        report = run_campaign(manifest, prompts, refs, frozen, args.out,
                              approval=args.approval, budget=args.budget,
                              publication=args.publication, environ=dict(os.environ))
    except (ReplayError, OSError, ValueError, KeyError, zipfile.BadZipFile):
        parser.exit(2, "Campaign stopped; inspect retained public evidence. Never rerun automatically.\n")
    print(json.dumps({k: v for k, v in report.items() if k != "tasks"}, sort_keys=True))
    return 0 if report["status"] == "finished" else 2


if __name__ == "__main__":
    sys.exit(main())
