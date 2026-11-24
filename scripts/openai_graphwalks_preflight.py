"""Run the OpenAI source-bound preflight with an independent endpoint guard.

The automatic workflow has no paid mode, budget override or generation
endpoint. The fixed $5 ceiling is solely a hypothetical reservation limit.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Callable

from model_claim_replay.core import ReplayError
from model_claim_replay.openai_graphwalks import MODEL, PREFLIGHT, _request, diagnostic


def count_only_request(
    path: str, payload: dict[str, Any] | None, key: str,
    *, transport: Callable = _request,
) -> dict[str, Any]:
    """Reject any call outside the metadata and input-token endpoints."""
    if path == "/v1/models/" + MODEL and payload is None:
        return transport(path, payload, key)
    if path == "/v1/responses/input_tokens" and isinstance(payload, dict):
        return transport(path, payload, key)
    raise ReplayError("Automatic preflight prohibits all generation endpoints")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = diagnostic(
            args.parquet, args.index, args.out,
            approval=PREFLIGHT, budget="5", environ=dict(os.environ),
            request=count_only_request,
        )
    except ReplayError as exc:
        parser.exit(2, f"OpenAI live preflight: {exc}\n")
    if result.get("generation_performed") is not False or result.get("status") not in (
        "preflight_ready", "preflight_blocked",
    ):
        parser.exit(2, "Unexpected result for token-count-only workflow\n")
    print(f"OpenAI {result['status']}: {result['input_tokens']} input tokens; "
          f"maximum estimated generation reservation USD {result['reservation_usd']}. "
          "No generation or paid authorization.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
