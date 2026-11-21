"""Budget-gated GraphWalks BFS execution using pinned source bytes and Gemini.

The workflow is split into a non-generative token-count preflight and an
explicit paid run. A checkpoint intent is written *before* every billable
request. An interrupted request is never implicitly retried. This is a
candidate-dataset diagnostic, not reproduction of a publisher's claimed score.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import stat
import tempfile
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterator

from .core import ReplayError, canonical_json, read_bytes, read_json, read_jsonl, sha256_bytes
from .gemini_rest import MAX_ONE_HOP_OUTPUT, ProviderStatusError

DATASET_SHA256 = "537879431c72a42e3b500f80efc3047e7facb90390b6063d33679b4320985911"
INDEX_SHA256 = "250d80874ad9bc8edf278cf3bf7aa145da3f2b34967c5504b8fa8703358480ee"
DATASET_REVISION = "be6cc6ecf9b4d495b07d1ff53d2a16598e90fed7"
MODEL = "gemini-4-neon"
CONTEXT_LIMIT = 1_048_576
FOREGROUND_OUTPUT_LIMIT = MAX_ONE_HOP_OUTPUT
INPUT_USD_PER_M = Decimal("3.00")
OUTPUT_USD_PER_M = Decimal("15.00")
PRICE_SOURCE = "https://aistudio.google.com/docs/pricing"
SCHEMA = "graphwalks-gemini-plan-v2"
SELECTION_POLICY = "balanced_public_context_bands_v1"


def sha256_file(path: Path) -> str:
    """Compute the digest in bounded memory, refusing non-files."""
    if not path.is_file():
        raise ReplayError("The pinned GraphWalks Parquet file does not exist")
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _ensure_hash(path: Path, expected: str, *, label: str) -> None:
    if sha256_file(path) != expected:
        raise ReplayError(f"{label} SHA-256 does not match the pinned source")


def _parquet_rows(path: Path) -> Iterator[dict[str, Any]]:
    """Read a bounded batch at a time; use the original Parquet row ordering."""
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ReplayError("GraphWalks execution needs pyarrow: pip install 'model-claim-replay[graphwalks]'") from exc
    parquet = pq.ParquetFile(str(path))
    required = {"prompt", "answer_nodes", "problem_type"}
    if not required.issubset(parquet.schema_arrow.names):
        raise ReplayError("Source Parquet is missing required GraphWalks fields")
    for batch in parquet.iter_batches(batch_size=8, columns=sorted(required)):
        yield from batch.to_pylist()


def verified_prompts(
    parquet_path: Path, index_path: Path,
    *, expected_parquet_sha256: str = DATASET_SHA256,
    expected_index_sha256: str = INDEX_SHA256,
    source_rows: Callable[[Path], Iterator[dict[str, Any]]] = _parquet_rows,
) -> dict[str, str]:
    """Verify all indexed source prompts and references before any API activity.

    The production CLI uses two pinned digests; tests inject fixture digests
    without weakening the public benchmark's defaults.
    """
    _ensure_hash(parquet_path, expected_parquet_sha256, label="Parquet")
    _ensure_hash(index_path, expected_index_sha256, label="BFS index")
    index = read_jsonl(index_path)
    if len({x["id"] for x in index}) != len(index):
        raise ReplayError("Duplicate BFS index IDs")
    lookup: dict[int, dict[str, Any]] = {}
    for item in index:
        source_index = item.get("source_row_index")
        if type(source_index) is not int or source_index < 0 or source_index in lookup:
            raise ReplayError("Invalid or duplicate Parquet row reference")
        if item.get("id") != f"bfs-row-{source_index:06d}" or item.get("problem_type") != "bfs":
            raise ReplayError("Source index must contain matching BFS IDs")
        if not isinstance(item.get("prompt_sha256"), str):
            raise ReplayError("Source index lacks a prompt digest")
        lookup[source_index] = item
    prompts: dict[str, str] = {}
    counted = 0
    for position, record in enumerate(source_rows(parquet_path)):
        counted += 1
        item = lookup.get(position)
        if item is None:
            continue
        prompt = record.get("prompt")
        if (record.get("problem_type") != "bfs" or not isinstance(prompt, str)
                or sha256_bytes(prompt.encode("utf-8")) != item["prompt_sha256"]
                or record.get("answer_nodes") != item.get("answer_nodes")):
            raise ReplayError(f"Parquet and reference index disagree at row {position}")
        if len(prompt) != item.get("prompt_chars_actual"):
            raise ReplayError("Actual prompt length does not match the pinned reference")
        prompts[item["id"]] = prompt
    if len(prompts) != len(index) or any(i >= counted for i in lookup):
        raise ReplayError("Missing or unexpected source rows in GraphWalks Parquet")
    return prompts


def _usd(input_tokens: int, output_tokens: int) -> Decimal:
    return ((Decimal(input_tokens) * INPUT_USD_PER_M +
             Decimal(output_tokens) * OUTPUT_USD_PER_M) / Decimal(1_000_000))


def _tokens(value: Any, *, description: str) -> int:
    if type(value) is not int or value < 0:
        raise ReplayError(f"Invalid provider {description} token count")
    return value


def _balanced_public_cohort(index: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    """Prespecify context-balanced tasks before model scores exist.

    The independently verified 200-row BFS index contains 100 shorter
    (~256K-token) problems followed by 100 longer (~1M-token) problems.
    Within each band, evenly spaced rows are sampled deterministically.
    Exact source bytes remain pinned by the caller's SHA-256 checks.
    """
    if len(index) != 200 or type(count) is not int or not 1 <= count <= 200:
        raise ReplayError("Balanced GraphWalks selection needs 1-200 pinned BFS tasks")
    n_short, n_long = (count + 1) // 2, count // 2
    short, long = index[:100], index[100:]
    def spread(band: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
        return [band[(i * len(band)) // n] for i in range(n)] if n else []
    return spread(short, n_short) + spread(long, n_long)


def build_token_plan(
    index_path: Path, prompts: dict[str, str],
    *, count_tokens: Callable[[str], int], max_tasks: int,
    max_output_tokens: int = 16384, thinking_level: str = "xhigh",
    model: str = MODEL, dataset_revision: str = DATASET_REVISION,
    expected_index_sha256: str = INDEX_SHA256,
    expected_parquet_sha256: str = DATASET_SHA256,
) -> dict[str, Any]:
    """Record *actual* model token counts without generating a completion."""
    if model != MODEL or thinking_level not in ("low", "medium", "high", "xhigh"):
        raise ReplayError("This adapter supports Gemini 4 Neon and documented thinking levels only")
    if (type(max_tasks) is not int or max_tasks < 1 or
            type(max_output_tokens) is not int or not 1 <= max_output_tokens <= FOREGROUND_OUTPUT_LIMIT):
        raise ReplayError("Invalid positive task count or foreground output limit")
    _ensure_hash(index_path, expected_index_sha256, label="BFS index")
    index = read_jsonl(index_path)
    if len(prompts) != len(index):
        raise ReplayError("The complete source cohort must pass source-data verification before counting")
    if max_tasks > len(index):
        raise ReplayError("Requested task count exceeds the verified reference cohort")
    selected = _balanced_public_cohort(index, max_tasks)
    rows: list[dict[str, Any]] = []
    for item in selected:
        ident = item["id"]
        prompt = prompts.get(ident)
        if not isinstance(prompt, str) or sha256_bytes(prompt.encode("utf-8")) != item.get("prompt_sha256"):
            raise ReplayError("Task prompt is not bound to the verified BFS index")
        input_tokens = _tokens(count_tokens(prompt), description="input")
        if input_tokens == 0:
            raise ReplayError("Provider returned zero input tokens for a nonempty prompt")
        fits = input_tokens + max_output_tokens <= CONTEXT_LIMIT
        rows.append({
            "id": ident, "prompt_sha256": item["prompt_sha256"],
            "input_tokens": input_tokens, "fits_context_with_output_allowance": fits,
            "maximum_reserved_cost_usd": str(_usd(input_tokens, max_output_tokens)),
        })
    return {
        "schema_version": SCHEMA,
        "evidence_level": "candidate_public_dataset_api_token_preflight_not_a_model_evaluation",
        "model": model, "thinking_level": thinking_level,
        "max_output_tokens": max_output_tokens,
        "dataset_revision": dataset_revision,
        "parquet_sha256": expected_parquet_sha256,
        "index_sha256": expected_index_sha256,
        "reference_task_count": len(index),
        "selection_policy": SELECTION_POLICY,
        "selection_counts": {
            "short_context": (len(rows) + 1) // 2,
            "long_context": len(rows) // 2,
        },
        "planned_tasks": rows,
        "planned_count": len(rows),
        "context_limit": CONTEXT_LIMIT,
        "pricing": {"input_usd_per_m": str(INPUT_USD_PER_M),
                    "output_usd_per_m": str(OUTPUT_USD_PER_M),
                    "as_of": "2026-11-20", "source": PRICE_SOURCE,
                    "tier": "standard", "currency": "USD"},
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "maximum_reserved_cost_usd": str(sum(
            (Decimal(x["maximum_reserved_cost_usd"]) for x in rows), Decimal(0))),
        "blocked_for_context": sum(not row["fits_context_with_output_allowance"] for row in rows),
        "comparison_status": "not_comparable",
        "limitations": [
            "Token counts originate from the specified provider endpoint and are self-reported.",
            "The publisher's exact dataset revision and run settings are unverified.",
            "The reservation is an estimate under a dated price table, not a provider billing guarantee.",
            "No generation was performed; max_output_tokens caps both reasoning and answer output.",
        ],
    }


def save_plan(plan: dict[str, Any], path: Path) -> None:
    """Create a new plan without overwriting evidence from earlier runs."""
    if path.exists():
        raise ReplayError("Plan path already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical_json(plan) + b"\n")


def _load_plan(plan_path: Path, index_path: Path, *, require_fresh: bool = True) -> dict[str, Any]:
    plan = read_json(plan_path)
    if not isinstance(plan, dict) or plan.get("schema_version") != SCHEMA:
        raise ReplayError("Not a supported GraphWalks Gemini token plan")
    if (plan.get("model") != MODEL or plan.get("index_sha256") != INDEX_SHA256 or
            plan.get("parquet_sha256") != DATASET_SHA256 or
            plan.get("dataset_revision") != DATASET_REVISION):
        raise ReplayError("The token plan is not bound to the pinned public GraphWalks source")
    _ensure_hash(index_path, INDEX_SHA256, label="BFS index")
    if plan.get("thinking_level") not in ("low", "medium", "high", "xhigh"):
        raise ReplayError("Unknown or absent model thinking configuration")
    # Token counts and provider pricing are time-sensitive. Refuse stale
    # approvals instead of silently reusing a potentially obsolete quote.
    created_utc = plan.get("created_utc")
    if not isinstance(created_utc, str):
        raise ReplayError("Token plan lacks a creation timestamp")
    try:
        created = dt.datetime.fromisoformat(created_utc)
    except ValueError as exc:
        raise ReplayError("Token plan creation timestamp is invalid") from exc
    if created.tzinfo is None or created.utcoffset() is None:
        raise ReplayError("Token plan creation timestamp must be timezone-aware")
    now = dt.datetime.now(dt.timezone.utc)
    if require_fresh and (created > now + dt.timedelta(minutes=5)
                          or now - created > dt.timedelta(hours=24)):
        raise ReplayError("Token plan is stale or future-dated; count tokens again")
    if plan.get("pricing") != {
        "input_usd_per_m": str(INPUT_USD_PER_M),
        "output_usd_per_m": str(OUTPUT_USD_PER_M),
        "as_of": "2026-11-20", "source": PRICE_SOURCE,
        "tier": "standard", "currency": "USD",
    }:
        raise ReplayError("Plan pricing differs from the published reference rate")
    output_limit = plan.get("max_output_tokens")
    if type(output_limit) is not int or not 1 <= output_limit <= FOREGROUND_OUTPUT_LIMIT:
        raise ReplayError("Invalid configured output ceiling")
    tasks = plan.get("planned_tasks")
    if not isinstance(tasks, list) or not tasks or len(tasks) > 200:
        raise ReplayError("No valid planned task cohort")
    index = read_jsonl(index_path)
    if len(index) != 200:
        raise ReplayError("A real-source run must bind the complete 200-task reference index")
    if plan.get("reference_task_count") != 200:
        raise ReplayError("Incorrect reference cohort size")
    if plan.get("planned_count") != len(tasks) or plan.get("context_limit") != CONTEXT_LIMIT:
        raise ReplayError("GraphWalks plan summary does not match the actual task cohort")
    if (plan.get("selection_policy") != SELECTION_POLICY
            or plan.get("selection_counts") != {
                "short_context": (len(tasks) + 1) // 2,
                "long_context": len(tasks) // 2,
            }):
        raise ReplayError("GraphWalks plan does not use the approved balanced selection")
    selected = _balanced_public_cohort(index, len(tasks))
    if plan.get("comparison_status") != "not_comparable":
        raise ReplayError("GraphWalks plan must not claim publisher comparability")
    for task, reference in zip(tasks, selected):
        if not isinstance(task, dict) or (task.get("id") != reference["id"] or
                task.get("prompt_sha256") != reference["prompt_sha256"]):
            raise ReplayError("Unexpected, reordered or altered balanced-plan task IDs")
        input_tokens = _tokens(task.get("input_tokens"), description="planned input")
        if input_tokens == 0:
            raise ReplayError("Plan contains a zero-token nonempty source prompt")
        if task.get("fits_context_with_output_allowance") is not (input_tokens + output_limit <= CONTEXT_LIMIT):
            raise ReplayError("Contradictory context feasibility flag")
        if task.get("maximum_reserved_cost_usd") != str(_usd(input_tokens, output_limit)):
            raise ReplayError("Contradictory per-task cost reservation")
    expected_total = sum(
        (Decimal(task["maximum_reserved_cost_usd"]) for task in tasks), Decimal(0)
    )
    expected_blocked = sum(not task["fits_context_with_output_allowance"] for task in tasks)
    if (plan.get("maximum_reserved_cost_usd") != str(expected_total)
            or plan.get("blocked_for_context") != expected_blocked):
        raise ReplayError("GraphWalks plan total cost or context blockers are inconsistent")
    return plan


def _write_exclusive(path: Path, obj: dict[str, Any]) -> None:
    """Atomically publish a durable journal entry without replacing prior data.

    A direct exclusive write exposes a truncated final file if the process
    stops during serialization or disk I/O. Persist the complete bytes to a
    same-filesystem temporary file, then create the destination using an
    exclusive hard link. Stage attempt files outside the audited attempts
    directory to avoid spurious corrupted entries after process termination.

    A failure following publication keeps the intent in place, conservatively
    preventing any automatic retry of a possibly billable request.
    """
    stage_dir = path.parent.parent if path.parent.name == "attempts" else path.parent
    fd, stage_name = tempfile.mkstemp(prefix=".graphwalks-journal-", dir=stage_dir)
    staged = Path(stage_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical_json(obj) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())

        # Atomic, exclusive publication. Concurrent or resumed attempts never
        # replace a previously recorded intent or provider result.
        os.link(staged, path)
        if os.name == "posix":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        staged.unlink(missing_ok=True)


@contextmanager
def _exclusive_paid_run(out: Path) -> Iterator[None]:
    """Fail closed if another runner owns this output directory.

    A persistent, per-run advisory lock is acquired nonblocking *before*
    inspecting a resumed journal. POSIX releases the lock on a process crash,
    unlike an exclusive-create sentinel that would permanently block recovery.
    Resolve parent-directory aliases to the same lock. Windows paid execution
    is refused until equivalent cross-process locking is implemented.
    """
    try:
        import fcntl
    except ImportError as exc:
        raise ReplayError(
            "GraphWalks paid execution needs POSIX advisory locking"
        ) from exc
    if out.is_symlink():
        raise ReplayError("GraphWalks paid run directory must not be a symlink")
    target = out.resolve(strict=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.parent / f".{target.name}.graphwalks-execution.lock"
    flags = os.O_RDWR | os.O_CREAT | os.O_NONBLOCK
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    fd = os.open(lock_path, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ReplayError("GraphWalks paid execution lock must be a regular file")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ReplayError(
                "Another GraphWalks execution is already active for this output directory"
            ) from None
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _run_status(response: Any) -> tuple[str, str | None, dict[str, int | None]]:
    status = getattr(response, "status", None)
    output = getattr(response, "output_text", None)
    usage = getattr(response, "usage", None)
    keys = ("total_input_tokens", "total_output_tokens", "total_thought_tokens",
            "total_cached_tokens", "total_tool_use_tokens")
    usage_values = {key: getattr(usage, key, None) for key in keys}
    for key, value in usage_values.items():
        if value is not None:
            _tokens(value, description=key)
    if getattr(status, "value", status) == "completed" and isinstance(output, str):
        # A completed task without provider input/output token accounting is
        # not admissible as a fully recorded run result.
        if (usage_values["total_input_tokens"] is None
                or usage_values["total_output_tokens"] is None):
            return "error", None, usage_values
        return "ok", output, usage_values
    return "error", None, usage_values


def execute_token_plan(
    plan_path: Path, parquet_path: Path, index_path: Path, out: Path,
    *, generate: Callable[[str, str, int, str], Any],
    recount_tokens: Callable[[str], int],
    allow_paid: bool, budget_usd: str,
    source_rows: Callable[[Path], Iterator[dict[str, Any]]] = _parquet_rows,
) -> dict[str, Any]:
    """Execute sequentially under explicit budget and never auto-retry a task.

    An attempted request can be billed even on timeout. Budget reservations are
    retained for uncertain attempts; observed billing is not claimed.
    """
    if not allow_paid:
        raise ReplayError("Explicit --execute-paid authorization is required")
    try:
        budget = Decimal(budget_usd)
    except (InvalidOperation, TypeError):
        raise ReplayError("--max-spend-usd must be a positive finite decimal") from None
    if not budget.is_finite() or budget <= 0:
        raise ReplayError("--max-spend-usd must be a positive finite decimal")
    # Serialize the source check, journal audit, budget accounting and
    # generation loop under one cross-process lock.
    with _exclusive_paid_run(out):
        plan = _load_plan(plan_path, index_path)
        prompts = verified_prompts(
            parquet_path, index_path,
            expected_parquet_sha256=plan["parquet_sha256"],
            expected_index_sha256=plan["index_sha256"],
            source_rows=source_rows,
        )
        if any(not row["fits_context_with_output_allowance"] for row in plan["planned_tasks"]):
            raise ReplayError("Plan contains out-of-context tasks; paid run is blocked")
        plan_sha256 = sha256_bytes(read_bytes(plan_path))
        attempts = out / "attempts"
        metadata = out / "run.json"
        if out.exists() and not metadata.is_file():
            raise ReplayError("Output directory exists without a valid run manifest")
        if not out.exists():
            out.mkdir(parents=True, exist_ok=False)
            attempts.mkdir(exist_ok=False)
            _write_exclusive(metadata, {
                "schema_version": "graphwalks-paid-run-v1",
                "model": MODEL, "plan_sha256": plan_sha256,
                "candidate_dataset_revision": DATASET_REVISION,
                "provenance": "api_self_reported_no_provider_attestation",
                "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "content_policy": "raw_model_answers_private_no_source_prompts",
            })
        else:
            existing = read_json(metadata)
            if existing.get("plan_sha256") != plan_sha256 or existing.get("model") != MODEL:
                raise ReplayError("A resume cannot change the original execution plan")
            # Validate the entire prior journal, including result contents and
            # per-task budget reservations, before authorizing any new requests.
            from .graphwalks_audit import audit_graphwalks_run
            audit_graphwalks_run(plan_path, index_path, out)
        reserved = Decimal(0)
        completed = ambiguous = sent = 0
        for task in plan["planned_tasks"]:
            ident = task["id"]
            intent = attempts / f"{ident}.intent.json"
            result_path = attempts / f"{ident}.result.json"
            upper = Decimal(task["maximum_reserved_cost_usd"])
            if intent.is_file():
                if reserved + upper > budget:
                    raise ReplayError("Existing attempt reservations exceed the supplied budget")
                if read_json(intent).get("plan_sha256") != plan_sha256:
                    raise ReplayError("Previous attempt is bound to another plan")
                reserved += upper
                if result_path.is_file():
                    completed += int(read_json(result_path).get("status") == "ok")
                else:
                    ambiguous += 1
                continue
            if reserved + upper > budget:
                break
            # The plan is user-held bytes, not authenticated provider usage.
            # Recount the exact current prompt before every billable call.
            fresh = _tokens(recount_tokens(prompts[ident]), description="pre-generation input")
            if fresh != task["input_tokens"]:
                raise ReplayError("Current provider token count differs from the approved plan")
            if fresh + plan["max_output_tokens"] > CONTEXT_LIMIT:
                raise ReplayError("Current input and output allowance exceed the model context")
            reserved += upper
            _write_exclusive(intent, {
                "id": ident, "plan_sha256": plan_sha256,
                "input_sha256": task["prompt_sha256"],
                "reserved_ceiling_usd": str(upper),
                "request_state": "possibly_billable_once_intent_created",
                "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            })
            sent += 1
            try:
                response = generate(prompts[ident], MODEL, plan["max_output_tokens"], plan["thinking_level"])
                status, output, usage = _run_status(response)
            except Exception as exc:
                status, output, usage = "error", None, {}
                # Never repeat a failed or uncertain request automatically. The
                # provider may already have billed the attempt.
                error_type = (f"ProviderHTTP_{exc.status_code}"
                              if isinstance(exc, ProviderStatusError)
                              else type(exc).__name__)
            else:
                error_type = None
            data: dict[str, Any] = {"id": ident, "status": status, "usage": usage,
                                   "error_type": error_type}
            if status == "ok":
                data["output"] = output
                completed += 1
            _write_exclusive(result_path, data)
        return {
            "schema_version": "graphwalks-paid-run-summary-v1",
            "plan_sha256": plan_sha256,
            "new_requests": sent,
            "successful_attempts": completed,
            "unresolved_attempts_without_results": ambiguous,
            "budget_reserved_usd": str(reserved),
            "budget_authorized_usd": str(budget),
            "notional_spend_only": True,
            "comparison_status": "not_comparable",
        }


def export_private_responses(plan_path: Path, index_path: Path, run_dir: Path, out: Path) -> None:
    """Export private responses for the separate source-faithful F1 scorer."""
    if out.exists():
        raise ReplayError("Response export already exists")
    # Prevent export from bypassing the independent local evidence audit.
    from .graphwalks_audit import audit_graphwalks_run
    audit_graphwalks_run(plan_path, index_path, run_dir)
    plan = read_json(plan_path)
    meta = read_json(run_dir / "run.json")
    if meta.get("plan_sha256") != sha256_bytes(read_bytes(plan_path)):
        raise ReplayError("The run manifest does not match this plan")
    rows = []
    for task in plan["planned_tasks"]:
        ident = task["id"]
        artifact = run_dir / "attempts" / f"{ident}.result.json"
        if not artifact.is_file():
            continue
        item = read_json(artifact)
        if item.get("id") != ident:
            raise ReplayError("Recorded response task ID mismatch")
        if item.get("status") == "ok" and isinstance(item.get("output"), str):
            rows.append({"id": ident, "status": "ok", "output": item["output"]})
        else:
            rows.append({"id": ident, "status": "error"})
    if not rows:
        raise ReplayError("No recorded responses available for export")
    out.parent.mkdir(parents=True, exist_ok=True)
    from .core import write_jsonl
    with tempfile.TemporaryDirectory(prefix="mcr-export-", dir=out.parent) as tmp:
        staged = Path(tmp) / "responses.jsonl"
        write_jsonl(staged, rows)
        os.link(staged, out)
