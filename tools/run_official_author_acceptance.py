"""Run the live KOSIS-first / Statistics Korea fallback acceptance case.

The script deliberately starts from a fully structured Claim so a missing LLM
credential cannot be misreported as an official-evidence result.  It still
uses the shared live Core Engine, whose Catalog resolver performs actual KOSIS
Catalog and metadata requests before the configured KOSTAT release fallback.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import Settings
from core.official_engine_factory import OfficialEnginePaths, build_official_evidence_service
from schemas.claim import ClaimSchema


OUT_DIR = ROOT / "artifacts" / "official_author_acceptance"
ARTICLE_DATE = date(2025, 8, 29)
EXPECTED_VALUE = 677_597.0
EXPECTED_PUBLISHED_AT = date(2025, 8, 28)
PATHS = OfficialEnginePaths(
    standard_path=ROOT / "data" / "semantic_standard" / "concept_seed_v1.json",
    catalog_path=ROOT / "data" / "kosis_catalog" / "catalog_350.json",
    as_of_metadata_paths=[
        ROOT / "data" / "kosis_snapshots" / "official_cpi_detail_current_axes_v1.json",
        ROOT / "data" / "kosis_snapshots" / "official_goldset_asof_v3.json",
    ],
    metadata_manifest_paths=[
        ROOT / "data" / "kosis_snapshots" / "cpi_detail_metadata_v1_manifest.json"],
)


def build_rice_area_claim() -> ClaimSchema:
    """Return the acceptance Claim after Claim extraction/split has completed."""
    return ClaimSchema(
        claim_id="acceptance_2025_domestic_rice_area",
        source_sentence="2025년 벼 재배면적은 677,597ha였다.",
        indicator="재배면적",
        value=EXPECTED_VALUE,
        unit="ha",
        time="2025",
        frequency="YEAR",
        region="전국",
        dimension={"작물": "벼"},
        calculation="DIRECT_VALUE",
        source_hint="KOSTAT",
        parse_status="AUTO_OK",
    )


def _evaluation(payload: dict[str, Any]) -> list[str]:
    """Return acceptance failures without omitting the raw engine result."""
    verdict = payload.get("verdict") or {}
    trace = verdict.get("execution_trace") or {}
    stages = trace.get("events") or []
    stage_names = {stage.get("stage") for stage in stages if isinstance(stage, dict)}
    provenance = verdict.get("official_value_provenance") or []
    author_provenance = next(
        (item for item in provenance if item.get("source") == "OFFICIAL_AUTHOR_RELEASE"), None
    )
    evidence = (author_provenance or {}).get("official_author_evidence") or {}
    failures: list[str] = []
    if payload.get("catalog_diagnostics", {}).get("attempted_queries", 0) < 1:
        failures.append("KOSIS_CATALOG_NOT_ATTEMPTED")
    if "HARD_GUARD" not in stage_names and "EVIDENCE_CELL" not in stage_names:
        failures.append("KOSIS_PIPELINE_TRACE_MISSING")
    if verdict.get("route_status") != "AUTO" or verdict.get("verdict") != "MATCH":
        failures.append("DETERMINISTIC_MATCH_NOT_REACHED")
    official_values = verdict.get("evidence_values") or []
    if official_values != [EXPECTED_VALUE]:
        failures.append("OFFICIAL_VALUE_NOT_EXPECTED_677597_HA")
    if not evidence:
        failures.append("OFFICIAL_AUTHOR_PROVENANCE_MISSING")
    else:
        if evidence.get("published_at") != EXPECTED_PUBLISHED_AT.isoformat():
            failures.append("OFFICIAL_AUTHOR_PUBLICATION_DATE_MISMATCH")
        if not str(evidence.get("source_url", "")).startswith("https://"):
            failures.append("OFFICIAL_AUTHOR_SOURCE_URL_INVALID")
        if not str(evidence.get("document_hash", "")).startswith("sha256:"):
            failures.append("OFFICIAL_AUTHOR_DOCUMENT_HASH_MISSING")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", help="Auditable output identifier; defaults to UTC timestamp.")
    args = parser.parse_args()
    settings = Settings()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    claim = build_rice_area_claim()
    payload: dict[str, Any] = {
        "source": "LIVE_KOSIS_THEN_KOSTAT_OFFICIAL_AUTHOR_ACCEPTANCE",
        "run_id": run_id,
        "article_date": ARTICLE_DATE.isoformat(),
        "expected": {
            "official_value": EXPECTED_VALUE,
            "unit": "ha",
            "published_at": EXPECTED_PUBLISHED_AT.isoformat(),
        },
        "environment": {"kosis_api_key_configured": bool(settings.kosis_api_key)},
        "claim": claim.model_dump(mode="json"),
    }
    try:
        service = build_official_evidence_service(
            PATHS, kosis_api_key=settings.kosis_api_key, live_time_budget_seconds=20.0,
        )
        resolution = service.resolve(claim, article_date=ARTICLE_DATE)
        payload.update({
            "concept": resolution.concept.model_dump(mode="json"),
            "catalog_diagnostics": resolution.catalog_diagnostics,
            "candidates": [candidate.model_dump(mode="json") for candidate in resolution.candidates],
            "verdict": resolution.verdict.model_dump(mode="json"),
        })
        payload["acceptance_failures"] = _evaluation(payload)
    except Exception as error:  # preserve operational failure without credentials or raw request URLs
        payload["error"] = {"type": type(error).__name__, "message": str(error)[:500]}
        payload["acceptance_failures"] = ["LIVE_ENGINE_EXCEPTION"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUT_DIR / f"{run_id}.json"
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    output.write_text(serialized, encoding="utf-8")
    (OUT_DIR / "latest.json").write_text(serialized, encoding="utf-8")
    print(output)
    if payload["acceptance_failures"]:
        print("ACCEPTANCE_FAILED:" + ",".join(payload["acceptance_failures"]), file=sys.stderr)
        return 1
    print("ACCEPTANCE_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
