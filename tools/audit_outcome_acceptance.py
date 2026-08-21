"""Fail closed unless a live CLAFACT outcome artifact satisfies the contract."""

import argparse
import json
from pathlib import Path

FORBIDDEN_REASONS = {
    "KOSIS_CATALOG_UNAVAILABLE", "KOSIS_METADATA_UNAVAILABLE", "FETCH_FAILED",
    "NO_HARD_GUARD_CANDIDATE", "NO_EVIDENCE_COORDINATE_CANDIDATE",
    "LOW_SEMANTIC_SCORE", "AMBIGUOUS_MARGIN", "CALCULATION_EVIDENCE_PLAN_UNRESOLVED",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.results.read_text(encoding="utf-8").splitlines() if line.strip()]
    failures = []
    parents = {(row.get("article_id"), row.get("parent_claim_id")) for row in rows}
    if len(parents) != 16: failures.append(f"INPUT_PARENT_COUNT:{len(parents)}")
    if len(rows) != 38: failures.append(f"DERIVED_CLAIM_COUNT:{len(rows)}")
    if any(row.get("recovery_action") != "MULTI_CLAIM_SPLIT" for row in rows): failures.append("MULTI_CLAIM_REENTRY_INCOMPLETE")
    auto_count = as_of_count = structural_count = 0
    for row in rows:
        resolution = row.get("official_resolution")
        if resolution is None:
            structural_count += 1
            claim = row.get("claim") or {}
            if row.get("admission_route") != "STRUCTURAL_HOLD" or claim.get("parse_reason") != "MISSING_REQUIRED_SLOTS:time":
                failures.append(f"UNJUSTIFIED_STRUCTURAL_HOLD:{row.get('claim_id')}")
            continue
        verdict = resolution.get("verdict") or {}
        reason = verdict.get("reason_code")
        if reason in FORBIDDEN_REASONS: failures.append(f"FORBIDDEN_REASON:{reason}:{row.get('claim_id')}")
        cells = verdict.get("evidence_cells") or []
        provenance = verdict.get("official_value_provenance") or []
        if not cells or any(cell.get("status") != "CONFIRMED" for cell in cells): failures.append(f"EVIDENCE_INCOMPLETE:{row.get('claim_id')}")
        if verdict.get("route_status") == "AUTO":
            auto_count += 1
            if reason not in {"WITHIN_TOLERANCE", "OUTSIDE_TOLERANCE"}: failures.append(f"AUTO_REASON_INVALID:{row.get('claim_id')}")
            if not provenance or any(item.get("source") != "API" or not item.get("content_hash") for item in provenance): failures.append(f"AUTO_PROVENANCE_INVALID:{row.get('claim_id')}")
            if verdict.get("calculated_value") is None: failures.append(f"AUTO_CALCULATION_MISSING:{row.get('claim_id')}")
        elif reason == "AS_OF_UNAVAILABLE":
            as_of_count += 1
        else:
            failures.append(f"UNJUSTIFIED_HOLD:{reason}:{row.get('claim_id')}")
    report = {
        "acceptance_passed": not failures, "input_registry_records": len(parents),
        "derived_claims": len(rows), "auto_count": auto_count,
        "as_of_hold_count": as_of_count, "structural_time_hold_count": structural_count,
        "operational_failure_count": 0 if not any("UNAVAILABLE" in failure or "FETCH" in failure for failure in failures) else 1,
        "forbidden_coordinate_failure_count": sum(failure.startswith("FORBIDDEN_REASON") for failure in failures),
        "failures": failures,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if failures: raise SystemExit(1)


if __name__ == "__main__": main()
