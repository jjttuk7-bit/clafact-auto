"""Run two approved type-8 articles through the exact dashboard article boundary."""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
from datetime import date
import json
from pathlib import Path
from typing import Any

from config.settings import Settings
from core.canonical_pipeline import build_canonical_pipeline
from core.dashboard_acceptance import verify_dashboard_article


CASES = (
    {
        "case_id": "TYPE8_AGE_EDUCATION_RATE_LEVEL",
        "article_date": date(2025, 6, 17),
        "article_text": "지난 1분기 기준 30대 고졸 실업률은 4.2%인 반면, 대졸 이상은 2.4%에 그쳤다.",
        "expected_value": 2.4,
        "expected_source": "API",
    },
    {
        "case_id": "TYPE8_CUMULATIVE_TRADE_BALANCE",
        "article_date": date(2025, 2, 21),
        "article_text": "연간 누계 무역 수지는 10억5600만달러 적자다.",
        "expected_value": -1_056_000_000.0,
        "expected_source": "OFFICIAL_DOCUMENT",
    },
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--live-budget-seconds", type=float, default=45.0)
    args = parser.parse_args()
    settings = Settings()
    runtime = build_canonical_pipeline(
        settings,
        live_time_budget_seconds=args.live_budget_seconds,
    )
    rows: list[dict[str, Any]] = []
    for case in CASES:
        result = verify_dashboard_article(
            runtime,
            str(case["article_text"]),
            article_published_at=case["article_date"],
        )
        entries = [_jsonable(entry) for entry in result.entries]
        matched = [
            entry for entry in entries
            if _same_number((entry.get("claim") or {}).get("value"), case["expected_value"])
        ]
        accepted = any(
            _entry_has_verified_source(entry, str(case["expected_source"]))
            for entry in matched
        )
        rows.append({
            "case_id": case["case_id"],
            "article_date": case["article_date"].isoformat(),
            "article_text": case["article_text"],
            "expected_value": case["expected_value"],
            "expected_source": case["expected_source"],
            "accepted": accepted,
            "entries": entries,
        })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    summary = {
        "input_count": len(rows),
        "passed_count": sum(row["accepted"] for row in rows),
        "failed_count": sum(not row["accepted"] for row in rows),
        "cases": {str(row["case_id"]): bool(row["accepted"]) for row in rows},
        "result_path": str((args.output_dir / "results.jsonl").resolve()),
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed_count"]:
        raise SystemExit(1)


def _entry_has_verified_source(entry: dict[str, Any], source: str) -> bool:
    resolution = entry.get("official_resolution")
    verdict = resolution.get("verdict") if isinstance(resolution, dict) else None
    if not isinstance(verdict, dict):
        return False
    if verdict.get("route_status") != "AUTO" or verdict.get("verdict") != "MATCH":
        return False
    provenance = verdict.get("official_value_provenance") or []
    return bool(provenance) and all(
        item.get("source") == source
        and item.get("source_url")
        and item.get("content_hash")
        and item.get("retrieved_at")
        and isinstance(item.get("publication"), dict)
        and item["publication"].get("status") == "VERIFIED"
        for item in provenance
    )


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
