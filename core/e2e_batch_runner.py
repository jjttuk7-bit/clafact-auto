"""Reproducible profile-first batch verification orchestration."""

import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from core.calculation_execution import execute_calculation_plan
from core.calculation_planner import build_calculation_plan
from core.claim_value_provenance import has_explicit_percent_value
from core.unit_normalizer import convert_value
from core.e2e_trace import build_e2e_trace
from core.kosis_fetcher import OfficialValueFetcher
from core.profile_first import resolve_profile_first
from core.verdict_engine import make_verdict
from core.verification_evidence_service import resolve_profile_evidence
from schemas.claim_registry import ClaimRegistryRecord
from schemas.concept import StandardConceptSchema
from schemas.evidence import EvidenceCellSchema
from schemas.verification_profile import VerificationProfileSchema


def run_e2e_batch(
    records: Iterable[ClaimRegistryRecord],
    profiles: Iterable[VerificationProfileSchema],
    concepts: Mapping[tuple[str, str], StandardConceptSchema],
    *,
    snapshot_paths: Iterable[Any] = (),
    api_lookup: Callable[[EvidenceCellSchema], list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    """Run only deterministic profile/evidence/value stages; never invent values."""
    profile_list = list(profiles)
    fetcher = OfficialValueFetcher(snapshot_paths, api_lookup=api_lookup)
    results: list[dict[str, Any]] = []
    for record in records:
        try:
            key = (record.article_id, record.sentence_id)
            concept = concepts.get(key)
            base = {
                "article_id": record.article_id,
                "sentence_id": record.sentence_id,
                "claim_id": record.claim.claim_id,
                "route_status": "HOLD",
                "reason_code": None,
                "profile_id": None,
                "official_value": None,
                "snapshot_hash": "",
                "versions": {},
            }
            if record.claim.parse_status != "AUTO_OK":
                base["route_status"] = "HOLD"
                base["reason_code"] = _parse_hold_reason(
                    record.claim.parse_status, record.claim.parse_reason
                )
                results.append(_with_execution_trace(base))
                continue
            if concept is None:
                base["reason_code"] = "CONCEPT_NOT_FOUND"
                results.append(_with_execution_trace(base))
                continue
            selection = resolve_profile_first(record.claim, concept, profile_list)
            if selection.status == "NOT_FOUND":
                base["reason_code"] = "PROFILE_NOT_FOUND"
                results.append(_with_execution_trace(base))
                continue
            if selection.status == "HOLD" or selection.profile is None:
                base["reason_code"] = selection.reason_code
                results.append(_with_execution_trace(base))
                continue
            if (
                record.claim.unit == "%"
                and record.claim.value is not None
                and not has_explicit_percent_value(
                    record.claim.source_sentence, record.claim.value
                )
            ):
                base["reason_code"] = "CLAIM_VALUE_NOT_EXPLICIT_IN_SOURCE"
                results.append(_with_execution_trace(base))
                continue
            base["profile_id"] = selection.profile.profile_id
            base["versions"] = _versions(selection.profile)
            evidence = resolve_profile_evidence(record.claim, selection.profile, period=_period(record.claim.time))
            if evidence.status == "HOLD" or evidence.evidence_cell is None:
                base["reason_code"] = evidence.reason_code
                results.append(_with_execution_trace(base))
                continue
            plan_claim = record.claim.model_copy(
                update={"calculation": selection.profile.calculation_type}
            )
            plan = build_calculation_plan(plan_claim, evidence.evidence_cell)
            if plan is None:
                base["reason_code"] = "CALCULATION_PLAN_UNRESOLVED"
                results.append(_with_execution_trace(base))
                continue
            execution = execute_calculation_plan(plan, fetcher, article_date=record.article_published_at)
            base["snapshot_hashes"] = execution.snapshot_hashes
            if execution.status != "SUCCESS":
                base["reason_code"] = execution.status
                results.append(_with_execution_trace(base))
                continue
            claim_value_for_verdict = record.claim.value
            if (
                selection.profile.calculation_type == "DIRECT_VALUE"
                and record.claim.value is not None
                and record.claim.unit is not None
            ):
                claim_value_for_verdict = convert_value(
                    record.claim.value, record.claim.unit, selection.profile.unit
                )
                base["claim_value_in_profile_unit"] = claim_value_for_verdict
            verdict = make_verdict(
                record.claim.claim_id,
                claim_value_for_verdict,
                execution.values,
                execution.calculated_value,
                tolerance=0.05,
            )
            base.update(
                {
                    "route_status": verdict.route_status,
                    "official_value": execution.values[0],
                    "evidence_values": execution.values,
                    "calculated_value": execution.calculated_value,
                    "verdict": verdict.verdict,
                    "reason_code": verdict.reason_code,
                }
            )
            results.append(_with_execution_trace(base))
        except Exception as error:
            results.append(_batch_record_error(record, error))
    return results


def summarize_e2e_batch(results: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(results)
    routes = Counter(str(row["route_status"]) for row in rows)
    reasons = Counter(str(row["reason_code"]) for row in rows if row.get("reason_code"))
    profiles = sum(row.get("profile_id") is not None for row in rows)
    values = sum(row.get("official_value") is not None for row in rows)
    return {
        "total_records": len(rows),
        "route_counts": dict(sorted(routes.items())),
        "hold_reason_counts": dict(sorted(reasons.items())),
        "profile_coverage": {"matched": profiles, "unmatched": len(rows) - profiles},
        "snapshot_coverage": {"with_official_value": values, "without_official_value": len(rows) - values},
    }


def _period(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월", value)
    return f"{match.group(1)}-{int(match.group(2)):02d}" if match else value


def _parse_hold_reason(parse_status: str, parse_reason: str | None) -> str:
    """Preserve parser state in the reason while keeping final E2E routes AUTO/HOLD."""
    if parse_status == "HUMAN_REVIEW":
        return f"PARSE_HUMAN_REVIEW: {parse_reason or 'UNSPECIFIED'}"
    return f"PARSE_{parse_reason or parse_status}"


def _versions(profile: VerificationProfileSchema) -> dict[str, str]:
    return {
        name: getattr(profile, name)
        for name in (
            "dataset_version",
            "preprocess_version",
            "claim_schema_version",
            "semantic_standard_version",
            "kosis_catalog_version",
            "matching_version",
            "calculation_version",
        )
    }


def _with_execution_trace(result: dict[str, Any]) -> dict[str, Any]:
    result["execution_trace"] = build_e2e_trace(
        str(result["claim_id"]),
        route_status=str(result["route_status"]),
        reason_code=result["reason_code"],
        multi_evidence=bool(result.get("evidence_values") and len(result["evidence_values"]) > 1),
    ).model_dump(mode="json")
    return result

def _batch_record_error(record: ClaimRegistryRecord, error: Exception) -> dict[str, Any]:
    """Convert an unexpected per-Claim failure into an auditable HOLD result."""
    return _with_execution_trace({
        "article_id": record.article_id,
        "sentence_id": record.sentence_id,
        "claim_id": record.claim.claim_id,
        "route_status": "HOLD",
        "reason_code": "BATCH_RECORD_ERROR",
        "error_type": type(error).__name__,
        "profile_id": None,
        "official_value": None,
        "snapshot_hash": "",
        "versions": {},
    })

