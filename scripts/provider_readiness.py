"""Metadata-only OpenAI readiness. No prompts or model generation."""

from __future__ import annotations

import argparse
import http.client
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from model_claim_replay.openai_graphwalks import MODEL as DEFAULT_MODEL

_OPENAI_HOST = "api.openai.com"
_OPENAI_PATH = "/v1/models/" + DEFAULT_MODEL
_MAX_METADATA_BYTES = 2 * 1024 * 1024
_TIMEOUT_SECONDS = 15
_ProviderRequest = Callable[[str, str, Mapping[str, str]], tuple[int, Any]]


class ProviderProbeError(Exception):
    """A transport or response-shape error that must not expose secrets."""


def _metadata_get(
    host: str, path: str, headers: Mapping[str, str],
) -> tuple[int, Any]:
    """Perform one bounded metadata GET over a fixed host with no redirects."""
    connection = http.client.HTTPSConnection(host, timeout=_TIMEOUT_SECONDS)
    try:
        connection.request("GET", path, headers=dict(headers))
        response = connection.getresponse()
        status = response.status
        # Do not parse error responses: they may echo identifying request
        # details or other sensitive upstream diagnostics.
        if status != 200:
            return status, None
        raw = response.read(_MAX_METADATA_BYTES + 1)
        if len(raw) > _MAX_METADATA_BYTES:
            raise ProviderProbeError("oversized metadata response")
        try:
            return status, json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise ProviderProbeError("invalid metadata response") from exc
    except (OSError, http.client.HTTPException) as exc:
        raise ProviderProbeError("provider metadata transport failed") from exc
    finally:
        connection.close()


def _credentials(environ: Mapping[str, str], *names: str) -> list[str]:
    """Collect distinct nonblank secret aliases without emitting their values."""
    values: list[str] = []
    for name in names:
        candidate = environ.get(name)
        if isinstance(candidate, str) and candidate.strip() and candidate not in values:
            values.append(candidate)
    return values


def probe_providers(
    environ: Mapping[str, str],
    *,
    request: _ProviderRequest | None = None,
) -> dict[str, Any]:
    """Check OpenAI only; never silently substitute a different provider."""
    if request is None:
        request = _metadata_get
    selected = None
    openai: dict[str, Any] = {"status": "credential_missing"}
    for key in _credentials(environ, "OPENAI_API_KEY", "OPENAI_KEY"):
        try:
            status, payload = request(
                _OPENAI_HOST, _OPENAI_PATH,
                {"Authorization": "Bearer " + key, "Accept": "application/json"},
            )
        except ProviderProbeError:
            openai = {"status": "transport_or_response_error"}
        else:
            if status != 200:
                openai = {"status": "http_error", "http_status": status}
                continue
            if isinstance(payload, dict) and payload.get("id") == DEFAULT_MODEL:
                openai = {"status": "model_metadata_available", "http_status": 200}
                selected = "openai"
                break
            openai = {"status": "unexpected_model_metadata", "http_status": 200}
    return {
        "schema_version": "model-claim-replay-provider-readiness-v2",
        "mode": "metadata_only_no_generation",
        "preferred": "openai",
        "fallback": None,
        "selected": selected,
        "default_model": DEFAULT_MODEL,
        "gemini": {"status": "not_checked"},
        "openai": openai,
        "generative_request_performed": False,
        "benchmark_claim_reproduced": False,
        "limitations": (
            "Exact model metadata access is not a generation test, quota "
            "validation, context-capacity test or execution receipt. "
            "No other provider is contacted."
        ),
    }


def main() -> int:
    """Write a key-free GitHub Actions artifact and report the selected provider."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    # Never overwrite a previous receipt, including an error receipt.
    if args.out.exists():
        parser.error("Refusing to overwrite an existing readiness receipt")
    report = probe_providers(os.environ)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        "Metadata-only provider readiness: "
        + (report["selected"] or "none")
        + "; Gemini " + report["gemini"]["status"]
        + "; OpenAI " + report["openai"]["status"]
    )
    print("No generation, no benchmark reproduction and no key contents reported.")
    return 0 if report["selected"] is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
