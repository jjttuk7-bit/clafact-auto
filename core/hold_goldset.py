"""Build reproducible human-review candidates from HOLD pipeline records."""

from __future__ import annotations

import csv
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


GOLDSET_SCHEMA_VERSION = "1.0"
DEFAULT_SEED = "20260820"
DEFAULT_QUOTAS: dict[str, int] = {
    "CLAIM_PARSE_UNCERTAIN": 86,
    "NO_EVIDENCE_COORDINATE_CANDIDATE": 44,
    "NO_HARD_GUARD_CANDIDATE": 29,
    "AMBIGUOUS_MARGIN": 18,
    "LOW_SEMANTIC_SCORE": 17,
    "AS_OF_UNAVAILABLE": 17,
    "CALCULATION_EVIDENCE_PLAN_UNRESOLVED": 16,
    "CONCEPT_NOT_FOUND": 15,
    "PUBLICATION_FETCH_FAILED": 6,
    "FETCH_FAILED": 1,
    "KOSIS_CATALOG_UNAVAILABLE": 1,
}


_OUT_OF_SCOPE = re.compile(r"미 노동부|미국 노동부|아일랜드|중동|KAIDA|한국수입자동차협회|카이즈유|키움증권|HMG그룹|테슬라|벤츠|BMW|압타밀|백산수")
_FORECAST = re.compile(r"전망|것으로 봤|가능할 것|추정")
_RELATIVE_PERIOD = re.compile(r"지난달|이달|올해|작년")
_ROOT_CAUSE_BY_REASON = {
    "CLAIM_PARSE_UNCERTAIN": "CLAIM_PARSING",
    "AMBIGUOUS_MARGIN": "SEMANTIC_STANDARD",
    "LOW_SEMANTIC_SCORE": "SEMANTIC_STANDARD",
    "CONCEPT_NOT_FOUND": "SEMANTIC_STANDARD",
    "NO_HARD_GUARD_CANDIDATE": "SEMANTIC_STANDARD",
    "NO_EVIDENCE_COORDINATE_CANDIDATE": "EVIDENCE_COORDINATE",
    "CALCULATION_EVIDENCE_PLAN_UNRESOLVED": "EVIDENCE_COORDINATE",
    "AS_OF_UNAVAILABLE": "AS_OF_PUBLICATION",
    "PUBLICATION_FETCH_FAILED": "AS_OF_PUBLICATION",
    "FETCH_FAILED": "OFFICIAL_FETCH",
    "KOSIS_CATALOG_UNAVAILABLE": "KOSIS_CATALOG",
}


def review_hold_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Produce an AI provisional diagnostic label from a sentence and its trace reason."""
    sentence = str(record.get("source_sentence") or "")
    reason = str(record.get("reason_code") or "")
    if _OUT_OF_SCOPE.search(sentence):
        return {"review_status": "AI_PROVISIONAL_REVIEWED", "automation_feasibility": "NOT_AUTO_VERIFIABLE", "primary_root_cause": "KOSIS_OUT_OF_SCOPE", "exact_kosis_coordinate_resolvable": "NO", "reviewer_confidence": "HIGH", "reviewer_notes": "Sentence identifies a foreign or private-source statistic; do not force a KOSIS coordinate."}
    if _FORECAST.search(sentence):
        return {"review_status": "AI_PROVISIONAL_REVIEWED", "automation_feasibility": "NOT_AUTO_VERIFIABLE", "primary_root_cause": "ARTICLE_INFORMATION_MISSING", "exact_kosis_coordinate_resolvable": "NO", "reviewer_confidence": "MEDIUM", "reviewer_notes": "Forecast or conditional wording is not a directly observable official-statistics claim."}
    root_cause = _ROOT_CAUSE_BY_REASON.get(reason, "ARTICLE_INFORMATION_MISSING")
    if _RELATIVE_PERIOD.search(sentence) and "통계청" not in sentence and "국가데이터처" not in sentence and "관세청" not in sentence:
        feasibility, confidence, note = "CONTEXT_REQUIRED", "MEDIUM", "Relative period requires the article publication date or cited release before exact coordinate resolution."
    else:
        feasibility, confidence, note = "AUTO_VERIFIABLE", "MEDIUM", f"Sentence contains a statistical claim; current primary bottleneck is {root_cause}."
    return {"review_status": "AI_PROVISIONAL_REVIEWED", "automation_feasibility": feasibility, "primary_root_cause": root_cause, "exact_kosis_coordinate_resolvable": "UNKNOWN", "reviewer_confidence": confidence, "reviewer_notes": note}

REVIEW_TEMPLATE: dict[str, Any] = {
    "review_status": "PENDING",
    "automation_feasibility": None,
    "primary_root_cause": None,
    "exact_kosis_coordinate_resolvable": None,
    "reviewer_confidence": None,
    "reviewer_notes": None,
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read non-empty JSONL rows from an E2E result artifact."""
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def select_hold_sample(
    records: Iterable[Mapping[str, Any]],
    quotas: Mapping[str, int] = DEFAULT_QUOTAS,
    seed: str = DEFAULT_SEED,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return all HOLD records and a deterministic per-reason sample."""
    holds = [dict(record) for record in records if record.get("route_status") == "HOLD"]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in holds:
        reason = record.get("reason_code")
        if not isinstance(reason, str) or not reason:
            raise ValueError("Every HOLD record must contain a non-empty reason_code.")
        grouped[reason].append(record)

    unknown_reasons = set(grouped) - set(quotas)
    if unknown_reasons:
        raise ValueError(f"No sampling quota for HOLD reason(s): {sorted(unknown_reasons)}")

    sample: list[dict[str, Any]] = []
    for reason in sorted(quotas):
        quota = quotas[reason]
        candidates = sorted(grouped.get(reason, []), key=lambda item: str(item.get("claim_id", "")))
        if len(candidates) < quota:
            raise ValueError(f"Quota {quota} exceeds {reason} population {len(candidates)}.")
        chooser = random.Random(f"{seed}:{reason}")
        sample.extend(chooser.sample(candidates, quota))

    return holds, sorted(sample, key=lambda item: (str(item["reason_code"]), str(item["claim_id"])))


def _review_candidate(record: Mapping[str, Any]) -> dict[str, Any]:
    candidate = dict(record)
    candidate["goldset_schema_version"] = GOLDSET_SCHEMA_VERSION
    candidate["review"] = dict(REVIEW_TEMPLATE)
    return candidate


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def _write_review_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    fields = [
        "claim_id", "article_id", "sentence_id", "source_sentence", "pipeline_reason_code",
        "review_status", "automation_feasibility", "primary_root_cause", "exact_kosis_coordinate_resolvable",
        "reviewer_confidence", "reviewer_notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            review = row["review"]
            writer.writerow({
                "claim_id": row.get("claim_id"),
                "article_id": row.get("article_id"),
                "sentence_id": row.get("sentence_id"),
                "source_sentence": row.get("source_sentence"),
                "pipeline_reason_code": row.get("reason_code"),
                **review,
            })


def _write_guideline(path: Path) -> None:
    path.write_text(
        """# HOLD Gold Set Candidate v1 — Human Review Guide

This is a review-ready candidate set, not a completed ground-truth Gold Set.
Each row must be reviewed against the article context and official KOSIS evidence.

## Review fields

- `automation_feasibility`: `AUTO_VERIFIABLE`, `CONTEXT_REQUIRED`, or `NOT_AUTO_VERIFIABLE`.
- `primary_root_cause`: one of `CLAIM_PARSING`, `SEMANTIC_STANDARD`, `KOSIS_CATALOG`,
  `EVIDENCE_COORDINATE`, `AS_OF_PUBLICATION`, `OFFICIAL_FETCH`, `KOSIS_OUT_OF_SCOPE`,
  `ARTICLE_INFORMATION_MISSING`.
- `exact_kosis_coordinate_resolvable`: `YES`, `NO`, or `UNKNOWN`.
- `reviewer_confidence`: `HIGH`, `MEDIUM`, or `LOW`.

Do not infer an official value. When marking a row `AUTO_VERIFIABLE`, record the official
KOSIS table and coordinate in `reviewer_notes`; the final verdict remains subject to a direct
official query and deterministic calculation.
""",
        encoding="utf-8",
    )



def write_ai_provisional_reviews(sample_path: Path, output_dir: Path) -> dict[str, Any]:
    """Write sentence-and-trace based AI review labels without changing the source sample."""
    if output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {output_dir}")
    reviewed: list[dict[str, Any]] = []
    for record in read_jsonl(sample_path):
        labeled = dict(record)
        labeled["review"] = review_hold_record(labeled)
        labeled["goldset_schema_version"] = GOLDSET_SCHEMA_VERSION
        reviewed.append(labeled)

    output_dir.mkdir(parents=True)
    _write_jsonl(output_dir / "review_sample_ai_provisional.jsonl", reviewed)
    _write_review_csv(output_dir / "review_sample_ai_provisional.csv", reviewed)
    report = {
        "goldset_schema_version": GOLDSET_SCHEMA_VERSION,
        "source_sample": str(sample_path),
        "reviewed_count": len(reviewed),
        "review_status": "AI_PROVISIONAL_REVIEWED",
        "automation_feasibility_counts": dict(sorted(Counter(row["review"]["automation_feasibility"] for row in reviewed).items())),
        "primary_root_cause_counts": dict(sorted(Counter(row["review"]["primary_root_cause"] for row in reviewed).items())),
        "confidence_counts": dict(sorted(Counter(row["review"]["reviewer_confidence"] for row in reviewed).items())),
        "limitations": "AI sentence-and-trace review; no official value, coordinate, or final verdict is asserted.",
    }
    (output_dir / "ai_review_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report

def write_hold_goldset(
    input_path: Path,
    output_dir: Path,
    quotas: Mapping[str, int] = DEFAULT_QUOTAS,
    seed: str = DEFAULT_SEED,
) -> dict[str, Any]:
    """Create immutable review artifacts; refuses to overwrite an existing directory."""
    if output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {output_dir}")
    records = read_jsonl(input_path)
    holds, sample = select_hold_sample(records, quotas=quotas, seed=seed)
    candidates = [_review_candidate(record) for record in sample]

    output_dir.mkdir(parents=True)
    _write_jsonl(output_dir / "hold_inventory.jsonl", holds)
    _write_jsonl(output_dir / "review_sample.jsonl", candidates)
    _write_review_csv(output_dir / "review_sample.csv", candidates)
    _write_guideline(output_dir / "LABELING_GUIDE.md")

    report = {
        "goldset_schema_version": GOLDSET_SCHEMA_VERSION,
        "source_results": str(input_path),
        "source_record_count": len(records),
        "hold_population_count": len(holds),
        "hold_reason_counts": dict(sorted(Counter(row["reason_code"] for row in holds).items())),
        "sample_count": len(candidates),
        "sample_reason_counts": dict(sorted(Counter(row["reason_code"] for row in sample).items())),
        "sampling_seed": seed,
        "sampling_method": "deterministic stratified sampling with fixed reason quotas",
        "review_status": "PENDING_HUMAN_REVIEW",
    }
    (output_dir / "sampling_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report

