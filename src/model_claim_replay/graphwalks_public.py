"""Cross-check three redacted GraphWalks artifacts, entirely offline.

This validator establishes only consistency of the supplied self-reported
receipts. No raw model outputs, original answer index, provider credentials,
network access, or third-party dependencies are needed. A coherent set of
fabricated receipts will also pass; this is not provider attestation.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .core import ReplayError, read_bytes, read_json, sha256_bytes
from .graphwalks_runtime import (
    CONTEXT_LIMIT,
    DATASET_REVISION,
    DATASET_SHA256,
    INDEX_SHA256,
    INPUT_USD_PER_M,
    MODEL,
    OUTPUT_USD_PER_M,
    PRICE_SOURCE,
    SCHEMA,
    SELECTION_POLICY,
)

_SHA = re.compile(r"^[0-9a-f]{64}$")
_TASK = re.compile(r"^bfs-row-[0-9]{6}$")
_STATES = frozenset({"completed", "error", "unresolved", "not_attempted"})
_PLAN_FIELDS = frozenset({
    "schema_version", "evidence_level", "model", "thinking_level",
    "max_output_tokens", "dataset_revision", "parquet_sha256",
    "index_sha256", "reference_task_count", "selection_policy",
    "selection_counts", "planned_tasks", "planned_count", "context_limit",
    "pricing", "created_utc", "maximum_reserved_cost_usd",
    "blocked_for_context", "comparison_status", "limitations",
})
_PLAN_TASK_FIELDS = frozenset({
    "id", "prompt_sha256", "input_tokens",
    "fits_context_with_output_allowance", "maximum_reserved_cost_usd",
})
_AUDIT_FIELDS = frozenset({
    "schema_version", "evidence_level", "plan_sha256", "run_manifest_sha256",
    "index_sha256", "source_parquet_sha256", "model_declared", "planned",
    "attempted", "completed", "failed", "unresolved", "not_attempted",
    "responses_missing_usage", "budget_reserved_usd", "comparison_status",
    "execution_authenticated", "entries",
})
_GRADE_FIELDS = frozenset({
    "schema_version", "evidence_level", "dataset_revision_user_declared",
    "reference_index_sha256", "response_file_sha256", "task_count",
    "graded", "parsed", "malformed", "api_errors", "missing", "mean_f1",
    "scored_subset_mean_f1_diagnostic", "comparison_status",
    "comparison_explanation", "results",
})
_GRADED_ROW_FIELDS = frozenset({
    "id", "status", "f1", "precision", "recall",
    "parse_failed", "predicted_nodes", "reference_nodes",
})


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise ReplayError("Public GraphWalks receipts: " + message)


def _count(value: Any, description: str) -> int:
    _check(type(value) is int and value >= 0, f"invalid {description} count")
    return value


def _money(value: Any, description: str) -> Decimal:
    _check(isinstance(value, str), f"invalid {description} decimal")
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ReplayError(f"Public GraphWalks receipts: invalid {description} decimal") from exc
    _check(amount.is_finite() and amount >= 0, f"invalid {description} amount")
    return amount


def _ratio(value: Any, description: str) -> float:
    _check(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
           f"invalid {description}")
    return float(value)


def _same_score(actual: Any, expected: float, description: str) -> None:
    _check(type(actual) in (int, float) and math.isfinite(actual)
           and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-12),
           f"inconsistent {description}")


def _digest(value: Any, description: str) -> None:
    _check(isinstance(value, str) and _SHA.fullmatch(value) is not None,
           f"invalid {description} SHA-256")


def verify_public_graphwalks_receipts(
    plan_path: Path, audit_path: Path, grades_path: Path,
) -> dict[str, Any]:
    """Check internal consistency of public receipts from a single diagnostic.

    A passing result confirms only that supplied metadata, task statuses and
    arithmetic are mutually consistent. Hashes bind these local input files
    to this receipt; they do not authenticate the origin of their contents.
    """
    plan, audit, grades = (read_json(p) for p in (plan_path, audit_path, grades_path))
    _check(all(isinstance(x, dict) for x in (plan, audit, grades)),
           "each artifact must be a JSON object")

    _check(set(plan) == _PLAN_FIELDS, "token plan has missing or unexpected fields")
    _check(set(audit) == _AUDIT_FIELDS, "audit has missing or unexpected fields")
    _check(set(grades) == _GRADE_FIELDS, "scorer has missing or unexpected fields")
    _check(plan.get("schema_version") == SCHEMA, "unsupported token plan")
    _check(plan.get("evidence_level") ==
           "candidate_public_dataset_api_token_preflight_not_a_model_evaluation",
           "token plan improperly claims evaluation evidence")
    _check(plan.get("thinking_level") in ("low", "medium", "high", "xhigh"),
           "invalid model thinking configuration")
    _check(plan.get("pricing") == {
        "input_usd_per_m": str(INPUT_USD_PER_M),
        "output_usd_per_m": str(OUTPUT_USD_PER_M),
        "as_of": "2026-11-20", "source": PRICE_SOURCE,
        "tier": "standard", "currency": "USD",
    }, "token plan has incorrect pricing assumptions")
    _check(isinstance(plan.get("created_utc"), str), "token plan has no timestamp")
    try:
        created = dt.datetime.fromisoformat(plan["created_utc"])
    except ValueError as exc:
        raise ReplayError("Public GraphWalks receipts: invalid token plan timestamp") from exc
    _check(created.tzinfo is not None and created.utcoffset() is not None,
           "token plan timestamp lacks timezone")
    _check(isinstance(plan.get("limitations"), list)
           and all(isinstance(x, str) for x in plan["limitations"]),
           "token plan limitations are malformed")
    _check(plan.get("model") == MODEL, "unsupported model identity")
    _check(plan.get("dataset_revision") == DATASET_REVISION
           and plan.get("parquet_sha256") == DATASET_SHA256
           and plan.get("index_sha256") == INDEX_SHA256,
           "plan source does not match the pinned public candidate")
    _check(plan.get("selection_policy") == SELECTION_POLICY,
           "unsupported task selection policy")
    _check(plan.get("comparison_status") == "not_comparable",
           "plan improperly asserts publisher comparability")
    _check(plan.get("context_limit") == CONTEXT_LIMIT, "plan context limit differs")
    _check(plan.get("reference_task_count") == 200, "plan reference count differs")
    output_limit = _count(plan.get("max_output_tokens"), "output allowance")
    _check(1 <= output_limit <= 32768, "invalid output allowance")
    planned = plan.get("planned_tasks")
    _check(isinstance(planned, list) and 1 <= len(planned) <= 200,
           "plan has no valid task cohort")
    _check(plan.get("planned_count") == len(planned), "plan task count differs")
    _check(plan.get("selection_counts") == {
        "short_context": (len(planned) + 1) // 2,
        "long_context": len(planned) // 2,
    }, "plan context-band counts differ")

    task_ids: list[str] = []
    reservation_by_id: dict[str, Decimal] = {}
    for task in planned:
        _check(isinstance(task, dict) and set(task) == _PLAN_TASK_FIELDS,
               "invalid or unredacted planned task")
        ident = task.get("id")
        _check(isinstance(ident, str) and _TASK.fullmatch(ident) is not None,
               "invalid planned task identity")
        _check(ident not in reservation_by_id, "duplicate planned task")
        _digest(task.get("prompt_sha256"), "prompt")
        tokens = _count(task.get("input_tokens"), "input tokens")
        _check(tokens > 0, "nonempty prompt has zero input tokens")
        _check(task.get("fits_context_with_output_allowance") is
               (tokens + output_limit <= CONTEXT_LIMIT),
               "plan task context feasibility differs")
        expected = (Decimal(tokens) * INPUT_USD_PER_M
                    + Decimal(output_limit) * OUTPUT_USD_PER_M) / Decimal(1_000_000)
        reservation = _money(task.get("maximum_reserved_cost_usd"), "task reservation")
        _check(reservation == expected, "task reservation arithmetic differs")
        reservation_by_id[ident] = reservation
        task_ids.append(ident)
    _check(_money(plan.get("maximum_reserved_cost_usd"), "plan reservation")
           == sum(reservation_by_id.values(), Decimal(0)),
           "plan total reservation differs")
    _check(plan.get("blocked_for_context") ==
           sum(not task["fits_context_with_output_allowance"] for task in planned),
           "plan blocked-context count differs")

    plan_digest = sha256_bytes(read_bytes(plan_path))
    _check(audit.get("schema_version") == "graphwalks-private-journal-audit-v1",
           "unsupported journal audit")
    _check(audit.get("evidence_level") == "self_reported_local_journal_consistency_only",
           "invalid journal evidence level")
    _check(audit.get("plan_sha256") == plan_digest,
           "journal audit does not bind the supplied token plan")
    _check(audit.get("index_sha256") == INDEX_SHA256
           and audit.get("source_parquet_sha256") == DATASET_SHA256
           and audit.get("model_declared") == MODEL,
           "journal source or model identity differs")
    _digest(audit.get("run_manifest_sha256"), "private run manifest")
    _check(audit.get("comparison_status") == "not_comparable"
           and audit.get("execution_authenticated") is False,
           "journal claims unsupported comparability or authentication")
    entries = audit.get("entries")
    _check(isinstance(entries, list) and len(entries) == len(planned),
           "audit task count differs")
    statuses: dict[str, str] = {}
    for task, entry in zip(planned, entries):
        _check(isinstance(entry, dict) and entry.get("id") == task["id"],
               "audit task order or identity differs")
        status = entry.get("status")
        _check(type(status) is str and status in _STATES, "invalid audit task status")
        expected_fields = {"id", "status"}
        if status != "not_attempted":
            expected_fields.add("intent_sha256")
        if status in ("completed", "error"):
            expected_fields.add("result_sha256")
        _check(set(entry) == expected_fields, "audit entry has unexpected fields")
        ident = task["id"]
        statuses[ident] = status
        if status == "not_attempted":
            _check("intent_sha256" not in entry and "result_sha256" not in entry,
                   "unattempted task has journal hashes")
        else:
            _digest(entry.get("intent_sha256"), "attempt intent")
            if status in ("completed", "error"):
                _digest(entry.get("result_sha256"), "attempt result")
            else:
                _check("result_sha256" not in entry,
                       "unresolved request has a result hash")
    expected_counts = Counter(statuses.values())
    _check(audit.get("planned") == len(planned), "audit planned count differs")
    _check(audit.get("attempted") == len(planned) - expected_counts["not_attempted"],
           "audit attempt count differs")
    for field, status in (("completed", "completed"), ("failed", "error"),
                          ("unresolved", "unresolved"), ("not_attempted", "not_attempted")):
        _check(audit.get(field) == expected_counts[status], f"audit {field} count differs")
    reserved = sum((reservation_by_id[k] for k, v in statuses.items()
                    if v != "not_attempted"), Decimal(0))
    _check(_money(audit.get("budget_reserved_usd"), "audit reservation") == reserved,
           "audit spending reservation differs")
    _check(_count(audit.get("responses_missing_usage"), "missing usage")
           <= expected_counts["completed"] + expected_counts["error"],
           "audit missing-usage count exceeds recorded results")

    _check(grades.get("schema_version") == "graphwalks-offline-grade-v1",
           "unsupported scoring receipt")
    _check(grades.get("evidence_level") == "locally_imported_response_scores_unattested",
           "invalid scoring evidence level")
    _check(grades.get("dataset_revision_user_declared") == DATASET_REVISION
           and grades.get("reference_index_sha256") == INDEX_SHA256,
           "scorer source binding differs")
    _digest(grades.get("response_file_sha256"), "private response file")
    _check(grades.get("comparison_status") == "not_comparable",
           "scorer improperly claims publisher comparability")
    rows = grades.get("results")
    _check(isinstance(rows, list) and len(rows) == 200, "scorer did not cover 200 references")
    seen: set[str] = set()
    graded = malformed = errors = missing = 0
    f1_sum = 0.0
    for row in rows:
        _check(isinstance(row, dict), "invalid score row")
        ident = row.get("id")
        _check(isinstance(ident, str) and _TASK.fullmatch(ident) is not None
               and ident not in seen, "invalid or duplicate scored task identity")
        seen.add(ident)
        status = row.get("status")
        intended = statuses.get(ident, "not_attempted")
        expected_status = {"completed": "graded", "error": "error",
                           "unresolved": "missing", "not_attempted": "missing"}[intended]
        _check(status == expected_status, f"scored status differs from journal for {ident}")
        if status == "graded":
            _check(set(row) == _GRADED_ROW_FIELDS,
                   "graded result has missing or unexpected fields")
            graded += 1
            p, r, f1 = (_ratio(row.get(key), f"{key} for {ident}")
                        for key in ("precision", "recall", "f1"))
            _check(type(row.get("parse_failed")) is bool, "invalid parser status")
            predicted = _count(row.get("predicted_nodes"), "predicted nodes")
            reference = _count(row.get("reference_nodes"), "reference nodes")
            failed = row["parse_failed"]
            if failed:
                _check(p == r == f1 == 0, "malformed answer has nonzero score")
                malformed += 1
            else:
                if not predicted and not reference:
                    _check(p == r == f1 == 1, "empty reference and output must score one")
                elif not predicted or not reference:
                    _check(p == r == f1 == 0, "single empty node set must score zero")
                else:
                    overlap_p, overlap_r = p * predicted, r * reference
                    _check(math.isclose(overlap_p, overlap_r, abs_tol=1e-9)
                           and math.isclose(overlap_p, round(overlap_p), abs_tol=1e-9)
                           and 0 <= overlap_p <= min(predicted, reference) + 1e-9,
                           "precision/recall imply an impossible node overlap")
                expected_f1 = 2 * p * r / (p + r) if (p + r) else 0.0
                _same_score(f1, expected_f1, f"F1 for {ident}")
                _check((predicted > 0 or p in (0, 1))
                       and (reference > 0 or r in (0, 1)),
                       "invalid zero-set precision or recall")
            f1_sum += f1
        else:
            _check(set(row) == {"id", "status"},
                   "an ungraded task contains scoring fields")
            errors += int(status == "error")
            missing += int(status == "missing")
    _check(set(task_ids).issubset(seen), "scorer omitted planned task identities")
    _check(grades.get("task_count") == 200, "score denominator differs")
    for field, expected in (("graded", graded), ("parsed", graded - malformed),
                             ("malformed", malformed), ("api_errors", errors),
                             ("missing", missing)):
        _check(grades.get(field) == expected, f"scorer {field} count differs")
    _check(graded + errors + missing == 200, "scorer task accounting differs")
    if graded:
        _same_score(grades.get("scored_subset_mean_f1_diagnostic"), f1_sum / graded,
                    "graded subset mean")
    else:
        _check(grades.get("scored_subset_mean_f1_diagnostic") is None,
               "empty subset has a mean score")
    if graded == 200:
        _same_score(grades.get("mean_f1"), f1_sum / 200, "full cohort mean")
    else:
        _check(grades.get("mean_f1") is None, "partial cohort claims a full mean")

    return {
        "schema_version": "graphwalks-public-receipt-verification-v1",
        "verification_status": "internally_consistent_self_reported_only",
        "claim_reproduced": False,
        "provider_execution_authenticated": False,
        "score_recomputed_from_model_outputs": False,
        "source_dataset_reverified": False,
        "limitations": [
            "The source Parquet, answer index and raw model outputs were not supplied.",
            "A coherent fabricated or jointly altered receipt set may pass these checks.",
            "Provider identity, model execution, grading correctness and billing are unattested.",
            "The claimed source cohort and publisher protocol have not been independently matched.",
        ],
        "input_sha256": {
            "token_plan": plan_digest,
            "execution_audit": sha256_bytes(read_bytes(audit_path)),
            "score_report": sha256_bytes(read_bytes(grades_path)),
        },
        "planned": len(planned),
        "attempted": audit["attempted"],
        "completed": expected_counts["completed"],
        "failed": expected_counts["error"],
        "unresolved": expected_counts["unresolved"],
        "graded": graded,
        "task_count": 200,
        "scored_subset_mean_f1_diagnostic": f1_sum / graded if graded else None,
        "comparison_status": "not_comparable",
    }
