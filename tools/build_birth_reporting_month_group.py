"""Build a bounded Registry for source-grounded monthly birth growth Claims."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import sys
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.claim_registry_loader import load_claim_registry
from core.validated_claim_recovery import recover_validated_claim


AUDIT_HEADERS = (
    "Claim번호", "기사번호", "문장번호", "기사일", "원문", "원래시점", "원래주기",
    "복구시점", "복구주기", "개선전상태", "개선후상태", "복구판정", "복구사유",
)
_MONTH_RANGE = re.compile(r"(?:1[0-2]|[1-9])\s*[~～∼\-–]\s*(?:1[0-2]|[1-9])월")
_YEAR_OVER_YEAR = re.compile(r"전년\s*(?:동월|같은\s*달)|지난해\s*같은\s*달|1년\s*전")
_INCREASE = re.compile(r"증가|늘(?:었|어|었다|었다고|어나)|상승")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry_path", type=Path)
    parser.add_argument("ledger_path", type=Path)
    parser.add_argument("output_registry", type=Path)
    parser.add_argument("audit_csv", type=Path)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 20:
        parser.error("--limit must be between 1 and 20")

    selected_ids = _ledger_candidates(args.ledger_path)
    loaded = load_claim_registry(args.registry_path)
    if loaded.errors:
        parser.error(f"SOURCE_REGISTRY_ERRORS:{len(loaded.errors)}")
    records = [
        record for record in loaded.records
        if record.claim.claim_id in selected_ids
        and _key(record.claim.indicator) == _key("출생아 수")
    ]

    output_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, str]] = []
    for record in records:
        before = record.claim
        recovered = before
        reason = _eligibility_reason(before)
        if reason is None:
            comparison = dict(before.comparison or {})
            comparison.setdefault("type", "YEAR_OVER_YEAR")
            condition = dict(before.condition or {})
            condition.setdefault("direction", "INCREASE")
            prepared = before.model_copy(update={
                "comparison": comparison,
                "condition": condition,
            })
            recovered = recover_validated_claim(
                prepared,
                record.article_published_at,
                source_value_text=prepared.source_sentence,
                context_comparison_type="YEAR_OVER_YEAR",
            )
            if recovered.frequency != "월" or recovered.time == before.time:
                reason = "SOURCE_REPORTING_MONTH_NOT_UNIQUE"
            elif recovered.parse_status != "AUTO_OK":
                reason = str(recovered.parse_reason or "CLAIM_CONTRACT_HOLD")
            elif len(output_rows) >= args.limit:
                reason = "GROUP_LIMIT_REACHED"

        admitted = reason is None
        audit_rows.append({
            "Claim번호": before.claim_id,
            "기사번호": record.article_id,
            "문장번호": record.sentence_id,
            "기사일": record.article_published_at.isoformat() if record.article_published_at else "",
            "원문": before.source_sentence,
            "원래시점": str(before.time or ""),
            "원래주기": str(before.frequency or ""),
            "복구시점": str(recovered.time or ""),
            "복구주기": str(recovered.frequency or ""),
            "개선전상태": before.parse_status,
            "개선후상태": recovered.parse_status,
            "복구판정": "공식조회대상" if admitted else "보류",
            "복구사유": "SOURCE_REPORTING_MONTH_RECOVERED" if admitted else str(reason),
        })
        if not admitted:
            continue
        enrichment = dict(record.slot_enrichment or {})
        enrichment.update({
            "parent_claim_id": before.claim_id,
            "recovery_method": "SOURCE_REPORTING_MONTH",
            "original_time": before.time,
            "original_frequency": before.frequency,
            "recovered_time": recovered.time,
            "recovered_frequency": recovered.frequency,
        })
        output_rows.append(record.model_copy(update={
            "claim": recovered,
            "slot_enrichment": enrichment,
        }).model_dump(mode="json"))

    _write_jsonl(args.output_registry, output_rows)
    _write_csv(args.audit_csv, audit_rows)
    print(json.dumps({
        "evaluated_count": len(audit_rows),
        "official_pipeline_input_count": len(output_rows),
        "held_count": len(audit_rows) - len(output_rows),
        "output_registry": str(args.output_registry),
        "audit_csv": str(args.audit_csv),
    }, ensure_ascii=False, sort_keys=True))
    return 0


def _eligibility_reason(claim) -> str | None:
    if claim.calculation != "GROWTH_RATE":
        return "CALCULATION_TYPE_NOT_SUPPORTED"
    if _MONTH_RANGE.search(claim.source_sentence):
        return "MONTH_RANGE_NOT_SUPPORTED"
    comparison_type = str((claim.comparison or {}).get("type") or "").upper()
    if comparison_type not in {"", "YEAR_OVER_YEAR"}:
        return "COMPARISON_TYPE_NOT_SUPPORTED"
    if not _YEAR_OVER_YEAR.search(claim.source_sentence):
        return "YEAR_OVER_YEAR_NOT_SOURCE_GROUNDED"
    if not _INCREASE.search(claim.source_sentence):
        return "DIRECTION_NOT_SOURCE_GROUNDED"
    return None


def _ledger_candidates(path: Path) -> set[str]:
    latest: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            claim_id = str(row.get("Claim번호") or "")
            if claim_id:
                latest[claim_id] = row
    return {
        claim_id for claim_id, row in latest.items()
        if row.get("현재문제묶음") == "COORDINATE"
        and row.get("남은작업") != "완료"
    }


def _key(value: str | None) -> str:
    return re.sub(r"[\s_\-]", "", value or "").casefold()


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
