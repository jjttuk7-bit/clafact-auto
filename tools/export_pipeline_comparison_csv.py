"""Combine canonical pipeline JSONL runs into one human-readable comparison CSV."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.hard_guard_diagnostics import format_hard_guard_rejections


FIELDS = (
    "실행구분", "부모Claim번호", "자식Claim번호", "원문", "지표", "기사수치", "단위",
    "시점", "주기", "계산방식", "구조화상태", "공식조회진입", "최종상태", "중단사유",
    "의미표준", "후보통계표수", "가까운후보탈락사유", "공식좌표", "공식값", "최종판정",
    "공식값URL", "공표URL", "응답해시", "공표해시", "실행단계",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--run", action="append", required=True, help="LABEL=JSONL_PATH")
    args = parser.parse_args()

    rows: list[dict[str, object]] = []
    for specification in args.run:
        label, separator, raw_path = specification.partition("=")
        if not separator or not label or not raw_path:
            parser.error("--run must use LABEL=JSONL_PATH")
        path = Path(raw_path)
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(_row(label, json.loads(line)))

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"rows": len(rows), "output": str(args.output_csv)}, ensure_ascii=False))


def _row(label: str, payload: dict[str, object]) -> dict[str, object]:
    claim = _dict(payload.get("claim"))
    resolution = _dict(payload.get("official_resolution"))
    verdict = _dict(resolution.get("verdict"))
    concept = _dict(resolution.get("concept"))
    diagnostics = _dict(resolution.get("catalog_diagnostics"))
    candidates = [item for item in resolution.get("candidates") or [] if isinstance(item, dict)]
    provenance = [item for item in verdict.get("official_value_provenance") or [] if isinstance(item, dict)]
    publications = [_dict(item.get("publication")) for item in provenance]
    trace = _dict(verdict.get("execution_trace"))
    events = [item for item in trace.get("events") or [] if isinstance(item, dict)]
    return {
        "실행구분": label,
        "부모Claim번호": payload.get("parent_claim_id") or payload.get("claim_id") or "",
        "자식Claim번호": payload.get("claim_id") or claim.get("claim_id") or "",
        "원문": claim.get("source_sentence") or payload.get("source_sentence") or "",
        "지표": claim.get("indicator") or "",
        "기사수치": claim.get("value") if claim.get("value") is not None else "",
        "단위": claim.get("unit") or "",
        "시점": claim.get("time") or "",
        "주기": claim.get("frequency") or "",
        "계산방식": claim.get("calculation") or "",
        "구조화상태": claim.get("parse_status") or "",
        "공식조회진입": payload.get("admission_route") or "",
        "최종상태": payload.get("terminal_status") or verdict.get("route_status") or "",
        "중단사유": payload.get("reason_code") or verdict.get("reason_code") or "",
        "의미표준": concept.get("canonical_name") or concept.get("standard_key") or "",
        "후보통계표수": len(candidates) or resolution.get("candidate_count") or 0,
        "가까운후보탈락사유": format_hard_guard_rejections(diagnostics),
        "공식좌표": _json(verdict.get("evidence_cells") or []),
        "공식값": _json(verdict.get("evidence_values") or []),
        "최종판정": verdict.get("verdict") or "",
        "공식값URL": " | ".join(_unique(str(item.get("source_url") or "") for item in provenance)),
        "공표URL": " | ".join(_unique(str(item.get("source_url") or "") for item in publications)),
        "응답해시": " | ".join(_unique(str(item.get("content_hash") or "") for item in provenance)),
        "공표해시": " | ".join(_unique(str(item.get("content_hash") or "") for item in publications)),
        "실행단계": " | ".join(
            f"{item.get('stage')}={item.get('status')}"
            + (f"({item.get('reason_code')})" if item.get("reason_code") else "")
            for item in events
        ),
    }


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _unique(values: object) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))  # type: ignore[union-attr]


if __name__ == "__main__":
    main()
