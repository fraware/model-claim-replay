"""Offline score verification from an explicitly published final-line receipt.

Checks source-index bytes, source task, local commitments and the deterministic
GraphWalks score. It does not authenticate provider execution, prove fidelity
of final-line extraction to an unpublished full answer, or verify charges.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .core import ReplayError, canonical_json, read_bytes, read_json, read_jsonl, sha256_bytes
from .graphwalks import grade_response
from .graphwalks_runtime import DATASET_REVISION, DATASET_SHA256, INDEX_SHA256
from .openai_graphwalks import MODEL, TASK, PUBLISH_FINAL_LINE, public_final_line


def verify(bundle: Path, index: Path, *, expected_index_sha256: str = INDEX_SHA256) -> dict[str, Any]:
    """Verify a single-task scoring receipt against a pinned reference index.

    The keyword digest is available for offline test fixtures. The public CLI
    always uses the production source commitment.
    """
    def require(condition: bool, message: str) -> None:
        if not condition:
            raise ReplayError(message)

    def obj(name: str) -> dict[str, Any]:
        value = read_json(bundle / name)
        require(isinstance(value, dict), "Expected JSON object: " + name)
        return value

    require(sha256_bytes(read_bytes(index)) == expected_index_sha256, "Reference index SHA-256 mismatch")
    plan, intent, result, evidence = (
        obj("plan.json"), obj("intent.json"), obj("outcome.json"), obj("scoring-evidence.json")
    )
    plan_digest = sha256_bytes(read_bytes(bundle / "plan.json"))
    require(plan.get("schema_version") == "graphwalks-openai-single-task-v1"
            and plan.get("mode") == "paid_diagnostic"
            and plan.get("scoring_evidence_publication") == PUBLISH_FINAL_LINE,
            "Expected explicitly published paid diagnostic plan")
    require(plan.get("dataset_revision") == DATASET_REVISION
            and plan.get("parquet_sha256") == DATASET_SHA256
            and plan.get("reference_index_sha256") == expected_index_sha256,
            "Source commitments differ from pinned GraphWalks source")
    require(intent.get("status") == "generation_intent"
            and intent.get("plan_sha256") == plan_digest,
            "Generation intent does not bind the plan")
    require(result.get("schema_version") == "graphwalks-openai-single-task-result-v1"
            and result.get("status") == "graded"
            and result.get("scoring_evidence_status") == "final_line_exported"
            and result.get("comparison_status") == "not_comparable"
            and result.get("published_claim_reproduced") is False,
            "Expected a graded, non-comparable diagnostic with published final line")
    require(set(evidence) == {"schema_version", "task_id", "model", "plan_sha256",
                              "answer_sha256", "final_line", "final_line_sha256"}
            and evidence.get("schema_version") == "graphwalks-openai-final-line-v1",
            "Unexpected scoring evidence fields or schema")
    for record in (plan, result, evidence):
        require(record.get("model") == MODEL and record.get("task_id") == TASK,
                "Model or task identity mismatch")
    require(result.get("plan_sha256") == evidence.get("plan_sha256") == plan_digest,
            "Result or scoring evidence does not bind the plan")
    require(result.get("scoring_evidence_sha256") == sha256_bytes(read_bytes(bundle / "scoring-evidence.json")),
            "Scoring evidence SHA-256 mismatch")
    answer_digest = result.get("answer_sha256")
    require(isinstance(answer_digest, str) and len(answer_digest) == 64
            and all(c in "0123456789abcdef" for c in answer_digest)
            and evidence.get("answer_sha256") == answer_digest, "Answer commitment mismatch")
    line = evidence.get("final_line")
    require(isinstance(line, str) and "\n" not in line and public_final_line(line) == line,
            "Invalid exported final line")
    require(evidence.get("final_line_sha256") == sha256_bytes(line.encode("utf-8")),
            "Final-line SHA-256 mismatch")
    references = {row["id"]: row for row in read_jsonl(index)}
    reference = references.get(TASK)
    require(reference is not None and reference.get("problem_type") == "bfs"
            and reference.get("prompt_sha256") == plan.get("prompt_sha256"),
            "Pinned reference task or prompt commitment mismatch")
    grade = grade_response(line, reference.get("answer_nodes"))
    require(canonical_json(grade) == canonical_json(result.get("grade")),
            "Recorded grade differs from independently recomputed final-line grade")
    return {
        "schema_version": "graphwalks-openai-final-line-verification-v1",
        "status": "score_recomputed_from_disclosed_final_line",
        "model": MODEL, "task_id": TASK, "grade": grade,
        "plan_sha256": plan_digest,
        "reference_index_sha256": expected_index_sha256,
        "published_claim_reproduced": False,
        "provider_execution_authenticated": False,
        "full_answer_extraction_verified": False,
        "limitations": "Offline deterministic score check of a disclosed line against a pinned reference. Full answer, line extraction fidelity, provider execution and billing are not independently authenticated.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = verify(args.bundle, args.index)
    except (ReplayError, OSError, ValueError, TypeError) as exc:
        parser.exit(2, f"Final-line verification failed: {exc}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
