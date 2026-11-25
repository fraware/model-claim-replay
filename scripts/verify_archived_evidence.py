"""Verify both historical OpenAI experiments entirely offline.

Run from the repository checkout after installing the base package. All
archives are byte-identical public artifacts, not reconstructed receipts.
Only the disclosed answers are rescored; provider origin, full-answer
extraction, invoice accuracy and external review remain unverified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

from model_claim_replay.core import ReplayError
from model_claim_replay.openai_graphwalks_verify import verify
from verify_openai_campaign import verify_journal

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "graphwalks"
INDEX_NAME = "graphwalks-bfs-reference-index.jsonl"
INDEX_SHA256 = "250d80874ad9bc8edf278cf3bf7aa145da3f2b34967c5504b8fa8703358480ee"


def extract_verified(archive: Path, digest: str, names: set[str], dest: Path) -> None:
    """Extract only exact allowlisted members from a known original archive."""
    if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
        raise ReplayError(f"Archive digest mismatch: {archive.name}")
    with zipfile.ZipFile(archive) as z:
        actual = z.namelist()
        if len(actual) != len(names) or set(actual) != names:
            raise ReplayError(f"Unexpected archive members: {archive.name}")
        dest.mkdir()
        for name in sorted(names):
            (dest / name).write_bytes(z.read(name))


def verify_archived_evidence() -> dict:
    """Return separately scoped verifier reports, with no network dependency."""
    with tempfile.TemporaryDirectory(prefix="claim-replay-evidence-") as tmp:
        root = Path(tmp)
        extract_verified(
            EVIDENCE / "verified-bfs-reference-index.zip",
            "cf2d078035f3a4fe5a93aeaf8cf06f1c170751bc3e4fc2f2cd68a66a380bb9fe",
            {INDEX_NAME, "manifest.json"}, root / "source",
        )
        index = root / "source" / INDEX_NAME
        if hashlib.sha256(index.read_bytes()).hexdigest() != INDEX_SHA256:
            raise ReplayError("Reference index digest mismatch")
        extract_verified(
            EVIDENCE / "openai-first-generation-2026-11-24" / "original-actions-artifact.zip",
            "dd7834d6f3162ab2683d5cf39a382393dea1afcd0725ab03102ea252c7b24a07",
            {"plan.json", "intent.json", "outcome.json", "scoring-evidence.json", "verification.json"},
            root / "pilot",
        )
        campaign_names = {"plan.json", "summary.json"}
        campaign_names.update(f"task-{i:02d}-outcome.json" for i in range(1, 17))
        campaign_names.update(f"task-{i:02d}-intent.json" for i in range(1, 9))
        extract_verified(
            EVIDENCE / "openai-campaign-paid-evidence-2026-11-24.zip",
            "f6a2dc1af63a5f50be087f1db45de0145a7880ac527852ebf0be0d9ef8a3d113",
            campaign_names, root / "campaign",
        )
        return {
            "schema_version": "archived-openai-evidence-verification-v1",
            "pilot": verify(root / "pilot", index),
            "campaign": verify_journal(root / "campaign", index),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        report = verify_archived_evidence()
    except (ReplayError, OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        parser.exit(2, f"Archived evidence verification failed: {exc}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
