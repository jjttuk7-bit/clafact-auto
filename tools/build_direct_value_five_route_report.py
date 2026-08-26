"""Build one auditable CSV for five registered direct-value routes and seven reruns."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.direct_value_multi_claim_results import _is_official_verdict_complete


FIELDS = (
    "행구분", "공식경로규칙", "적용조건", "공식자료", "기존성공건수",
    "대상Claim번호", "원문", "개선전상태", "개선전사유", "개선전실패단계",
    "개선후상태", "개선후사유", "개선후실패단계", "판정", "기사값", "공식값",
    "단위", "기준시점", "대상집단", "차원JSON", "공식좌표JSON", "공식출처URL",
    "응답해시", "공표확인", "공식근거완료", "기존완료수", "신규완료수", "최종누적완료수",
)

RULES = (
    ("관세청 무역수지 누계 공식문서", "무역수지·누계·적자/흑자 부호가 원문과 일치", "관세청 공식 보도자료", 1),
    ("월간 전국 전체 취업자", "취업자 수·월·전국·15세 이상 전체", "KOSIS DT_1DA7001S / T30", 5),
    ("월간 전국 전체 실업률", "실업률·월·전국·세부 차원 없음", "KOSIS DT_1DA7001S / T80", 1),
    ("월간 연령별 고용률", "고용률·월·전국·연령 범위 있음", "KOSIS DT_1DA7002S / T90", 2),
    ("분기 연령·학력별 실업률", "실업률·분기·전국·연령과 학력 모두 있음", "KOSIS DT_1DA7105S / T80", 1),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before_results", type=Path)
    parser.add_argument("after_results", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("output_summary", type=Path)
    args = parser.parse_args()

    before = _load(args.before_results)
    after = _load(args.after_results)
    before_by_id = _unique(before)
    after_by_id = _unique(after)
    if set(before_by_id) != set(after_by_id) or len(after_by_id) != 7:
        raise ValueError("DIRECT_VALUE_SEVEN_CLAIM_COVERAGE_MISMATCH")

    newly_complete = sum(_is_official_verdict_complete(row) for row in after)
    if newly_complete > 7:
        raise ValueError("DIRECT_VALUE_COMPLETION_COUNT_INVALID")
    existing_complete = sum(rule[3] for rule in RULES)
    final_complete = existing_complete + newly_complete

    rows: list[dict[str, Any]] = []
    for name, condition, source, count in RULES:
        rows.append({
            **_blank(), "행구분": "공식경로규칙", "공식경로규칙": name,
            "적용조건": condition, "공식자료": source, "기존성공건수": count,
            "기존완료수": existing_complete, "신규완료수": newly_complete,
            "최종누적완료수": final_complete,
        })

    for claim_id in before_by_id:
        prior = before_by_id[claim_id]
        current = after_by_id[claim_id]
        claim = current.get("claim") or {}
        verdict = ((current.get("official_resolution") or {}).get("verdict") or {})
        evidence = verdict.get("evidence_cells") or []
        provenance = verdict.get("official_value_provenance") or []
        rows.append({
            **_blank(),
            "행구분": "동일패턴7건재실행",
            "공식경로규칙": _route_name(evidence, claim),
            "대상Claim번호": claim_id,
            "원문": claim.get("source_sentence", ""),
            "개선전상태": prior.get("terminal_status", ""),
            "개선전사유": prior.get("reason_code", ""),
            "개선전실패단계": _failure_stage(prior),
            "개선후상태": current.get("terminal_status", ""),
            "개선후사유": current.get("reason_code", ""),
            "개선후실패단계": _failure_stage(current),
            "판정": verdict.get("verdict", ""),
            "기사값": claim.get("value", ""),
            "공식값": verdict.get("calculated_value", ""),
            "단위": claim.get("unit", ""),
            "기준시점": claim.get("time", ""),
            "대상집단": claim.get("population", ""),
            "차원JSON": _json(claim.get("dimension")),
            "공식좌표JSON": _json(evidence),
            "공식출처URL": " | ".join(sorted({str(item.get("source_url")) for item in provenance if item.get("source_url")})),
            "응답해시": " | ".join(sorted({str(item.get("content_hash")) for item in provenance if item.get("content_hash")})),
            "공표확인": "VERIFIED" if provenance and all((item.get("publication") or {}).get("status") == "VERIFIED" for item in provenance) else "",
            "공식근거완료": "Y" if _is_official_verdict_complete(current) else "N",
            "기존완료수": existing_complete,
            "신규완료수": newly_complete,
            "최종누적완료수": final_complete,
        })

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "등록한공식경로규칙수": len(RULES),
        "기존공식근거완료수": existing_complete,
        "재실행대상수": len(after),
        "재실행신규공식근거완료수": newly_complete,
        "재실행일치수": sum(((row.get("official_resolution") or {}).get("verdict") or {}).get("verdict") == "MATCH" for row in after),
        "재실행불일치수": sum(((row.get("official_resolution") or {}).get("verdict") or {}).get("verdict") == "MISMATCH" for row in after),
        "재실행보류수": sum(row.get("terminal_status") != "AUTO" for row in after),
        "최종누적공식근거완료수": final_complete,
        "결과CSV": str(args.output_csv.resolve()),
    }
    args.output_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


def _route_name(evidence: list[dict[str, Any]], claim: dict[str, Any]) -> str:
    table = str(evidence[0].get("tbl_id") or "") if evidence else ""
    item = str(evidence[0].get("itm_id") or "") if evidence else ""
    return {
        ("DT_1DA7001S", "T30"): "월간 전국 전체 취업자",
        ("DT_1DA7001S", "T80"): "월간 전국 전체 실업률",
        ("DT_1DA7002S", "T90"): "월간 연령별 고용률",
        ("DT_1DA7105S", "T80"): "분기 연령·학력별 실업률",
    }.get((table, item), f"미등록 경로:{table}/{item}:{claim.get('indicator', '')}")


def _failure_stage(row: dict[str, Any]) -> str:
    for stage in reversed(row.get("stage_results") or []):
        if stage.get("status") not in {"PASS", "SKIPPED"}:
            return str(stage.get("stage") or "")
    verdict = ((row.get("official_resolution") or {}).get("verdict") or {})
    trace = (verdict.get("execution_trace") or {}).get("events") or []
    for stage in reversed(trace):
        if stage.get("status") != "PASS":
            return str(stage.get("stage") or "")
    return "VERDICT" if row.get("terminal_status") == "AUTO" else ""


def _load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _unique(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped = {str(row.get("claim_id") or ""): row for row in rows}
    if "" in mapped or len(mapped) != len(rows):
        raise ValueError("DIRECT_VALUE_RESULT_ID_NOT_UNIQUE")
    return mapped


def _blank() -> dict[str, Any]:
    return {field: "" for field in FIELDS}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True) if value not in (None, "") else ""


if __name__ == "__main__":
    main()
