"""Enforce an explicit human budget and a complete GraphWalks diagnostic plan.

This is a second check in the Actions workflow; paid execution also enforces
its own source, token-count, context and per-request budget contracts.
No provider request is made by this script.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from model_claim_replay.core import ReplayError
from model_claim_replay.graphwalks_runtime import _load_plan

APPROVAL_PHRASE = "AUTHORIZE_PAID_GEMINI"
MAX_PILOT_USD = Decimal("100")
ALLOWED_PILOT_SIZES = frozenset({1, 2, 5, 20})


def validate_authorization(approval: str, budget_text: str) -> Decimal:
    """Verify a human-entered consent phrase and a finite capped USD amount."""
    if approval != APPROVAL_PHRASE:
        raise ReplayError("Paid pilot is disabled: exact authorization phrase is absent")
    try:
        budget = Decimal(budget_text)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ReplayError("USD spending ceiling must be a finite decimal") from exc
    if not budget.is_finite() or not Decimal(0) < budget <= MAX_PILOT_USD:
        raise ReplayError("USD spending ceiling must be positive and at most $100")
    return budget


def validate_pilot_plan(plan: dict[str, Any], *, budget: Decimal, tasks: int) -> Decimal:
    """Require full requested coverage within the approved reserved budget.

    A valid plan's internal per-task totals, source hashes and freshness are
    separately revalidated by `_load_plan` before this function is called.
    """
    if type(tasks) is not int or tasks not in ALLOWED_PILOT_SIZES:
        raise ReplayError("Diagnostic cohort must contain exactly 1, 2, 5 or 20 tasks")
    if plan.get("planned_count") != tasks or len(plan.get("planned_tasks", [])) != tasks:
        raise ReplayError("Token plan does not cover the requested diagnostic cohort")
    if plan.get("blocked_for_context") != 0:
        raise ReplayError("At least one planned prompt exceeds the model context")
    try:
        reserved = Decimal(plan["maximum_reserved_cost_usd"])
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise ReplayError("Token plan lacks a valid maximum cost reservation") from exc
    if not reserved.is_finite() or reserved <= 0 or reserved > budget:
        raise ReplayError("Full-cohort token reservation exceeds authorized USD ceiling")
    return reserved


def main() -> int:
    """Run the same explicit approval check before download and inference."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", required=True)
    parser.add_argument("--max-spend-usd", required=True)
    parser.add_argument("--tasks", type=int, required=True)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--index", type=Path)
    args = parser.parse_args()
    try:
        budget = validate_authorization(args.approval, args.max_spend_usd)
        if args.tasks not in ALLOWED_PILOT_SIZES:
            raise ReplayError("Diagnostic cohort must contain 1, 2, 5 or 20 tasks")
        if (args.plan is None) != (args.index is None):
            raise ReplayError("A plan and pinned reference index must be supplied together")
        if args.plan is not None:
            plan = _load_plan(args.plan, args.index)
            reserved = validate_pilot_plan(plan, budget=budget, tasks=args.tasks)
            print(f"Authorized all {args.tasks} planned requests; maximum reserved USD: {reserved}")
        else:
            print("Explicit pilot authorization validated; no provider request made")
    except ReplayError as exc:
        parser.exit(status=2, message=f"Paid diagnostic gate: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
