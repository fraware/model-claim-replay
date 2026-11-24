"""One-task, source-pinned OpenAI Responses diagnostic.

No Gemini fallback. The exact public candidate prompt is submitted once,
after fresh token counting and an explicit USD reservation. A local intent
precedes generation; the private response and public score are separate.
This diagnostic is not a reproduction of any published Gemini score.
"""
from __future__ import annotations

import argparse
import datetime as dt
import http.client
import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

from .core import ReplayError, canonical_json, read_jsonl, sha256_bytes
from .graphwalks import grade_response
from .graphwalks_runtime import DATASET_REVISION, DATASET_SHA256, INDEX_SHA256, verified_prompts

MODEL = "gpt-6.2-sol"
TASK = "bfs-row-000100"
OUTPUT_LIMIT = 65_536
INPUT_LIMIT = 922_000
CONTEXT_LIMIT = 1_050_000
# Upper standard long-context rates, including the full-request surcharge
# above 272K input tokens. No cache discount assumed.
INPUT_RATE = Decimal("4")
OUTPUT_RATE = Decimal("15")
APPROVAL = "AUTHORIZE_PAID_OPENAI"
MAX_BUDGET = Decimal("100")
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
PRICE_SOURCE = "https://developers.openai.com/api/docs/models/gpt-6.2-sol"
Request = Callable[[str, dict[str, Any] | None, str], dict[str, Any]]


def authorization(approval: str, budget: str) -> Decimal:
    if approval != APPROVAL:
        raise ReplayError("Exact OpenAI paid authorization phrase is absent")
    try:
        value = Decimal(budget)
    except (InvalidOperation, ValueError, TypeError):
        raise ReplayError("Invalid USD ceiling") from None
    if not value.is_finite() or not 0 < value <= MAX_BUDGET:
        raise ReplayError("USD ceiling must be positive and at most $100")
    return value


def _request(path: str, payload: dict[str, Any] | None, key: str) -> dict[str, Any]:
    """Fixed HTTPS host, no redirects or retries; never surface error bodies."""
    if path not in ("/v1/models/" + MODEL, "/v1/responses/input_tokens", "/v1/responses"):
        raise ReplayError("Unapproved OpenAI endpoint")
    conn = http.client.HTTPSConnection("api.openai.com", timeout=900 if path == "/v1/responses" else 90)
    try:
        headers = {"Authorization": "Bearer " + key, "Accept": "application/json"}
        body = None if payload is None else canonical_json(payload)
        if body is not None:
            headers["Content-Type"] = "application/json"
        conn.request("GET" if body is None else "POST", path, body=body, headers=headers)
        response = conn.getresponse()
        if response.status != 200:
            raise ReplayError(f"OpenAI HTTP {response.status}")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ReplayError("OpenAI response exceeded byte bound")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ReplayError("Unexpected OpenAI response object")
        return value
    except (OSError, http.client.HTTPException, UnicodeError, json.JSONDecodeError):
        raise ReplayError("OpenAI transport or response decoding failed") from None
    finally:
        conn.close()


def _int(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ReplayError(f"Invalid {label}")
    return value


def reservation(input_tokens: int, output_tokens: int) -> Decimal:
    return (INPUT_RATE * _int(input_tokens, "input tokens")
            + OUTPUT_RATE * _int(output_tokens, "output tokens")) / Decimal(1_000_000)


def _write(path: Path, data: dict[str, Any]) -> None:
    # Exclusive durable journal: never overwrite or implicitly resume.
    with path.open("xb") as stream:
        stream.write(canonical_json(data) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def choose_key(environ: dict[str, str], request: Request) -> str:
    """Try alternate credentials for metadata only; never retry generation."""
    attempted = set()
    for name in ("OPENAI_API_KEY", "OPENAI_KEY"):
        key = environ.get(name)
        if not key or key in attempted:
            continue
        attempted.add(key)
        try:
            if request("/v1/models/" + MODEL, None, key).get("id") == MODEL:
                return key
        except ReplayError:
            continue
    raise ReplayError("No OpenAI credential authenticated the pinned model")


def diagnostic(
    parquet: Path, index: Path, out: Path, *, approval: str, budget: str,
    environ: dict[str, str], request: Request = _request,
    source_reader: Callable[..., dict[str, str]] = verified_prompts,
) -> dict[str, Any]:
    ceiling = authorization(approval, budget)
    if out.exists() or out.is_symlink():
        raise ReplayError("Output already exists; never resume a paid diagnostic")
    prompts = source_reader(parquet, index)
    references = {row["id"]: row for row in read_jsonl(index)}
    prompt = prompts[TASK]
    reference = references[TASK]
    digest = sha256_bytes(prompt.encode("utf-8"))
    if digest != reference["prompt_sha256"]:
        raise ReplayError("Prompt digest mismatch")
    key = choose_key(environ, request)
    count_payload = {"model": MODEL, "input": prompt, "reasoning": {"effort": "xhigh"}, "truncation": "disabled"}
    counted = request("/v1/responses/input_tokens", count_payload, key)
    if counted.get("object") != "response.input_tokens":
        raise ReplayError("Unexpected token count response")
    tokens = _int(counted.get("input_tokens"), "input token count")
    reserved = reservation(tokens, OUTPUT_LIMIT)
    if not tokens or tokens > INPUT_LIMIT or tokens + OUTPUT_LIMIT > CONTEXT_LIMIT:
        raise ReplayError("Original prompt exceeds the OpenAI input or context bound")
    if reserved > ceiling:
        raise ReplayError("OpenAI token reservation exceeds authorized ceiling")
    out.mkdir(parents=True, exist_ok=False)
    public = out / "public"
    private = out / "private"
    public.mkdir()
    private.mkdir(mode=0o700)
    plan = {
        "schema_version": "graphwalks-openai-single-task-v1",
        "model": MODEL, "task_id": TASK, "prompt_sha256": digest,
        "dataset_revision": DATASET_REVISION, "parquet_sha256": DATASET_SHA256,
        "reference_index_sha256": INDEX_SHA256, "input_tokens": tokens,
        "max_output_tokens": OUTPUT_LIMIT, "reasoning_effort": "xhigh",
        "input_limit": INPUT_LIMIT, "context_limit": CONTEXT_LIMIT,
        "input_usd_per_million_upper": str(INPUT_RATE), "output_usd_per_million_upper": str(OUTPUT_RATE),
        "reservation_usd": str(reserved), "authorized_ceiling_usd": str(ceiling),
        "price_source": PRICE_SOURCE, "pricing_checked_utc_date": "2026-11-24",
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "comparison_status": "not_comparable", "published_claim_reproduced": False,
    }
    _write(public / "plan.json", plan)
    _write(public / "intent.json", {"status": "generation_intent", "plan_sha256": sha256_bytes((public / "plan.json").read_bytes())})
    try:
        response = request("/v1/responses", {
            **count_payload, "max_output_tokens": OUTPUT_LIMIT,
            "store": False, "service_tier": "default", "tools": [],
        }, key)
        # Never upload raw response content or reasoning to a public artifact.
        _write(private / "response.json", response)
        usage = response.get("usage")
        if not isinstance(usage, dict):
            raise ReplayError("Missing provider token accounting")
        inp = _int(usage.get("input_tokens"), "actual input tokens")
        output = _int(usage.get("output_tokens"), "actual output tokens")
        total = _int(usage.get("total_tokens"), "actual total tokens")
        if total != inp + output or inp != tokens or output > OUTPUT_LIMIT or reservation(inp, output) > ceiling:
            raise ReplayError("Provider accounting differs from approved reservation")
        if response.get("status") != "completed" or response.get("model") != MODEL:
            raise ReplayError("Incomplete response or unexpected model identity")
        if response.get("service_tier") not in ("default", "auto"):
            raise ReplayError("Unexpected service tier")
        texts = []
        items = response.get("output")
        if not isinstance(items, list):
            raise ReplayError("Missing response output")
        for item in items:
            if not isinstance(item, dict):
                raise ReplayError("Invalid output item")
            if item.get("type") == "reasoning":
                continue
            if item.get("type") != "message" or item.get("role") != "assistant" or item.get("status") != "completed":
                raise ReplayError("Unexpected response output item")
            content = item.get("content")
            if not isinstance(content, list):
                raise ReplayError("Invalid response message")
            for part in content:
                if not isinstance(part, dict) or part.get("type") != "output_text" or not isinstance(part.get("text"), str):
                    raise ReplayError("Unexpected response content or refusal")
                texts.append(part["text"])
        if len(texts) != 1 or not texts[0]:
            raise ReplayError("Expected one complete answer text")
        score = grade_response(texts[0], reference["answer_nodes"])
        result = {
            "schema_version": "graphwalks-openai-single-task-result-v1",
            "status": "graded", "task_id": TASK, "model": MODEL,
            "plan_sha256": sha256_bytes((public / "plan.json").read_bytes()),
            "response_sha256": sha256_bytes((private / "response.json").read_bytes()),
            "answer_sha256": sha256_bytes(texts[0].encode("utf-8")),
            "input_tokens": inp, "output_tokens": output,
            "upper_usage_cost_usd": str(reservation(inp, output)),
            "grade": score, "comparison_status": "not_comparable",
            "published_claim_reproduced": False,
            "limitations": "Single source-bound candidate task; self-reported execution. Raw response not published; external rescoring pending.",
        }
    except (ReplayError, OSError, ValueError, TypeError, KeyError):
        _write(public / "outcome.json", {
            "status": "generation_or_accounting_uncertain", "task_id": TASK,
            "published_claim_reproduced": False, "retry_permitted": False,
        })
        raise ReplayError("Paid request or validation failed after durable intent; inspect privately, never rerun automatically") from None
    _write(public / "outcome.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--approval", required=True)
    parser.add_argument("--max-spend-usd", required=True)
    args = parser.parse_args()
    try:
        diagnostic(args.parquet, args.index, args.out, approval=args.approval,
                   budget=args.max_spend_usd, environ=dict(os.environ))
    except ReplayError as exc:
        parser.exit(2, f"OpenAI diagnostic: {exc}\n")
    print("Single-task OpenAI diagnostic graded; no publisher replication asserted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
