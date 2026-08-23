"""Crash-safe checkpointing for bounded multi-Claim group execution."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import json
from pathlib import Path
from typing import Any

from core.multi_claim_group_harness import GoldClaimCase
from core.operational_error import OperationalStageError


CaseExecutor = Callable[[GoldClaimCase], dict[str, Any]]


def run_cases_with_checkpoint(
    cases: Sequence[GoldClaimCase],
    executor: CaseExecutor,
    checkpoint_path: Path,
    *,
    signature: str,
    max_attempts: int = 2,
) -> list[dict[str, Any]]:
    """Execute each parent independently and persist every outcome immediately."""

    if max_attempts < 1:
        raise ValueError("MAX_ATTEMPTS_MUST_BE_POSITIVE")
    entries = _load_entries(checkpoint_path, signature)
    for case in cases:
        claim_id = case.parent_claim_id
        previous = entries.get(claim_id)
        if previous is not None and previous.get("completed") is True:
            continue

        result: dict[str, Any] | None = None
        completed = False
        attempts_this_run = 0
        for _ in range(max_attempts):
            attempts_this_run += 1
            try:
                result = executor(case)
            except OperationalStageError as error:
                result = _operational_failure(case, error)
                continue
            completed = True
            break

        assert result is not None
        prior_attempts = int(previous.get("attempts") or 0) if previous else 0
        entries[claim_id] = {
            "claim_id": claim_id,
            "signature": signature,
            "completed": completed,
            "attempts": prior_attempts + attempts_this_run,
            "result": result,
        }
        _write_entries(checkpoint_path, entries, cases)

    return [dict(entries[case.parent_claim_id]["result"]) for case in cases]


def _operational_failure(
    case: GoldClaimCase,
    error: OperationalStageError,
) -> dict[str, Any]:
    return {
        "claim_id": case.parent_claim_id,
        "status": "HUMAN_REVIEW",
        "reason_code": "CLAIM_GROUPING_PROVIDER_FAILURE",
        "stop_stage": error.stage,
        "executed_stages": [error.stage],
        "children": [],
        "diagnostic_id": error.diagnostic_id,
    }


def _load_entries(path: Path, signature: str) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    entries: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if payload.get("signature") != signature:
            continue
        claim_id = str(payload.get("claim_id") or "")
        if claim_id:
            entries[claim_id] = payload
    return entries


def _write_entries(
    path: Path,
    entries: dict[str, dict[str, Any]],
    cases: Sequence[GoldClaimCase],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(entries[case.parent_claim_id], ensure_ascii=False, sort_keys=True)
            + "\n"
            for case in cases
            if case.parent_claim_id in entries
        ),
        encoding="utf-8",
    )
    temporary.replace(path)
