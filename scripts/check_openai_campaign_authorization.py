"""Validate initial introduction of the fixed campaign authorization.

The record is consumed by its first main push, even if no request occurs.
Reject historical reuse, reruns, and any change to the approved inputs.
"""
from __future__ import annotations
import hashlib
import os
import re
import subprocess
from pathlib import Path

AUTH_PATH = "evidence/graphwalks/openai-campaign-authorization-2026-11-24.json"
EXPECTED = "{\n  \"schema_version\": \"graphwalks-campaign-authorization-v1\",\n  \"experiment_id\": \"openai-campaign-v1-2026-11-24\",\n  \"protocol_issue\": 42,\n  \"approval\": \"AUTHORIZE_OPENAI_CAMPAIGN\",\n  \"model\": \"gpt-6.2-sol\",\n  \"manifest_sha256\": \"b5bedeaf9ba25f0f6321bd7fbe6995db7bdd706c881f3168ef03b10ee3d22efc\",\n  \"preflight_archive_sha256\": \"622dc133c231e7f14562037f4d2094916054aae991b43fd83ab31dcbf27ac853\",\n  \"max_spend_usd\": \"25\",\n  \"max_generation_requests\": 8,\n  \"selected_tasks\": 16,\n  \"publication\": \"PUBLISH_FINAL_LINE\",\n  \"reasoning_effort\": \"xhigh\",\n  \"max_output_tokens\": 65536,\n  \"scope\": \"One frozen campaign; exact preflight comparison; no retries, replacement tasks, or publisher replication.\"\n}\n".encode("utf-8")
MANIFEST = "evidence/graphwalks/openai-campaign-v1.json"
ARCHIVE = "evidence/graphwalks/openai-campaign-preflight-2026-11-24.zip"
INPUTS = {
    MANIFEST: "b5bedeaf9ba25f0f6321bd7fbe6995db7bdd706c881f3168ef03b10ee3d22efc",
    ARCHIVE: "622dc133c231e7f14562037f4d2094916054aae991b43fd83ab31dcbf27ac853",
}


def check(root: Path, before: str, head: str, event: str, ref: str, attempt: str) -> None:
    if (event, ref, attempt) != ("push", "refs/heads/main", "1"):
        raise ValueError("Only the initial main push is authorized")
    if any(not re.fullmatch(r"[0-9a-f]{40}", sha) or sha == "0" * 40 for sha in (before, head)):
        raise ValueError("Invalid push commit bounds")

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                              text=True, timeout=60).stdout.strip()

    if git("rev-parse", "HEAD") != head or before == head:
        raise ValueError("Checkout does not match the authorized push")
    git("merge-base", "--is-ancestor", before, head)
    if git("log", "--full-history", "--format=%H", before, "--", AUTH_PATH):
        raise ValueError("Authorization already exists in prior history")
    if git("diff", "--diff-filter=A", "--name-only", before, head, "--", AUTH_PATH) != AUTH_PATH:
        raise ValueError("Authorization must be newly introduced")
    path = root / AUTH_PATH
    if path.is_symlink() or path.read_bytes() != EXPECTED:
        raise ValueError("Authorization differs from the fixed campaign")
    for rel, digest in INPUTS.items():
        path = root / rel
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Authorized input digest mismatch: " + rel)


if __name__ == "__main__":
    try:
        check(Path.cwd(), os.environ.get("BEFORE_SHA", ""), os.environ.get("GITHUB_SHA", ""),
              os.environ.get("GITHUB_EVENT_NAME", ""), os.environ.get("GITHUB_REF", ""),
              os.environ.get("GITHUB_RUN_ATTEMPT", ""))
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        raise SystemExit("Campaign authorization refused: " + str(exc)) from None
    print("One-time campaign authorized: 16 selected, at most 8 requests, USD 25 reservation.")
