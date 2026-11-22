"""Metadata-only provider readiness with a clearly labeled OpenAI fallback.

This probe makes at most one HTTPS GET to Gemini model metadata and one to
OpenAI's models endpoint. It never sends prompts, creates completions, invokes
Interactions/Responses, counts tokens, or accesses secret values beyond request
headers. It cannot establish permission or capacity for a billable evaluation.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from model_claim_replay.graphwalks_runtime import MODEL as GEMINI_CLAIM_MODEL

_GEMINI_HOST = "generativelanguage.googleapis.com"
_OPENAI_HOST = "api.openai.com"
_GEMINI_PATH = "/v1beta/models/" + GEMINI_CLAIM_MODEL
_OPENAI_PATH = "/v1/models"
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
    """Select usable metadata access: Gemini claim model, then OpenAI fallback.

    Model-list metadata access is a credential/API availability diagnostic only.
    An OpenAI result cannot reproduce a Google Gemini publisher claim.
    """
    if request is None:
        request = _metadata_get
    selected = None
    gemini: dict[str, Any] = {"status": "credential_missing"}
    openai: dict[str, Any] = {"status": "not_checked"}
    gemini_keys = _credentials(
        environ, "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY",
    )
    for key in gemini_keys:
        try:
            status, payload = request(
                _GEMINI_HOST, _GEMINI_PATH,
                {"x-goog-api-key": key, "Accept": "application/json"},
            )
        except ProviderProbeError:
            gemini = {"status": "transport_or_response_error"}
        else:
            if status == 200:
                if (
                    isinstance(payload, dict)
                    and payload.get("name") == "models/" + GEMINI_CLAIM_MODEL
                ):
                    gemini = {"status": "model_metadata_available", "http_status": 200}
                    selected = "gemini"
                    break
                gemini = {"status": "unexpected_model_metadata", "http_status": 200}
            else:
                gemini = {"status": "http_error", "http_status": status}

    if selected is None:
        openai_keys = _credentials(environ, "OPENAI_API_KEY", "OPENAI_KEY")
        openai = {"status": "credential_missing"} if not openai_keys else openai
        for key in openai_keys:
            try:
                status, payload = request(
                    _OPENAI_HOST, _OPENAI_PATH,
                    {"Authorization": "Bearer " + key, "Accept": "application/json"},
                )
            except ProviderProbeError:
                openai = {"status": "transport_or_response_error"}
            else:
                if status == 200:
                    models = payload.get("data") if isinstance(payload, dict) else None
                    if isinstance(models, list) and any(
                        isinstance(row, dict) and isinstance(row.get("id"), str)
                        and bool(row["id"])
                        for row in models
                    ):
                        openai = {"status": "model_catalog_available", "http_status": 200}
                        selected = "openai"
                        break
                    openai = {"status": "unexpected_model_catalog", "http_status": 200}
                else:
                    openai = {"status": "http_error", "http_status": status}
    return {
        "schema_version": "model-claim-replay-provider-readiness-v1",
        "mode": "metadata_only_no_generation",
        "preferred": "gemini",
        "fallback": "openai",
        "selected": selected,
        "gemini_claim_model": GEMINI_CLAIM_MODEL,
        "gemini": gemini,
        "openai": openai,
        "generative_request_performed": False,
        "benchmark_claim_reproduced": False,
        "limitations": (
            "HTTP model metadata/list access is not a generation test, quota "
            "validation, context-capacity test or provider execution receipt. "
            "OpenAI fallback is for operational readiness only; it does not "
            "reproduce or validate the published Gemini GraphWalks claim."
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
