"""Bounded, auditable scope for direct-value multi-Claim execution."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from core.targeted_claim_splitter import discover_numeric_mentions


@dataclass(frozen=True, slots=True)
class DirectValueMultiClaimCase:
    parent_claim_id: str
    source_sentence: str
    expressions: tuple[str, ...]
    source_row: dict[str, str]


@dataclass(frozen=True, slots=True)
class DirectValueMultiClaimScope:
    parents: tuple[DirectValueMultiClaimCase, ...]
    single_cases: tuple[DirectValueMultiClaimCase, ...]
    grouping_cases: tuple[DirectValueMultiClaimCase, ...]
    source_sha256: str


CaseExecutor = Callable[[DirectValueMultiClaimCase], dict[str, Any]]


def load_direct_value_multi_claim_scope(
    source_csv: Path,
    *,
    expected_parent_count: int,
    approved_external_limit: int,
) -> DirectValueMultiClaimScope:
    """Select safe parents and stop before exceeding external-data approval."""

    source_csv = Path(source_csv).resolve()
    with source_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        if not {"Claim번호", "원문", "숫자역할안전판정"} <= headers:
            raise ValueError("MULTI_CLAIM_SCOPE_INPUT_COLUMNS_MISSING")
        rows = list(reader)

    parents: list[DirectValueMultiClaimCase] = []
    seen: set[str] = set()
    for row in rows:
        if row["숫자역할안전판정"].strip() != "SAFE_TARGET_ROLE":
            continue
        claim_id = row["Claim번호"].strip()
        source = row["원문"].strip()
        if not claim_id or not source:
            raise ValueError("MULTI_CLAIM_SCOPE_IDENTITY_MISSING")
        if claim_id in seen:
            raise ValueError(f"MULTI_CLAIM_SCOPE_DUPLICATE_PARENT:{claim_id}")
        seen.add(claim_id)
        mentions = discover_numeric_mentions(source)
        if not mentions:
            raise ValueError(f"SAFE_PARENT_WITHOUT_STATISTIC:{claim_id}")
        parents.append(
            DirectValueMultiClaimCase(
                parent_claim_id=claim_id,
                source_sentence=source,
                expressions=tuple(mention.expression for mention in mentions),
                source_row=dict(row),
            )
        )

    if len(parents) != expected_parent_count:
        raise ValueError(
            f"MULTI_CLAIM_SCOPE_PARENT_COUNT_MISMATCH:{len(parents)}:"
            f"{expected_parent_count}"
        )
    singles = tuple(case for case in parents if len(case.expressions) == 1)
    grouping = tuple(case for case in parents if len(case.expressions) >= 2)
    if len(grouping) > approved_external_limit:
        raise ValueError(
            f"APPROVED_EXTERNAL_SCOPE_EXCEEDED:{len(grouping)}:"
            f"{approved_external_limit}"
        )
    return DirectValueMultiClaimScope(
        parents=tuple(parents),
        single_cases=singles,
        grouping_cases=grouping,
        source_sha256=hashlib.sha256(source_csv.read_bytes()).hexdigest().upper(),
    )


def run_scope_with_checkpoint(
    cases: Sequence[DirectValueMultiClaimCase],
    executor: CaseExecutor,
    checkpoint_path: Path,
    *,
    signature: str,
    start: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Run at most 20 approved parents and resume only an identical signature."""

    if start < 0:
        raise ValueError("MULTI_CLAIM_START_MUST_BE_NON_NEGATIVE")
    if not 1 <= limit <= 20:
        raise ValueError("MULTI_CLAIM_LIMIT_MUST_BE_BETWEEN_1_AND_20")
    selected = list(cases[start:start + limit])
    checkpoint_path = Path(checkpoint_path)
    entries = _load_checkpoint(checkpoint_path, signature)
    for case in selected:
        previous = entries.get(case.parent_claim_id)
        if previous is not None and previous.get("completed") is True:
            continue
        result = executor(case)
        if str(result.get("parent_claim_id") or "") != case.parent_claim_id:
            raise ValueError(
                f"MULTI_CLAIM_RESULT_PARENT_MISMATCH:{case.parent_claim_id}"
            )
        entries[case.parent_claim_id] = {
            "parent_claim_id": case.parent_claim_id,
            "signature": signature,
            "completed": True,
            "result": result,
        }
        _write_checkpoint(checkpoint_path, entries, cases, signature)
    return [dict(entries[case.parent_claim_id]["result"]) for case in selected]


def _load_checkpoint(path: Path, signature: str) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    entries: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if payload.get("signature") != signature:
            continue
        parent_id = str(payload.get("parent_claim_id") or "")
        if parent_id:
            entries[parent_id] = payload
    return entries


def _write_checkpoint(
    path: Path,
    entries: dict[str, dict[str, Any]],
    cases: Sequence[DirectValueMultiClaimCase],
    signature: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(entries[case.parent_claim_id], ensure_ascii=False, sort_keys=True)
            + "\n"
            for case in cases
            if case.parent_claim_id in entries
            and entries[case.parent_claim_id].get("signature") == signature
        ),
        encoding="utf-8",
    )
    temporary.replace(path)
