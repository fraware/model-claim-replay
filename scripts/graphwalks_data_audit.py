"""Verify the public long-context GraphWalks Parquet and export a BFS index.

This audit downloads the **public MIT-licensed** benchmark file at a pinned
upstream revision, independently hashes the actual bytes, and extracts a
compact reference index. It does not call any AI model, establish Google's
200-item selection, or reproduce a publisher's evaluation.

Requires pyarrow. Network traffic is limited to the pinned public Parquet URL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

DATASET = "openai/graphwalks"
FILENAME = "graphwalks_256k_to_1mil.parquet"
MAX_BYTES = 350_000_000
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")


class DataAuditError(ValueError):
    """The input file, upstream provenance or task schema fails validation."""


def validate_source(revision: str, sha256: str, size_bytes: int) -> None:
    """Validate exact, independently sourced file-identity parameters."""
    if not isinstance(revision, str) or not SHA40.fullmatch(revision):
        raise DataAuditError("Dataset revision must be a 40-character lowercase commit SHA")
    if not isinstance(sha256, str) or not SHA64.fullmatch(sha256):
        raise DataAuditError("Parquet digest must be a lowercase SHA-256")
    if type(size_bytes) is not int or not 0 < size_bytes <= MAX_BYTES:
        raise DataAuditError("Parquet expected size is outside the permitted range")


def download_checked_parquet(
    target: Path, *, revision: str, sha256: str, expected_bytes: int,
) -> None:
    """Stream bounded public bytes, checking both published size and digest."""
    validate_source(revision, sha256, expected_bytes)
    url = f"https://huggingface.co/datasets/{DATASET}/resolve/{revision}/{FILENAME}"
    request = urllib.request.Request(url, headers={"User-Agent": "model-claim-replay/0.1"})
    digest = hashlib.sha256()
    count = 0
    try:
        with urllib.request.urlopen(request, timeout=120) as response, target.open("xb") as output:
            length = response.headers.get("Content-Length")
            if length is not None and int(length) != expected_bytes:
                raise DataAuditError("Reported HTTP size differs from pinned upstream file size")
            while True:
                block = response.read(4 * 1024 * 1024)
                if not block:
                    break
                count += len(block)
                if count > expected_bytes:
                    raise DataAuditError("Download exceeds the pinned upstream file size")
                output.write(block)
                digest.update(block)
    except urllib.error.HTTPError as exc:
        raise DataAuditError(f"Pinned dataset HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise DataAuditError(f"Pinned dataset retrieval failed ({type(exc).__name__})") from exc
    if count != expected_bytes or digest.hexdigest() != sha256:
        raise DataAuditError("Downloaded Parquet bytes disagree with pinned size or SHA-256")


def make_reference_record(index: int, row: dict[str, Any]) -> dict[str, Any] | None:
    """Validate one dataset row; preserve only BFS source identity and answers."""
    if type(index) is not int or index < 0 or not isinstance(row, dict):
        raise DataAuditError("Invalid row index or record")
    problem_type = row.get("problem_type")
    if problem_type not in ("bfs", "parents"):
        raise DataAuditError("Unexpected public GraphWalks task type")
    prompt = row.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        raise DataAuditError("GraphWalks prompt is missing or not text")
    nodes = row.get("answer_nodes")
    if not isinstance(nodes, list) or any(not isinstance(v, str) or not v for v in nodes):
        raise DataAuditError("GraphWalks answer_nodes must be a string list")
    if problem_type != "bfs":
        return None
    actual_chars = len(prompt)
    declared_chars = row.get("prompt_chars")
    if declared_chars is not None and (type(declared_chars) is not int or declared_chars < 0):
        raise DataAuditError("Invalid source prompt_chars")
    return {
        "id": f"bfs-row-{index:06d}",
        "problem_type": "bfs",
        "answer_nodes": nodes,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_chars_actual": actual_chars,
        "prompt_chars_declared": declared_chars,
        "source_row_index": index,
    }


def audit_parquet(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Scan each row group without exporting source prompt contents."""
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise DataAuditError("pyarrow must be installed to inspect the public Parquet") from exc
    parquet = pq.ParquetFile(str(path))
    fields = {"prompt", "answer_nodes", "problem_type", "prompt_chars"}
    missing = fields - set(parquet.schema_arrow.names)
    if missing:
        raise DataAuditError("Public Parquet schema is missing: " + ", ".join(sorted(missing)))
    count = Counter()
    selected: list[dict[str, Any]] = []
    idx = 0
    for rg in range(parquet.num_row_groups):
        table = parquet.read_row_group(rg, columns=sorted(fields))
        for row in table.to_pylist():
            kind = row.get("problem_type")
            count[kind] += 1
            record = make_reference_record(idx, row)
            if record is not None:
                selected.append(record)
            idx += 1
        del table
    if idx != parquet.metadata.num_rows:
        raise DataAuditError("Parquet row count differs from processed rows")
    return selected, {
        "total_rows": idx,
        "counts_by_problem_type": dict(sorted(count.items())),
        "row_groups": parquet.num_row_groups,
        "source_schema_columns": parquet.schema_arrow.names,
        "bfs_prompt_chars_range": [
            min((x["prompt_chars_actual"] for x in selected), default=None),
            max((x["prompt_chars_actual"] for x in selected), default=None),
        ],
    }


def main() -> int:
    """Audit one public dataset revision; output minimal row references and receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--size-bytes", required=True, type=int)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--retain-parquet", action="store_true",
        help="Keep the SHA-256-verified public Parquet locally for token preflight; never upload it",
    )
    args = parser.parse_args()
    try:
        validate_source(args.revision, args.sha256, args.size_bytes)
    except DataAuditError as exc:
        parser.error(str(exc))
    if args.out.exists():
        parser.error("Refusing to overwrite a prior source audit")
    args.out.mkdir(parents=True, exist_ok=False)
    if args.retain_parquet:
        # The retained file contains original benchmark prompts and gold answers.
        # This option is intended only for private, ephemeral execution runners.
        source_file = args.out / FILENAME
        download_checked_parquet(source_file, revision=args.revision,
                                 sha256=args.sha256, expected_bytes=args.size_bytes)
        tasks, stats = audit_parquet(source_file)
    else:
        with tempfile.TemporaryDirectory(prefix="mcr-long-context-") as temp:
            source_file = Path(temp) / FILENAME
            download_checked_parquet(source_file, revision=args.revision,
                                     sha256=args.sha256, expected_bytes=args.size_bytes)
            tasks, stats = audit_parquet(source_file)
    index_bytes = b"".join(json.dumps(t, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8") + b"\n" for t in tasks)
    (args.out / "graphwalks-bfs-reference-index.jsonl").write_bytes(index_bytes)
    report = {
        "schema_version": "graphwalks-verified-source-v1",
        "evidence_level": "independently_verified_upstream_file_bytes_not_publisher_cohort",
        "dataset": DATASET,
        "license": "mit (upstream metadata)",
        "dataset_revision": args.revision,
        "parquet_filename": FILENAME,
        "parquet_sha256_verified": args.sha256,
        "parquet_size_bytes_verified": args.size_bytes,
        "bfs_task_count": len(tasks),
        "reference_index_sha256": hashlib.sha256(index_bytes).hexdigest(),
        "original_grader_url": f"https://huggingface.co/datasets/{DATASET}/blob/{args.revision}/README.md",
        "audit": stats,
        "limitations": [
            "Google's selected 200 task identities and dataset revision remain unverified.",
            "GraphWalks prompts are hashed but omitted; model input delivery was not tested.",
            "No model inference, tokenization, API cost or independent performance scoring took place.",
            "Upstream data license is recorded from metadata, not independently legally assessed.",
        ],
    }
    (args.out / "manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("Verified long-context source Parquet bytes:", args.sha256)
    print("Total tasks:", stats["total_rows"], "BFS tasks:", len(tasks),
          "(Google's 200-item cohort not established)")
    print("Reference index SHA-256:", report["reference_index_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
