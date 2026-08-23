"""Gold-case loading and auditable CSV output for bounded multi-Claim runs."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class GoldClaimCase:
    article_id: str
    sentence_id: str
    parent_claim_id: str
    source_sentence: str
    discovered_expressions: tuple[str, ...]
    expected_roles: dict[str, dict[str, str | None]]
    expected_child_count: int
    expected_route: str


def load_gold_cases(path: Path) -> list[GoldClaimCase]:
    cases: list[GoldClaimCase] = []
    with path.open(encoding="utf-8-sig", newline="") as source:
        for line_number, row in enumerate(csv.DictReader(source), start=2):
            try:
                expressions = json.loads(row["발견수치"])
                expected_roles = json.loads(row["기대역할표"])
                case = GoldClaimCase(
                    article_id=row["기사번호"].strip(),
                    sentence_id=row["문장번호"].strip(),
                    parent_claim_id=row["부모Claim번호"].strip(),
                    source_sentence=row["원문"].strip(),
                    discovered_expressions=tuple(str(item) for item in expressions),
                    expected_roles={
                        str(key): {
                            "role": str(value["role"]),
                            "group_id": (
                                str(value["group_id"])
                                if value.get("group_id")
                                else None
                            ),
                        }
                        for key, value in expected_roles.items()
                    },
                    expected_child_count=int(row["기대자식수"]),
                    expected_route=row["기대경로"].strip(),
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise ValueError(f"INVALID_MULTI_CLAIM_GOLD_ROW:{line_number}") from error
            if not all(
                (
                    case.article_id,
                    case.sentence_id,
                    case.parent_claim_id,
                    case.source_sentence,
                    case.expected_route,
                )
            ):
                raise ValueError(f"INCOMPLETE_MULTI_CLAIM_GOLD_ROW:{line_number}")
            cases.append(case)
    identities = [case.parent_claim_id for case in cases]
    if len(identities) != len(set(identities)):
        raise ValueError("DUPLICATE_MULTI_CLAIM_GOLD_ID")
    return cases


_HEADERS = (
    "기사번호",
    "문장번호",
    "부모Claim번호",
    "원문",
    "발견수치",
    "기대역할표",
    "실제역할표",
    "기대자식수",
    "실제자식수",
    "분리판정",
    "자식Claim번호",
    "12개항목상태",
    "재입장결과",
    "중단사유",
    "코드버전",
    "자료버전",
    "실행시각",
)


def write_multi_claim_evaluation_csv(
    cases: list[GoldClaimCase],
    results: list[dict[str, Any]],
    path: Path,
    *,
    code_version: str,
    data_version: str,
) -> None:
    """Write one row per recovered child, retaining unresolved parents."""

    result_by_id = {str(result.get("claim_id") or ""): result for result in results}
    if len(result_by_id) != len(results):
        raise ValueError("DUPLICATE_MULTI_CLAIM_RESULT")
    expected_ids = {case.parent_claim_id for case in cases}
    if set(result_by_id) != expected_ids:
        raise ValueError("MULTI_CLAIM_RESULT_ID_MISMATCH")
    written_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, object]] = []
    for case in cases:
        result = result_by_id[case.parent_claim_id]
        children = [
            child for child in result.get("children") or [] if isinstance(child, dict)
        ]
        actual_count = len(children)
        split_outcome = "일치" if actual_count == case.expected_child_count else "불일치"
        actual_roles = _actual_roles(children)
        row_children: list[dict[str, Any] | None] = children or [None]
        for child in row_children:
            rows.append(
                {
                    "기사번호": case.article_id,
                    "문장번호": case.sentence_id,
                    "부모Claim번호": case.parent_claim_id,
                    "원문": case.source_sentence,
                    "발견수치": _json(case.discovered_expressions),
                    "기대역할표": _json(case.expected_roles),
                    "실제역할표": _json(actual_roles),
                    "기대자식수": case.expected_child_count,
                    "실제자식수": actual_count,
                    "분리판정": split_outcome,
                    "자식Claim번호": str(child.get("claim_id") or "") if child else "",
                    "12개항목상태": _slot_summary(child),
                    "재입장결과": (
                        str(child.get("admission_route") or "")
                        if child
                        else str(result.get("status") or "")
                    ),
                    "중단사유": _stop_reason(result, child),
                    "코드버전": code_version,
                    "자료버전": data_version,
                    "실행시각": written_at,
                }
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _actual_roles(children: list[dict[str, Any]]) -> list[dict[str, object]]:
    roles: list[dict[str, object]] = []
    for index, child in enumerate(children, start=1):
        audit = child.get("recovery_audit")
        numeric_roles = audit.get("numeric_roles") if isinstance(audit, dict) else None
        if not isinstance(numeric_roles, dict):
            continue
        for expression, role in numeric_roles.items():
            roles.append(
                {
                    "expression": str(expression),
                    "role": str(role),
                    "group_id": f"g{index}",
                }
            )
    return roles


def _slot_summary(child: dict[str, Any] | None) -> str:
    if child is None:
        return ""
    audit = child.get("slot_audit")
    entries = audit.get("entries") if isinstance(audit, dict) else None
    return " | ".join(
        f"{entry.get('slot')}={entry.get('status')}"
        for entry in entries or []
        if isinstance(entry, dict) and entry.get("slot") and entry.get("status")
    )


def _stop_reason(
    result: dict[str, Any],
    child: dict[str, Any] | None,
) -> str:
    if child is not None:
        audit = child.get("slot_audit")
        reasons = audit.get("reason_codes") if isinstance(audit, dict) else None
        if reasons:
            return " | ".join(str(reason) for reason in reasons)
    return str(result.get("reason_code") or "")


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
