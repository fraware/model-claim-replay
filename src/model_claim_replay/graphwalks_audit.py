"""Offline integrity audit of a private GraphWalks execution journal.

This checks consistency of locally self-reported artifacts. It does not
authenticate model identity, provider billing, or the remote execution.
Only digests and score-readiness metadata enter the audit report; raw answers
and original prompts stay in the private run directory.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from .core import ReplayError, read_bytes, read_json, sha256_bytes
from .graphwalks_runtime import (
    DATASET_REVISION, MODEL, _USAGE_OVERRUN_ERROR, _load_plan,
    _reported_usage_exceeds_reservation,
)

_USAGE_FIELDS = frozenset({
    "total_input_tokens", "total_output_tokens", "total_thought_tokens",
    "total_cached_tokens", "total_tool_use_tokens",
})
_INTENT_FIELDS = frozenset({
    "id", "plan_sha256", "input_sha256", "reserved_ceiling_usd",
    "request_state", "started_utc",
})
_RESULT_FIELDS = frozenset({"id", "status", "usage", "error_type", "output"})


def audit_graphwalks_run(plan_path: Path, index_path: Path, run_dir: Path) -> dict[str, Any]:
    """Verify local task records, budget commitments and response consistency.

    Uses the full source-index pin and historical plan validation, without
    imposing the execution-only 24-hour token-plan expiration. This audit
    intentionally avoids opening the large Parquet or making API requests.

    Raises ReplayError on any malformed, unbound or extraneous attempt file.
    A SHA-256 check over self-reported files does not attest their origin.
    """
    plan = _load_plan(plan_path, index_path, require_fresh=False)
    plan_digest = sha256_bytes(read_bytes(plan_path))
    manifest_path = run_dir / "run.json"
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict) or (
        manifest.get("schema_version") != "graphwalks-paid-run-v1"
        or manifest.get("model") != MODEL
        or manifest.get("plan_sha256") != plan_digest
        or manifest.get("candidate_dataset_revision") != DATASET_REVISION
        or manifest.get("provenance") != "api_self_reported_no_provider_attestation"
        or manifest.get("content_policy") != "raw_model_answers_private_no_source_prompts"
    ):
        raise ReplayError("Private run manifest does not match the pinned execution plan")

    directory = run_dir / "attempts"
    if not directory.is_dir() or directory.is_symlink():
        raise ReplayError("Private run lacks a valid attempts directory")

    valid_names = {
        f"{task['id']}.{extension}.json"
        for task in plan["planned_tasks"] for extension in ("intent", "result")
    }
    for entry in directory.iterdir():
        if entry.is_symlink() or not entry.is_file() or entry.name not in valid_names:
            raise ReplayError("Private run has an unexpected attempt artifact")

    entries: list[dict[str, Any]] = []
    reserved = Decimal(0)
    attempted = complete = errors = unresolved = 0
    missing_usage = 0
    for task in plan["planned_tasks"]:
        task_id = task["id"]
        intent_path = directory / f"{task_id}.intent.json"
        result_path = directory / f"{task_id}.result.json"
        record: dict[str, Any] = {"id": task_id, "status": "not_attempted"}
        if not intent_path.is_file():
            if result_path.exists():
                raise ReplayError("Response record exists without an attempt intent")
            entries.append(record)
            continue

        intent = read_json(intent_path)
        if not isinstance(intent, dict) or set(intent) != _INTENT_FIELDS or (
            intent.get("id") != task_id
            or intent.get("plan_sha256") != plan_digest
            or intent.get("input_sha256") != task["prompt_sha256"]
            or intent.get("reserved_ceiling_usd") != task["maximum_reserved_cost_usd"]
            or intent.get("request_state") != "possibly_billable_once_intent_created"
            or not isinstance(intent.get("started_utc"), str)
        ):
            raise ReplayError(f"Attempt intent fails plan binding for {task_id}")
        reserved += Decimal(task["maximum_reserved_cost_usd"])
        attempted += 1
        record["intent_sha256"] = sha256_bytes(read_bytes(intent_path))
        record["status"] = "unresolved"

        if not result_path.is_file():
            unresolved += 1
            entries.append(record)
            continue
        result = read_json(result_path)
        if not isinstance(result, dict) or not set(result).issubset(_RESULT_FIELDS) or (
            result.get("id") != task_id or result.get("status") not in ("ok", "error")
        ):
            raise ReplayError(f"Malformed or unbound provider result for {task_id}")
        if "usage" not in result or not isinstance(result["usage"], dict):
            raise ReplayError(f"Provider usage must be a structured record for {task_id}")
        if not set(result["usage"]).issubset(_USAGE_FIELDS):
            raise ReplayError(f"Unexpected provider usage field for {task_id}")
        for value in result["usage"].values():
            if value is not None and (type(value) is not int or value < 0):
                raise ReplayError(f"Invalid provider token usage for {task_id}")
        overrun = _reported_usage_exceeds_reservation(
            result["usage"],
            planned_input=task["input_tokens"],
            output_allowance=plan["max_output_tokens"],
        )
        if overrun and (
            result["status"] != "error"
            or result.get("error_type") != _USAGE_OVERRUN_ERROR
        ):
            raise ReplayError(
                f"Provider usage exceeds the approved reservation without "
                f"quarantine for {task_id}"
            )
        if not overrun and result.get("error_type") == _USAGE_OVERRUN_ERROR:
            raise ReplayError(
                f"Unsubstantiated provider usage overrun marker for {task_id}"
            )
        if result["status"] == "ok":
            if not isinstance(result.get("output"), str) or result.get("error_type") is not None:
                raise ReplayError(f"Successful response lacks valid text for {task_id}")
            if (result["usage"].get("total_input_tokens") is None
                    or result["usage"].get("total_output_tokens") is None):
                raise ReplayError(f"Successful response lacks provider usage for {task_id}")
            complete += 1
        else:
            if "output" in result or result.get("error_type") is not None and not isinstance(result["error_type"], str):
                raise ReplayError(f"Error result contains invalid response fields for {task_id}")
            errors += 1
        if (result["usage"].get("total_input_tokens") is None
                or result["usage"].get("total_output_tokens") is None):
            missing_usage += 1
        record["status"] = "completed" if result["status"] == "ok" else "error"
        record["result_sha256"] = sha256_bytes(read_bytes(result_path))
        entries.append(record)

    return {
        "schema_version": "graphwalks-private-journal-audit-v1",
        "evidence_level": "self_reported_local_journal_consistency_only",
        "plan_sha256": plan_digest,
        "run_manifest_sha256": sha256_bytes(read_bytes(manifest_path)),
        "index_sha256": plan["index_sha256"],
        "source_parquet_sha256": plan["parquet_sha256"],
        "model_declared": MODEL,
        "planned": len(entries),
        "attempted": attempted,
        "completed": complete,
        "failed": errors,
        "unresolved": unresolved,
        "not_attempted": len(entries) - attempted,
        "responses_missing_usage": missing_usage,
        "budget_reserved_usd": str(reserved),
        "comparison_status": "not_comparable",
        "execution_authenticated": False,
        "entries": entries,
    }
