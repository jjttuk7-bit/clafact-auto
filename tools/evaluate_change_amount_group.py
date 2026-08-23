"""Evaluate a bounded change-amount group from persisted official evidence."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


MAX_GROUP_SIZE = 20
CSV_FIELDS = (
    "claim_id", "reclassified", "calculation", "official_periods",
    "official_values", "official_api_cells", "publication_verified_cells",
    "calculated_value", "terminal_verdict", "terminal_reason",
    "gate_passed", "gate_reasons",
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    requested = list(dict.fromkeys(args.claim_ids))
    if not requested:
        parser.error("one or more explicit --claim-id values are required")
    if len(requested) > MAX_GROUP_SIZE:
        parser.error(f"at most {MAX_GROUP_SIZE} --claim-id values are allowed")
    if args.output_csv.exists():
        parser.error("output already exists; choose a new output path")

    reclassified = _load_reclassification(args.reclassification_csv)
    results = _load_results(args.results_jsonl)
    rows = [
        evaluate_claim(
            claim_id,
            reclassified=reclassified.get(claim_id) == "RECLASSIFIED",
            result=results.get(claim_id),
        )
        for claim_id in requested
    ]
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    passed = all(row["gate_passed"] == "true" for row in rows)
    print(json.dumps({
        "claim_count": len(rows),
        "passed_count": sum(row["gate_passed"] == "true" for row in rows),
        "group_passed": passed,
        "output_csv": str(args.output_csv),
    }, ensure_ascii=False))
    return 0 if passed else 1


def evaluate_claim(
    claim_id: str, *, reclassified: bool, result: dict[str, Any] | None,
) -> dict[str, str]:
    reasons: list[str] = []
    if result and str(result.get("claim_id") or "") != claim_id:
        reasons.append("RESULT_CLAIM_ID_MISMATCH")
    if not reclassified:
        reasons.append("NOT_RECLASSIFIED")
    if result is None:
        reasons.append("OFFICIAL_RESULT_MISSING")
        result = {}
    claim = _dict(result.get("claim"))
    resolution = _dict(result.get("official_resolution"))
    verdict = _dict(resolution.get("verdict"))
    evidence = [_dict(item) for item in verdict.get("evidence_cells") or []]
    provenance = [_dict(item) for item in verdict.get("official_value_provenance") or []]
    calculation = str(claim.get("calculation") or "")
    official_values = verdict.get("evidence_values") or []
    periods = [str(item.get("prd_de") or "") for item in evidence]
    if len(official_values) != 2 or len(periods) != 2 or any(not period for period in periods) or len(set(periods)) != 2:
        reasons.append("OFFICIAL_OPERANDS_INCOMPLETE")
    if calculation != "DIFFERENCE":
        reasons.append("CALCULATION_NOT_DIFFERENCE")
    if len(evidence) != 2:
        reasons.append("OFFICIAL_EVIDENCE_NOT_TWO_CELLS")
    api_count = sum(item.get("source") == "API" for item in provenance)
    publication_count = sum(
        _dict(item.get("publication")).get("status") == "VERIFIED"
        for item in provenance
    )
    if len(provenance) != 2 or api_count != 2:
        reasons.append("OFFICIAL_API_PROVENANCE_INCOMPLETE")
    if len(provenance) != 2 or publication_count != 2:
        reasons.append("PUBLICATION_EVIDENCE_INCOMPLETE")
    if len(provenance) == 2 and any(
        not item.get("source_url")
        or not item.get("content_hash")
        or not item.get("retrieved_at")
        for item in provenance
    ):
        reasons.append("OFFICIAL_VALUE_AUDIT_FIELDS_INCOMPLETE")
    if len(provenance) == 2 and any(
        not _dict(item.get("publication")).get("source_url")
        or not _dict(item.get("publication")).get("content_hash")
        or not _dict(item.get("publication")).get("retrieved_at")
        for item in provenance
    ):
        reasons.append("PUBLICATION_AUDIT_FIELDS_INCOMPLETE")
    if verdict.get("calculated_value") is None:
        reasons.append("PYTHON_CALCULATION_MISSING")
    terminal_verdict = str(verdict.get("verdict") or "")
    if result.get("terminal_status") != "AUTO" or terminal_verdict not in {"MATCH", "MISMATCH"}:
        reasons.append("TERMINAL_VERDICT_INCOMPLETE")
    trace = _dict(verdict.get("execution_trace"))
    stage_statuses = {
        str(event.get("stage") or ""): str(event.get("status") or "")
        for event in trace.get("events") or []
        if isinstance(event, dict)
    }
    for stage in ("OFFICIAL_VALUE_FETCH", "CALCULATION", "VERDICT"):
        if stage_statuses.get(stage) != "PASS":
            reasons.append(f"STAGE_NOT_PASS:{stage}")
    return {
        "claim_id": claim_id,
        "reclassified": "true" if reclassified else "false",
        "calculation": calculation,
        "official_periods": "|".join(periods),
        "official_values": "|".join(str(value) for value in official_values),
        "official_api_cells": str(api_count),
        "publication_verified_cells": str(publication_count),
        "calculated_value": str(verdict.get("calculated_value") if verdict.get("calculated_value") is not None else ""),
        "terminal_verdict": terminal_verdict,
        "terminal_reason": str(result.get("reason_code") or verdict.get("reason_code") or ""),
        "gate_passed": "false" if reasons else "true",
        "gate_reasons": "|".join(reasons),
    }


def _load_reclassification(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {str(row.get("claim_id") or ""): str(row.get("result") or "") for row in rows}


def _load_results(path: Path) -> dict[str, dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {str(row.get("claim_id") or ""): row for row in rows if isinstance(row, dict)}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reclassification_csv", type=Path)
    parser.add_argument("results_jsonl", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--claim-id", dest="claim_ids", action="append", default=[])
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
