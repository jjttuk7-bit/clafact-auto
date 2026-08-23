"""Build a bounded Registry for safe explicit previous-month recovery."""

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
    "Claim번호", "기사번호", "문장번호", "기사일", "원문", "원래시점",
    "복구시점", "개선전상태", "개선후상태", "복구판정", "복구사유",
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry_path", type=Path)
    parser.add_argument("ledger_path", type=Path)
    parser.add_argument("output_registry", type=Path)
    parser.add_argument("audit_csv", type=Path)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit must be positive")

    selected_ids = _ledger_candidates(args.ledger_path)
    loaded = load_claim_registry(args.registry_path)
    if loaded.errors:
        parser.error(f"SOURCE_REGISTRY_ERRORS:{len(loaded.errors)}")
    records = [record for record in loaded.records if record.claim.claim_id in selected_ids]

    output_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, str]] = []
    for record in records:
        if len(output_rows) >= args.limit:
            break
        before = record.claim
        normalized = before
        if before.time is None and before.parse_status == "HOLD":
            normalized = before.model_copy(
                update={"parse_reason": "MISSING_REQUIRED_SLOTS:time"}
            )
        recovered = recover_validated_claim(normalized, record.article_published_at)
        admitted = (
            before.time is None
            and bool(recovered.time)
            and recovered.parse_status == "AUTO_OK"
        )
        reason = (
            "EXPLICIT_PREVIOUS_MONTH_RECOVERED"
            if admitted
            else (
                "UNSAFE_EXPLICIT_MONTH"
                if not recovered.time
                else str(recovered.parse_reason or "CLAIM_CONTRACT_HOLD")
            )
        )
        audit_rows.append({
            "Claim번호": before.claim_id,
            "기사번호": record.article_id,
            "문장번호": record.sentence_id,
            "기사일": record.article_published_at.isoformat() if record.article_published_at else "",
            "원문": before.source_sentence,
            "원래시점": str(before.time or ""),
            "복구시점": str(recovered.time or ""),
            "개선전상태": before.parse_status,
            "개선후상태": recovered.parse_status,
            "복구판정": "공식조회대상" if admitted else "보류",
            "복구사유": reason,
        })
        if not admitted:
            continue
        enrichment = dict(record.slot_enrichment or {})
        enrichment.update({
            "parent_claim_id": before.claim_id,
            "recovery_method": "EXPLICIT_PREVIOUS_MONTH",
            "original_time": before.time,
            "recovered_time": recovered.time,
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


def _ledger_candidates(path: Path) -> set[str]:
    selected: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("대표문제") != "CONTEXT" or row.get("남은작업") == "완료":
                continue
            missing = re.findall(r"([a-z_]+)=MISSING", row.get("12개항목상태") or "")
            if missing == ["time"] and row.get("Claim번호"):
                selected.add(str(row["Claim번호"]))
    return selected


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
