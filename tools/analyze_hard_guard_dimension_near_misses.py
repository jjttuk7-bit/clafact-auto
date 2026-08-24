"""Write a compact audit of Claims whose nearest KOSIS candidates fail dimensions."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.hard_guard_diagnostics import summarize_hard_guard_rejections
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_jsonl", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument(
        "--reject-code",
        default="DIMENSION_MEMBER_CONFLICT",
        help="Nearest-candidate reject code to include",
    )
    args = parser.parse_args()

    rows: list[dict[str, str]] = []
    with args.input_jsonl.open(encoding="utf-8") as source:
        for line in source:
            record = json.loads(line)
            resolution = record.get("official_resolution") or {}
            verdict = resolution.get("verdict") or {}
            if verdict.get("reason_code") != "NO_HARD_GUARD_CANDIDATE":
                continue
            candidate_data = resolution.get("candidates") or []
            candidates = [KosisCandidateSchema.model_validate(item) for item in candidate_data]
            claim = ClaimSchema.model_validate(record.get("claim") or {})
            diagnostics = summarize_hard_guard_rejections(claim, candidates)
            best_codes = sorted(
                key.removeprefix("hard_guard_best_reject_")
                for key, value in diagnostics.items()
                if key.startswith("hard_guard_best_reject_") and value
            )
            if args.reject_code not in best_codes:
                continue

            min_reject_count = diagnostics.get("hard_guard_min_reject_count")
            best_candidates: list[KosisCandidateSchema] = []
            for candidate in candidates:
                candidate_diagnostics = summarize_hard_guard_rejections(
                    claim, [candidate]
                )
                if candidate_diagnostics.get("hard_guard_min_reject_count") == min_reject_count:
                    best_candidates.append(candidate)

            rows.append(
                {
                    "claim_id": claim.claim_id or str(record.get("claim_id") or ""),
                    "indicator": claim.indicator or "",
                    "dimension": json.dumps(claim.dimension, ensure_ascii=False),
                    "population": claim.population or "",
                    "region": claim.region or "",
                    "source_sentence": claim.source_sentence,
                    "nearest_reject_count": str(min_reject_count or ""),
                    "nearest_reject_codes": "|".join(best_codes),
                    "nearest_table_ids": "|".join(
                        dict.fromkeys(candidate.tbl_id for candidate in best_candidates)
                    ),
                    "nearest_table_names": "|".join(
                        dict.fromkeys(candidate.tbl_name for candidate in best_candidates)
                    ),
                }
            )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else []
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"rows": len(rows), "output": str(args.output_csv)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
