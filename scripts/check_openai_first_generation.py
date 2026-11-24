"""Require the first introduction of the fixed experimental authorization on main.

Prior history of the path, including deleted copies, rejects a new attempt.
This gate is not a reusable paid-on-push mechanism.
"""
from __future__ import annotations
import os
import re
import subprocess
from pathlib import Path

AUTH_PATH = "evidence/graphwalks/openai-first-generation-authorization.json"
EXPECTED = "{\n  \"schema_version\": \"graphwalks-first-generation-authorization-v1\",\n  \"experiment_id\": \"openai-first-generation-2026-11-24\",\n  \"approval\": \"AUTHORIZE_PAID_OPENAI\",\n  \"model\": \"gpt-6.2-sol\",\n  \"task_id\": \"bfs-row-000100\",\n  \"max_spend_usd\": \"5\",\n  \"max_generation_requests\": 1,\n  \"publication\": \"PUBLISH_FINAL_LINE\",\n  \"dataset_revision\": \"be6cc6ecf9b4d495b07d1ff53d2a16598e90fed7\",\n  \"prompt_sha256\": \"8dff8adf1268f8298451e4e5c17d5f911c2cf1e5e3dab1a17cbe5ed9348956e6\",\n  \"reasoning_effort\": \"xhigh\",\n  \"max_output_tokens\": 65536,\n  \"scope\": \"Single public benchmark diagnostic; no automatic retries, additional tasks or claim replication.\"\n}\n".encode("utf-8")


def check(root: Path, before: str, head: str, event: str, ref: str, attempt: str) -> None:
    if (event, ref, attempt) != ("push", "refs/heads/main", "1"):
        raise ValueError("Only the initial main push is authorized")
    if any(not re.fullmatch(r"[0-9a-f]{40}", sha) or sha == "0" * 40 for sha in (before, head)):
        raise ValueError("Missing valid push commit bounds")

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                              text=True, timeout=60).stdout.strip()

    if git("rev-parse", "HEAD") != head or before == head:
        raise ValueError("Checkout does not match the authorized push")
    git("merge-base", "--is-ancestor", before, head)
    if git("log", "--full-history", "--format=%H", before, "--", AUTH_PATH):
        raise ValueError("Authorization path already exists in prior history")
    if git("diff", "--diff-filter=A", "--name-only", before, head, "--", AUTH_PATH) != AUTH_PATH:
        raise ValueError("Authorization must be newly introduced in this push")
    path = root / AUTH_PATH
    if path.is_symlink() or path.read_bytes() != EXPECTED:
        raise ValueError("Authorization record differs from the fixed experiment")


if __name__ == "__main__":
    try:
        check(Path.cwd(), os.environ.get("BEFORE_SHA", ""), os.environ.get("GITHUB_SHA", ""),
              os.environ.get("GITHUB_EVENT_NAME", ""), os.environ.get("GITHUB_REF", ""),
              os.environ.get("GITHUB_RUN_ATTEMPT", ""))
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        raise SystemExit("First-generation authorization refused: " + str(exc)) from None
    print("Initial authorization validated: one diagnostic, USD 5 reservation ceiling.")
