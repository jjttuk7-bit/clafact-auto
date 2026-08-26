"""Run unseen paraphrases through the exact Streamlit/OpenAI/KOSIS boundary."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date
import argparse
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings
from core.canonical_pipeline import build_canonical_pipeline
from core.dashboard_acceptance import verify_dashboard_article
from core.unit_normalizer import convert_value


CASES = (
    {
        "case_id": "UNSEEN_EMPLOYMENT_TOTAL_PARAPHRASE",
        "article_date": date(2025, 4, 20),
        "article_text": "국가데이터처 자료를 보면 2025년 3월 전국 취업자는 2858만9000명으로 집계됐다.",
        "expected_value": 28_589_000.0,
    },
    {
        "case_id": "UNSEEN_UNEMPLOYMENT_RATE_PARAPHRASE",
        "article_date": date(2025, 2, 20),
        "article_text": "국가데이터처가 확정한 2024년 12월 전국 실업률은 3.8%였다.",
        "expected_value": 3.8,
    },
    {
        "case_id": "UNSEEN_OLDER_EMPLOYMENT_RATE_PARAPHRASE",
        "article_date": date(2025, 6, 1),
        "article_text": "2025년 4월 전국 65세 이상 인구의 고용률은 40.4%로 나타났다.",
        "expected_value": 40.4,
    },
    {
        "case_id": "UNSEEN_RESTING_POPULATION_PARAPHRASE",
        "article_date": date(2025, 6, 11),
        "article_text": "국가데이터처가 발표한 2025년 5월 전국 쉬었음 인구는 239만 명으로 집계됐다.",
        "expected_value": 2_390_000.0,
    },
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--live-budget-seconds", type=float, default=30.0)
    args = parser.parse_args()
    runtime = build_canonical_pipeline(
        Settings(), live_time_budget_seconds=args.live_budget_seconds
    )
    rows: list[dict[str, Any]] = []
    for case in CASES:
        result = verify_dashboard_article(
            runtime, case["article_text"], article_published_at=case["article_date"]
        )
        entries = [_jsonable(entry) for entry in result.entries]
        matched = [entry for entry in entries if _claim_matches_expected(
            entry.get("claim") or {}, case["expected_value"]
        )]
        accepted = any(_strict_official_complete(entry) for entry in matched)
        rows.append({**case, "article_date": case["article_date"].isoformat(),
                     "accepted": accepted, "entries": entries})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "results.jsonl"
    output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    summary = {
        "input_count": len(rows),
        "passed_count": sum(bool(row["accepted"]) for row in rows),
        "failed_count": sum(not bool(row["accepted"]) for row in rows),
        "cases": {row["case_id"]: bool(row["accepted"]) for row in rows},
        "result_path": str(output.resolve()),
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


def _strict_official_complete(entry: dict[str, Any]) -> bool:
    resolution = entry.get("official_resolution") or {}
    verdict = resolution.get("verdict") or {}
    provenance = verdict.get("official_value_provenance") or []
    if entry.get("terminal_status") != "AUTO" or verdict.get("verdict") not in {"MATCH", "MISMATCH"}:
        return False
    return bool(provenance) and all(
        item.get("source") in {"API", "OFFICIAL_DOCUMENT"}
        and item.get("source_url") and item.get("content_hash") and item.get("retrieved_at")
        and isinstance(item.get("publication"), dict)
        and item["publication"].get("status") == "VERIFIED"
        for item in provenance
    )


def _claim_matches_expected(claim: dict[str, Any], expected: float) -> bool:
    value = claim.get("value")
    unit = str(claim.get("unit") or "")
    if _same_number(value, expected):
        return True
    for base_unit in ("명", "가구", "달러", "%"):
        try:
            if _same_number(convert_value(float(value), unit, base_unit), expected):
                return True
        except (TypeError, ValueError):
            continue
    return False

def _same_number(left: Any, right: Any) -> bool:
    try:
        return abs(float(left) - float(right)) <= max(1e-9, abs(float(right)) * 1e-12)
    except (TypeError, ValueError):
        return False


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return str(value)


if __name__ == "__main__":
    main()
