"""Single-hop Gemini Interactions generation with explicit request accounting.

Unlike an SDK-managed interaction, this adapter issues one direct HTTPS POST.
The Python standard library does not transparently retry failed requests or
follow HTTP redirects at the http.client level. A failed/uncertain call is
recorded by the caller's durable intent journal and must never be replayed.

The REST response parser accepts only a completed, single model-output step
and strictly validates source-model identity and token usage. It intentionally
ignores thought steps and never exports provider continuation tokens.
"""

from __future__ import annotations

import http.client
import json
from dataclasses import dataclass
from typing import Any, Callable

from .core import ReplayError

API_HOST = "generativelanguage.googleapis.com"
API_PATH = "/v1beta/interactions"
API_REVISION = "2026-05-20"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
# Google AI Studio's Gemini 4 Neon specification (2026-11-21):
# https://aistudio.google.com/docs/models/gemini-4-neon
# This is the provider's synchronous limit, not the default diagnostic budget.
MAX_ONE_HOP_OUTPUT = 65_536
DEFAULT_TIMEOUT_SECONDS = 900


class ProviderStatusError(ReplayError):
    """A provider HTTP error with only its status retained, never its body."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"Gemini provider HTTP {status_code}; body suppressed")


@dataclass(frozen=True)
class RestUsage:
    """Token counts returned by Gemini for this specific HTTP interaction."""

    total_input_tokens: int
    total_output_tokens: int
    total_thought_tokens: int | None = None
    total_cached_tokens: int | None = None
    total_tool_use_tokens: int | None = None


@dataclass(frozen=True)
class RestInteraction:
    """Only the fields necessary for local scoring and billing diagnostics."""

    status: str
    output_text: str | None
    usage: RestUsage | None


def _bounded_json(payload: bytes, expected_model: str) -> RestInteraction:
    """Parse one complete REST resource without exposing provider internals."""
    try:
        value = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReplayError("Gemini interaction returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise ReplayError("Gemini interaction must be a JSON object")
    if value.get("model") != expected_model:
        raise ReplayError("Gemini response model does not match the requested model")
    status = value.get("status")
    if not isinstance(status, str) or status not in {
        "completed", "requires_continuation", "incomplete", "failed",
        "requires_action", "in_progress", "cancelled", "queued",
    }:
        raise ReplayError("Unexpected Gemini response status")
    raw_usage = value.get("usage")
    usage: RestUsage | None = None
    if raw_usage is not None:
        if not isinstance(raw_usage, dict):
            raise ReplayError("Invalid Gemini usage metadata")
        fields = (
            "total_input_tokens", "total_output_tokens", "total_thought_tokens",
            "total_cached_tokens", "total_tool_use_tokens",
        )
        counts: dict[str, int | None] = {}
        for field in fields:
            n = raw_usage.get(field)
            if n is not None and (type(n) is not int or n < 0):
                raise ReplayError(f"Invalid Gemini {field} token count")
            counts[field] = n
        if counts["total_input_tokens"] is not None and counts["total_output_tokens"] is not None:
            usage = RestUsage(**counts)  # type: ignore[arg-type]
    if status != "completed":
        # No partial text is admitted for scoring. In particular, the server
        # may have incurred charges before returning requires_continuation.
        return RestInteraction(status=status, output_text=None, usage=usage)
    if usage is None:
        raise ReplayError("Completed Gemini interaction lacks token accounting")
    steps = value.get("steps")
    if not isinstance(steps, list):
        raise ReplayError("Completed Gemini interaction has no step sequence")
    outputs = [step for step in steps
               if isinstance(step, dict) and step.get("type") == "model_output"]
    if len(outputs) != 1:
        raise ReplayError("Expected exactly one Gemini model-output step")
    chunks = outputs[0].get("content")
    if not isinstance(chunks, list) or not chunks:
        raise ReplayError("Gemini model-output step has no text content")
    text_parts = []
    for chunk in chunks:
        if not isinstance(chunk, dict) or chunk.get("type") != "text" or not isinstance(chunk.get("text"), str):
            raise ReplayError("Gemini model output includes unsupported non-text content")
        text_parts.append(chunk["text"])
    return RestInteraction(status=status, output_text="".join(text_parts), usage=usage)


def single_interaction(
    prompt: str, *, api_key: str, model: str, max_output_tokens: int,
    thinking_level: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    _connect: Callable[..., Any] | None = None,
) -> RestInteraction:
    """Send one HTTPS POST to Google's official, fixed REST endpoint.

    `_connect` is test-only dependency injection for a local HTTP server.
    Production calls use verified TLS via http.client.HTTPSConnection.
    There is deliberately no redirect-following, polling or retry path.
    """
    if not isinstance(prompt, str) or not prompt:
        raise ReplayError("Gemini prompt must be nonempty text")
    if not isinstance(api_key, str) or not api_key or any(c in api_key for c in "\r\n"):
        raise ReplayError("A valid Gemini API key is required")
    if model != "gemini-4-neon":
        raise ReplayError("Only the pinned Gemini 4 Neon model is supported")
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= MAX_ONE_HOP_OUTPUT:
        raise ReplayError("Output allowance exceeds the one-hop nonstreaming ceiling")
    if thinking_level not in ("low", "medium", "high", "xhigh"):
        raise ReplayError("Unsupported Gemini thinking level")
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 3600:
        raise ReplayError("Invalid Gemini per-request timeout")
    body = json.dumps({
        "model": model,
        "input": prompt,
        "generation_config": {
            "thinking_level": thinking_level,
            "max_output_tokens": max_output_tokens,
        },
        "background": False,
        "stream": False,
        "store": False,
        "service_tier": "standard",
    }, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Api-Revision": API_REVISION,
    }
    factory = _connect or http.client.HTTPSConnection
    connection = factory(API_HOST, timeout=timeout_seconds)
    try:
        try:
            connection.request("POST", API_PATH, body=body, headers=headers)
            response = connection.getresponse()
            status_code = int(response.status)
            if status_code != 200:
                # 3xx is an error, not an invitation to make a second request.
                raise ProviderStatusError(status_code)
            length = response.getheader("Content-Length")
            if length is not None:
                try:
                    if int(length) > MAX_RESPONSE_BYTES:
                        raise ReplayError("Gemini response exceeds size limit")
                except ValueError as exc:
                    raise ReplayError("Invalid Gemini Content-Length") from exc
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ReplayError("Gemini response exceeds size limit")
        except (OSError, TimeoutError, http.client.HTTPException) as exc:
            # Do not reveal the request or API key through exception details.
            raise ReplayError(f"Gemini transport failed ({type(exc).__name__})") from None
    finally:
        connection.close()
    return _bounded_json(raw, model)
