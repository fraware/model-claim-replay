"""Record a redacted provider model-capability receipt for GraphWalks.

The pinned model metadata endpoint is queried once. Only a fixed allowlist of
scalar capability fields is retained; provider responses and credentials are
never copied into the public output. No generation or token counting occurs.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from model_claim_replay.graphwalks_runtime import (
    CONTEXT_LIMIT, FOREGROUND_OUTPUT_LIMIT, MODEL,
)
from provider_readiness import (
    ProviderProbeError, _GEMINI_HOST, _GEMINI_PATH, _metadata_get,
)

_Request = Callable[[str, str, Mapping[str, str]], tuple[int, Any]]


def read_model_capabilities(
    credential: str,
    *,
    request: _Request | None = None,
) -> dict[str, Any]:
    """Fetch metadata for the exact declared model with controlled diagnostics."""
    if not isinstance(credential, str) or not credential:
        raise ValueError("Gemini credential is absent")
    request = request or _metadata_get
    status: str = "unavailable"
    http_status: int | None = None
    input_limit: int | None = None
    output_limit: int | None = None
    try:
        http_status, body = request(
            _GEMINI_HOST, _GEMINI_PATH,
            {"x-goog-api-key": credential, "Accept": "application/json"},
        )
    except ProviderProbeError:
        status = "transport_or_response_error"
    else:
        if http_status != 200:
            status = "http_error"
        elif not isinstance(body, dict) or body.get("name") != "models/" + MODEL:
            status = "unexpected_model_metadata"
        else:
            status = "model_metadata_available"
            for field, variable in (("inputTokenLimit", "input"), ("outputTokenLimit", "output")):
                value = body.get(field)
                if type(value) is int and value > 0:
                    if variable == "input":
                        input_limit = value
                    else:
                        output_limit = value
    return {
        "schema_version": "graphwalks-provider-model-limits-v1",
        "evidence_level": "provider_metadata_self_reported_no_inference",
        "model": MODEL,
        "metadata_status": status,
        "http_status": http_status,
        "provider_input_token_limit": input_limit,
        "provider_output_token_limit": output_limit,
        "runner_conservative_context_limit": CONTEXT_LIMIT,
        "runner_foreground_output_limit": FOREGROUND_OUTPUT_LIMIT,
        "declared_input_limit_matches_provider": (
            input_limit == CONTEXT_LIMIT if input_limit is not None else None
        ),
        "declared_output_limit_within_provider": (
            FOREGROUND_OUTPUT_LIMIT <= output_limit if output_limit is not None else None
        ),
        "generation_performed": False,
        "limitations": (
            "Metadata is an unauthenticated public diagnostic of the API-key "
            "account's reported model; it does not establish billed capacity, "
            "a successful generative request or the publisher's protocol. "
            "InputTokenLimit is distinct from outputTokenLimit; the runner "
            "additionally reserves a conservative combined-token headroom."
        ),
    }


def main() -> int:
    """Save a no-overwrite allowlisted metadata receipt without key values."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        parser.error("Missing selected Gemini credential")
    result = read_model_capabilities(key)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        "Provider model metadata: " + result["metadata_status"]
        + "; input token limit "
        + str(result["provider_input_token_limit"])
        + "; output token limit "
        + str(result["provider_output_token_limit"])
    )
    print("No model generation, provider response body or secret material retained.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
