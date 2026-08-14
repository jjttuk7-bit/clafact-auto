"""Run real KOSIS API acceptance cases and write auditable JSON results."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import Settings
from core.claim_extractor_factory import create_claim_extractor
from core.claim_parser import parse_claim
from core.official_engine_factory import OfficialEnginePaths, build_official_evidence_service
OUT_DIR = ROOT / "artifacts" / "live_kosis_acceptance"
PATHS = OfficialEnginePaths(
    standard_path=ROOT / "data" / "semantic_standard" / "concept_seed_v1.json",
    catalog_path=ROOT / "data" / "kosis_catalog" / "catalog_350.json",
    as_of_metadata_paths=[
        ROOT / "data" / "kosis_snapshots" / "official_cpi_detail_current_axes_v1.json",
        ROOT / "data" / "kosis_snapshots" / "official_goldset_asof_v3.json",
    ],
    metadata_manifest_paths=[ROOT / "data" / "kosis_snapshots" / "cpi_detail_metadata_v1_manifest.json"],
)
CASES = [
    ("employment_direct", "2024년 12월 취업자 수는 2804만1000명이었다.", "2025-01-15"),
    ("cabbage_yoy", "2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다.", "2025-11-04"),
    ("employment_multidimensional", "2024년 서울 여성 15~29세 취업자 수는 50만4500명이었다.", "2025-01-15"),
    ("share_or_ratio", "2024년 12월 여성 취업자 수는 전체 취업자 수의 44%였다.", "2025-01-15"),
    ("no_official_statistic", "2024년 12월 한국의 가상양자고용지수는 42.7점이었다.", "2025-01-15"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[name for name, *_ in CASES])
    parser.add_argument("--run-id", help="Auditable output identifier; defaults to UTC timestamp.")
    args = parser.parse_args()
    settings = Settings()
    extractor = create_claim_extractor(settings)
    service = build_official_evidence_service(PATHS, kosis_api_key=settings.kosis_api_key, live_time_budget_seconds=10.0)
    results = []
    cases = [case for case in CASES if args.case is None or case[0] == args.case]
    for name, sentence, article_date_text in cases:
        article_date = date.fromisoformat(article_date_text)
        try:
            claim = parse_claim(sentence, extractor, article_published_at=article_date)
            if claim.parse_status == "AUTO_OK":
                resolution = service.resolve(claim, article_date=article_date)
                verdict = resolution.verdict
                results.append({"case": name, "sentence": sentence, "article_date": article_date_text, "claim": claim.model_dump(mode="json"), "concept": resolution.concept.model_dump(mode="json"), "candidates": [item.model_dump(mode="json") for item in resolution.candidates], "verdict": verdict.model_dump(mode="json")})
            else:
                results.append({"case": name, "sentence": sentence, "article_date": article_date_text, "claim": claim.model_dump(mode="json"), "verdict": {"route_status": "HOLD", "reason_code": claim.parse_reason}})
        except Exception as error:
            results.append({"case": name, "sentence": sentence, "article_date": article_date_text, "error_type": type(error).__name__})
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {"source": "LIVE_KOSIS_API", "run_id": run_id, "results": results}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUT_DIR / f"{run_id}.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()