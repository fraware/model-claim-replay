"""Record GraphWalks dataset revision and metadata without downloading tasks.

This probe is a source-access preflight. It is neither a dataset-content audit
nor a model evaluation. Never infer that a publisher used this same revision.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DATASET = "openai/graphwalks"
API_URL = "https://huggingface.co/api/datasets/openai/graphwalks?blobs=true"
REQUIRED_FILES = (
    "graphwalks_256k_to_1mil.parquet",
    "graphwalks_128k_and_shorter.parquet",
)
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")


class PreflightError(ValueError):
    """The public dataset's metadata is missing or inconsistent."""


def extract_dataset_metadata(payload: Any) -> dict[str, Any]:
    """Validate a Hugging Face dataset response and retain source facts only."""
    if not isinstance(payload, dict):
        raise PreflightError("Dataset metadata must be a JSON object")
    sha = payload.get("sha")
    if not isinstance(sha, str) or not SHA40.fullmatch(sha):
        raise PreflightError("Dataset snapshot commit is missing or malformed")
    if payload.get("private") is True or payload.get("gated") not in (None, False):
        raise PreflightError("Dataset is private or access-gated")
    card = payload.get("cardData")
    if not isinstance(card, dict) or str(card.get("license", "")).lower() != "mit":
        raise PreflightError("Dataset does not declare the expected MIT license")
    siblings = payload.get("siblings")
    if not isinstance(siblings, list):
        raise PreflightError("Dataset file listing is missing")
    listed: dict[str, dict[str, Any]] = {}
    for item in siblings:
        if not isinstance(item, dict):
            raise PreflightError("Malformed dataset file record")
        name = item.get("rfilename")
        if isinstance(name, str) and name in REQUIRED_FILES:
            if name in listed:
                raise PreflightError("Duplicate benchmark file metadata")
            size = item.get("size")
            if size is not None and (type(size) is not int or size <= 0):
                raise PreflightError("Invalid benchmark file size")
            blob = item.get("lfs")
            content_sha = blob.get("sha256") if isinstance(blob, dict) else None
            if content_sha is not None and (
                not isinstance(content_sha, str) or not SHA64.fullmatch(content_sha)
            ):
                raise PreflightError("Invalid benchmark file LFS digest")
            listed[name] = {"name": name, "size_bytes": size, "lfs_sha256": content_sha}
    absent = sorted(set(REQUIRED_FILES) - set(listed))
    if absent:
        raise PreflightError("Public dataset listing lacks required files: " + ", ".join(absent))
    return {
        "schema_version": "graphwalks-metadata-v1",
        "evidence_level": "upstream_metadata_only_not_dataset_bytes_verified",
        "dataset": DATASET,
        "dataset_repository_commit": sha,
        "license": "mit",
        "api_source": API_URL,
        "files": [listed[name] for name in REQUIRED_FILES],
        "limitations": [
            "No benchmark rows or full file bytes were downloaded or hashed.",
            "The exact 200 BFS problems and source revision used by Google are not verified.",
            "No model API calls or independent performance evaluations were performed.",
        ],
    }


def fetch_dataset_metadata() -> dict[str, Any]:
    """Retrieve and validate bounded public metadata over HTTPS."""
    request = urllib.request.Request(
        API_URL, headers={"Accept": "application/json", "User-Agent": "model-claim-replay/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise PreflightError(f"Hugging Face metadata HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise PreflightError(f"Dataset metadata request failed ({type(exc).__name__})") from exc
    if len(body) > MAX_RESPONSE_BYTES:
        raise PreflightError("Dataset metadata response exceeded the size limit")
    try:
        payload = json.loads(body)
    except (UnicodeError, ValueError) as exc:
        raise PreflightError("Dataset metadata response is not valid JSON") from exc
    result = extract_dataset_metadata(payload)
    result["checked_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    return result


def main() -> int:
    """Write an immutable, reviewable source-metadata receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="New metadata receipt path")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Refusing to overwrite an existing receipt")
    try:
        receipt = fetch_dataset_metadata()
    except PreflightError as exc:
        parser.error(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Pinned upstream dataset metadata at revision", receipt["dataset_repository_commit"])
    print("Metadata only; no dataset rows or model outputs have been evaluated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
