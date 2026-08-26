"""Freeze the 230 direct-value Claims into leakage-safe evaluation sets."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable

from core.direct_value_generalization_split import split_claim_rows


ADDED_FIELDS = (
    "기사그룹ID",
    "사용집합",
    "분할버전",
    "최초실행상태",
    "최초실행사유",
    "최초실패단계",
    "최초공식판정완료",
    "기준선상태",
    "기준선사유",
    "기준선실패단계",
    "기준선판정",
    "기준선공식값",
    "기준선공식좌표JSON",
    "기준선공식출처URL",
    "기준선응답해시",
    "기준선공표확인",
    "기준선공식판정완료",
    "기준선적용규칙",
    "개선후상태",
    "개선후사유",
    "개선후실패단계",
    "개선후판정",
    "개선후공식값",
    "개선후공식좌표JSON",
    "개선후공식출처URL",
    "개선후응답해시",
    "개선후공표확인",
    "개선후공식판정완료",
    "적용공통규칙ID",
)


def build_baseline_rows(
    ledger_rows: Iterable[dict[str, str]],
    rerun_rows: Iterable[dict[str, str]],
    *,
    seed: str = "clafact-direct-value-generalization-v1",
) -> list[dict[str, str]]:
    direct = [dict(row) for row in ledger_rows if row.get("최종검증유형") == "8번 직접값"]
    split_by_claim = {
        item.claim_id: item
        for item in split_claim_rows(direct, seed=seed)
    }
    by_claim = {
        str(row.get("자식Claim번호") or row.get("원본부모Claim번호") or ""): row
        for row in direct
    }
    overlays: dict[str, dict[str, str]] = {}
    for row in rerun_rows:
        if row.get("행구분") != "동일패턴7건재실행":
            continue
        claim_id = str(row.get("대상Claim번호") or "")
        if claim_id not in by_claim:
            raise ValueError(f"DIRECT_VALUE_RERUN_CLAIM_NOT_FOUND:{claim_id}")
        overlays[claim_id] = row

    output: list[dict[str, str]] = []
    for claim_id, row in by_claim.items():
        split = split_by_claim[claim_id]
        rerun = overlays.get(claim_id)
        baseline = {
            "상태": row.get("최종상태", ""),
            "사유": row.get("최종사유코드", ""),
            "실패단계": row.get("실패단계", ""),
            "판정": row.get("판정", ""),
            "공식값": row.get("공식계산값", ""),
            "공식좌표JSON": row.get("공식좌표JSON", ""),
            "공식출처URL": row.get("공식근거URL", ""),
            "응답해시": row.get("응답해시", ""),
            "공표확인": row.get("공표확인", ""),
            "공식판정완료": row.get("공식판정완료", ""),
            "적용규칙": "",
        }
        if rerun is not None:
            baseline.update({
                "상태": rerun.get("개선후상태", ""),
                "사유": rerun.get("개선후사유", ""),
                "실패단계": rerun.get("개선후실패단계", ""),
                "판정": rerun.get("판정", ""),
                "공식값": rerun.get("공식값", ""),
                "공식좌표JSON": rerun.get("공식좌표JSON", ""),
                "공식출처URL": rerun.get("공식출처URL", ""),
                "응답해시": rerun.get("응답해시", ""),
                "공표확인": rerun.get("공표확인", ""),
                "공식판정완료": rerun.get("공식근거완료", ""),
                "적용규칙": rerun.get("공식경로규칙", ""),
            })
        item = dict(row)
        item.update({
            "기사그룹ID": split.article_id,
            "사용집합": split.split_set,
            "분할버전": split.split_seed,
            "최초실행상태": row.get("최종상태", ""),
            "최초실행사유": row.get("최종사유코드", ""),
            "최초실패단계": row.get("실패단계", ""),
            "최초공식판정완료": row.get("공식판정완료", ""),
            "기준선상태": baseline["상태"],
            "기준선사유": baseline["사유"],
            "기준선실패단계": baseline["실패단계"],
            "기준선판정": baseline["판정"],
            "기준선공식값": baseline["공식값"],
            "기준선공식좌표JSON": baseline["공식좌표JSON"],
            "기준선공식출처URL": baseline["공식출처URL"],
            "기준선응답해시": baseline["응답해시"],
            "기준선공표확인": baseline["공표확인"],
            "기준선공식판정완료": baseline["공식판정완료"],
            "기준선적용규칙": baseline["적용규칙"],
            "개선후상태": baseline["상태"],
            "개선후사유": baseline["사유"],
            "개선후실패단계": baseline["실패단계"],
            "개선후판정": baseline["판정"],
            "개선후공식값": baseline["공식값"],
            "개선후공식좌표JSON": baseline["공식좌표JSON"],
            "개선후공식출처URL": baseline["공식출처URL"],
            "개선후응답해시": baseline["응답해시"],
            "개선후공표확인": baseline["공표확인"],
            "개선후공식판정완료": baseline["공식판정완료"],
            "적용공통규칙ID": baseline["적용규칙"],
        })
        output.append(item)
    return sorted(output, key=lambda row: str(row.get("자식Claim번호") or row.get("원본부모Claim번호")))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger_csv", type=Path)
    parser.add_argument("rerun_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("output_summary", type=Path)
    args = parser.parse_args()
    ledger = _read_csv(args.ledger_csv)
    rerun = _read_csv(args.rerun_csv)
    rows = build_baseline_rows(ledger, rerun)
    if len(rows) != 230:
        raise ValueError(f"DIRECT_VALUE_BASELINE_COUNT_MISMATCH:{len(rows)}:230")
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) + [field for field in ADDED_FIELDS if field not in rows[0]]
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    payload = args.output_csv.read_bytes()
    summary = {
        "claim_count": len(rows),
        "article_count": len({row["기사그룹ID"] for row in rows}),
        "split_counts": dict(Counter(row["사용집합"] for row in rows)),
        "baseline_official_complete": sum(row["기준선공식판정완료"] == "Y" for row in rows),
        "baseline_reasons": dict(Counter(row["기준선사유"] for row in rows)),
        "split_seed": rows[0]["분할버전"],
        "csv_sha256": sha256(payload).hexdigest(),
        "output_csv": str(args.output_csv.resolve()),
    }
    args.output_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    main()
