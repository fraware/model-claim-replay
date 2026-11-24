"""Offline verification of the frozen OpenAI campaign's public journal.

Recompute disclosed-line scores using independent set arithmetic. Check
selection, preflight commitments, intent/outcome coverage and reservations.
This does not authenticate provider execution, invoice charges, or extraction
of the disclosed line from the undisclosed full answer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import zipfile
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from model_claim_replay.core import ReplayError, read_bytes, read_json, read_jsonl

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evidence/graphwalks/openai-campaign-v1.json"
ARCHIVE = ROOT / "evidence/graphwalks/openai-campaign-preflight-2026-11-24.zip"
MANIFEST_SHA256 = "b5bedeaf9ba25f0f6321bd7fbe6995db7bdd706c881f3168ef03b10ee3d22efc"
ARCHIVE_SHA256 = "622dc133c231e7f14562037f4d2094916054aae991b43fd83ab31dcbf27ac853"
INDEX_SHA256 = "250d80874ad9bc8edf278cf3bf7aa145da3f2b34967c5504b8fa8703358480ee"
MODEL = "gpt-6.2-sol"
CEILING = Decimal("25")
OUTPUT_LIMIT = 65536
HEX = re.compile(r"[0-9a-f]{64}")
LINE = re.compile(r"Final Answer: \[[ \t]*(?:[0-9a-f]{10}(?:[ \t]*,[ \t]*[0-9a-f]{10})*)?[ \t]*\]")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def amount(value: Any) -> Decimal:
    require(isinstance(value, str), "Expected a decimal string")
    result = Decimal(value)
    require(result.is_finite() and result >= 0, "Invalid USD amount")
    return result


def count(value: Any) -> int:
    require(type(value) is int and value >= 0, "Invalid token or node count")
    return value


def cost(inp: int, out: int) -> Decimal:
    return (5 * Decimal(inp) + 20 * Decimal(out)) / 1_000_000


def object_file(path: Path) -> dict[str, Any]:
    require(not path.is_symlink(), "Symlink forbidden in evidence journal")
    value = read_json(path)
    require(isinstance(value, dict), "Expected JSON object: " + path.name)
    return value


def independent_grade(line: str, reference: list[str]) -> dict[str, Any]:
    """Independent implementation for the only permitted disclosed-line forms."""
    require(isinstance(line, str) and (line == "" or LINE.fullmatch(line) is not None),
            "Noncanonical public final line")
    truth = set(reference)
    nodes = set()
    if line:
        nodes = {n.strip() for n in line[line.index("[")+1:-1].split(",") if n.strip()}
    overlap = len(nodes & truth)
    if not line:
        p = r = f = 0.0
    elif not truth and not nodes:
        p = r = f = 1.0
    else:
        p = overlap / len(nodes) if nodes else 0.0
        r = overlap / len(truth) if truth else 0.0
        f = 2 * overlap / (len(nodes) + len(truth)) if nodes or truth else 0.0
    return {"f1": f, "precision": p, "recall": r, "parse_failed": not bool(line),
            "predicted_nodes": len(nodes), "reference_nodes": len(truth)}


def grade_equal(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    if set(actual) != set(expected):
        return False
    for key, value in expected.items():
        got = actual[key]
        if isinstance(value, float):
            if type(got) not in (int, float) or not math.isclose(got, value, rel_tol=1e-12, abs_tol=1e-12):
                return False
        elif type(got) is not type(value) or got != value:
            return False
    return True


def verify_journal(bundle: Path, index: Path, *, expected_index_sha256: str = INDEX_SHA256) -> dict[str, Any]:
    """Verify complete terminal journals; missing/changed records fail closed.

    The optional index digest is for fixture tests; the CLI always uses the
    pinned production digest. A changed preflight must be reviewed separately,
    not represented as a verified paid campaign.
    """
    manifest_raw = read_bytes(MANIFEST)
    require(digest(manifest_raw) == MANIFEST_SHA256, "Frozen manifest digest mismatch")
    manifest = json.loads(manifest_raw)
    require(digest(read_bytes(ARCHIVE)) == ARCHIVE_SHA256, "Frozen preflight archive digest mismatch")
    with zipfile.ZipFile(ARCHIVE) as z:
        require(z.namelist() == ["preflight.json"], "Unexpected archive members")
        frozen = json.loads(z.read("preflight.json"))
    require(frozen["manifest_sha256"] == MANIFEST_SHA256
            and frozen["reference_index_sha256"] == INDEX_SHA256,
            "Frozen preflight source commitments mismatch")
    require(digest(read_bytes(index)) == expected_index_sha256, "Reference index digest mismatch")
    refs = {row["id"]: row for row in read_jsonl(index)}
    plan = object_file(bundle / "plan.json")
    plan_sha = digest(read_bytes(bundle / "plan.json"))
    expected_plan = {
        "schema_version": "graphwalks-openai-paid-campaign-plan-v1",
        "frozen_preflight_archive_sha256": ARCHIVE_SHA256,
        "manifest_sha256": MANIFEST_SHA256,
        "reference_index_sha256": INDEX_SHA256,
        "model": MODEL, "reasoning_effort": "xhigh", "max_output_tokens": OUTPUT_LIMIT,
        "service_tier": "default", "prompt_cache_options": {"mode": "explicit", "ttl": "30m"},
        "authorized_ceiling_usd": "25", "publication": "PUBLISH_FINAL_LINE",
        "published_claim_reproduced": False,
    }
    require(all(plan.get(k) == v for k, v in expected_plan.items()), "Plan protocol mismatch")
    fresh = plan["fresh_preflight"]
    require(fresh == {k: v for k, v in frozen.items()
                       if k not in ("manifest_sha256", "reference_index_sha256")},
            "Fresh preflight differs from frozen measurement")
    source_rows = fresh["tasks"]
    require(len(source_rows) == len(manifest["tasks"]) == 16, "Wrong cohort size")
    require(sum(r["status"] == "feasible" for r in source_rows) == 8, "Wrong feasible denominator")
    reserve = Decimal(0)
    records = []
    disclosed = 0
    withheld = 0
    attempted = 0
    known_cost = Decimal(0)
    known = 0
    uncertain = False
    stopped = False
    expected_files = {"plan.json", "summary.json"}
    for n, (task, source) in enumerate(zip(manifest["tasks"], source_rows), 1):
        ident = task["id"]
        require(all(source.get(k) == v for k, v in task.items()), "Source row mismatch: " + ident)
        ref = refs[ident]
        require(ref["problem_type"] == "bfs" and ref["prompt_sha256"] == task["prompt_sha256"]
                and ref["prompt_chars_actual"] == task["prompt_chars"], "Reference mismatch: " + ident)
        answer = ref["answer_nodes"]
        require(isinstance(answer, list) and all(isinstance(x, str) and x for x in answer),
                "Invalid reference nodes")
        prefix = f"task-{n:02d}"
        name = prefix + "-outcome.json"
        expected_files.add(name)
        row = object_file(bundle / name)
        require(row["plan_sha256"] == plan_sha, "Outcome plan commitment mismatch: " + ident)
        require(all(row.get(k) == v for k, v in source.items() if k != "status"),
                "Outcome source fields mismatch: " + ident)
        status = row["status"]
        flag = row["generation_attempted"]
        require(type(flag) is bool, "Invalid generation-attempt marker")
        inp = count(source["input_tokens"])
        fits = inp <= 922000 and inp + OUTPUT_LIMIT <= 1050000
        if not fits:
            require(source["status"] == status == "context_blocked" and not flag
                    and source["reservation_usd"] is None, "Invalid blocked outcome")
        else:
            require(source["status"] == "feasible", "Invalid feasible source")
            reserved = amount(source["reservation_usd"])
            require(reserved == cost(inp, OUTPUT_LIMIT), "Reservation arithmetic mismatch")
            reserve += reserved
            require(status in ("graded", "incomplete", "refused", "unattempted",
                               "generation_or_accounting_uncertain"), "Invalid terminal status")
            require(flag == (status != "unattempted"), "Attempt/status mismatch")
            require(not (stopped and flag), "Generation after stopped campaign")
            if status == "unattempted":
                stopped = True
            if status == "generation_or_accounting_uncertain":
                require(row.get("retry_permitted") is False, "Uncertain request retry marker")
                stopped = uncertain = True
        if flag:
            attempted += 1
            name = prefix + "-intent.json"
            expected_files.add(name)
            require(object_file(bundle / name) == {
                "status": "generation_intent", "id": ident, "plan_sha256": plan_sha,
                "reservation_usd": source["reservation_usd"]}, "Intent mismatch: " + ident)
        if status in ("graded", "incomplete", "refused"):
            require(row["returned_model"] == MODEL, "Returned model mismatch")
            actual_input = count(row["input_tokens_actual"])
            output = count(row["output_tokens_actual"])
            estimate = amount(row["upper_usage_cost_usd"])
            require(actual_input == inp and output <= OUTPUT_LIMIT
                    and estimate == cost(actual_input, output)
                    and estimate <= amount(source["reservation_usd"]), "Usage accounting mismatch")
            require(isinstance(row["response_sha256"], str) and HEX.fullmatch(row["response_sha256"]) is not None,
                    "Invalid response commitment")
            known += 1
            known_cost += estimate
        else:
            require(not any(k in row for k in ("input_tokens_actual", "output_tokens_actual",
                                              "upper_usage_cost_usd", "response_sha256")),
                    "Unexpected usage claim for unaccounted outcome")
        if status == "graded":
            grade = row["grade"]
            require(isinstance(grade, dict) and set(grade) == {
                "f1", "precision", "recall", "parse_failed", "predicted_nodes", "reference_nodes"},
                "Invalid grade fields")
            require(type(grade["parse_failed"]) is bool and count(grade["reference_nodes"]) == len(set(answer)),
                    "Reference denominator mismatch")
            count(grade["predicted_nodes"])
            require(all(type(grade[k]) in (int, float) and math.isfinite(grade[k]) and 0 <= grade[k] <= 1
                        for k in ("f1", "precision", "recall")), "Invalid grade value")
            require(isinstance(row["answer_sha256"], str) and HEX.fullmatch(row["answer_sha256"]) is not None,
                    "Invalid full-answer commitment")
            if row["scoring_evidence_status"] == "final_line_exported":
                line = row["final_line"]
                recomputed = independent_grade(line, answer)
                require(digest(line.encode()) == row["final_line_sha256"], "Final-line digest mismatch")
                require(grade_equal(grade, recomputed), "Disclosed-line score mismatch: " + ident)
                disclosed += 1
            else:
                require(row["scoring_evidence_status"] == "withheld_noncanonical_final_line"
                        and "final_line" not in row and "final_line_sha256" not in row,
                        "Invalid withheld evidence status")
                withheld += 1
        else:
            require(not any(k in row for k in ("grade", "final_line", "final_line_sha256", "answer_sha256")),
                    "Score on ungraded task")
        records.append(row)
    require(reserve == amount(fresh["total_feasible_reservation_usd"]) <= CEILING,
            "Aggregate reservation mismatch")
    require(attempted <= 8 and known_cost <= reserve, "Campaign exceeds reservation")
    require({p.name for p in bundle.iterdir()} == expected_files, "Missing or unexpected journal member")
    summary = object_file(bundle / "summary.json")
    require(summary["schema_version"] == "graphwalks-openai-paid-campaign-result-v1"
            and summary["plan_sha256"] == plan_sha and summary["tasks"] == records
            and summary["published_claim_reproduced"] is False, "Summary commitments mismatch")
    expected_status = "stopped_uncertain" if uncertain else "stopped_time_limit" if stopped else "finished"
    require(summary["status"] == expected_status, "Summary termination mismatch")
    bands = {}
    for name, subset in (("overall", records), ("short", [r for r in records if r["band"] == "short"]),
                         ("long", [r for r in records if r["band"] == "long"])):
        scores = [r["grade"]["f1"] for r in subset if r["status"] == "graded"]
        stats = {"selected": len(subset), "statuses": dict(Counter(r["status"] for r in subset)),
                 "graded": len(scores), "conditional_mean_f1": sum(scores)/len(scores) if scores else None,
                 "full_selected_mean_f1": sum(scores)/len(subset) if scores and len(scores) == len(subset) else None,
                 "parse_failures": sum(r["grade"]["parse_failed"] for r in subset if r["status"] == "graded")}
        require(summary[name] == stats, "Summary denominator or grade arithmetic mismatch: " + name)
        bands[name] = stats
    require(summary["generation_attempted"] == attempted and summary["known_usage_records"] == known
            and amount(summary["known_usage_cost_estimate_usd"]) == known_cost
            and summary["all_attempted_usage_accounted"] is (known == attempted), "Summary usage mismatch")
    return {"schema_version": "graphwalks-openai-campaign-verification-v1",
            "status": "complete_journal_checked", "campaign_status": expected_status,
            "plan_sha256": plan_sha, "reference_index_sha256": expected_index_sha256,
            "selected_tasks": 16, "attempted": attempted, "known_usage_records": known,
            "known_usage_cost_estimate_usd": str(known_cost),
            "disclosed_scores_recomputed": disclosed, "withheld_scores_not_recomputed": withheld,
            "all_graded_scores_recomputed": disclosed > 0 and withheld == 0,
            "bands": bands, "published_claim_reproduced": False,
            "provider_execution_authenticated": False, "full_answer_extraction_verified": False,
            "actual_invoice_verified": False, "external_third_party_review": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = verify_journal(args.bundle, args.index)
    except (ReplayError, OSError, ValueError, KeyError, TypeError, InvalidOperation, zipfile.BadZipFile) as exc:
        parser.exit(2, f"Campaign verification failed: {exc}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
