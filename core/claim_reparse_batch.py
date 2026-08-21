"""Source-preserving Structured Output reparse for non-AUTO gold Claims."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor

from core.claim_parser import StructuredClaimExtractor, parse_claim
from core.openai_function_claim_extractor import (
    OpenAIAuthenticationError,
    OpenAIConfigurationError,
)
from schemas.claim_registry import ClaimRegistryRecord


DERIVED_SOURCE_REF = "gold_standard_v1_openai_reparse_v1"


def reparse_non_auto_records(
    records: Iterable[ClaimRegistryRecord],
    extractor: StructuredClaimExtractor,
    *,
    workers: int = 1,
) -> tuple[list[ClaimRegistryRecord], dict[str, object]]:
    """Reparse only non-AUTO records while retaining gold identity and order."""
    source_records = list(records)

    def transform(record: ClaimRegistryRecord) -> ClaimRegistryRecord:
        if record.claim.parse_status == "AUTO_OK":
            return record
        source_status = record.claim.parse_status
        source_reason = record.claim.parse_reason
        if record.article_published_at is None:
            return _failed_record(
                record, source_status, source_reason, "ARTICLE_DATE_REQUIRED"
            )
        try:
            parsed = parse_claim(
                record.claim.source_sentence,
                extractor,
                article_published_at=record.article_published_at,
            ).model_copy(update={
                "claim_id": record.claim.claim_id,
                "source_sentence": record.claim.source_sentence,
            })
        except (OpenAIAuthenticationError, OpenAIConfigurationError):
            raise
        except Exception as error:
            return _failed_record(
                record,
                source_status,
                source_reason,
                "CLAIM_REPARSE_FAILED",
                error_type=type(error).__name__,
            )
        return record.model_copy(update={
            "claim": parsed,
            "source_ref": DERIVED_SOURCE_REF,
            "slot_enrichment": _audit(
                source_status,
                source_reason,
                parsed.parse_status,
                parsed.parse_reason,
            ),
        })

    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            output = list(executor.map(transform, source_records))
    else:
        output = [transform(record) for record in source_records]

    counts = Counter(
        "preserved_auto_ok"
        if source.claim.parse_status == "AUTO_OK"
        else (
            "reparse_errors"
            if result.claim.parse_reason in {"CLAIM_REPARSE_FAILED", "ARTICLE_DATE_REQUIRED"}
            else "reparsed_auto_ok"
            if result.claim.parse_status == "AUTO_OK"
            else "reparsed_hold"
        )
        for source, result in zip(source_records, output, strict=True)
    )
    failure_reason_counts = Counter(
        str((result.slot_enrichment or {}).get("error_type"))
        for result in output
        if (result.slot_enrichment or {}).get("error_type")
    )
    summary: dict[str, object] = {
        "total_records": len(source_records),
        "selected_records": sum(
            record.claim.parse_status != "AUTO_OK" for record in source_records
        ),
        "reparsed_auto_ok": counts["reparsed_auto_ok"],
        "reparsed_hold": counts["reparsed_hold"],
        "reparse_errors": counts["reparse_errors"],
        "preserved_auto_ok": counts["preserved_auto_ok"],
    }
    if failure_reason_counts:
        summary["failure_reason_counts"] = dict(sorted(failure_reason_counts.items()))
    return output, summary


def _failed_record(
    record: ClaimRegistryRecord,
    source_status: str,
    source_reason: str | None,
    reason_code: str,
    *,
    error_type: str | None = None,
) -> ClaimRegistryRecord:
    held = record.claim.model_copy(update={
        "parse_status": "HOLD",
        "parse_reason": reason_code,
    })
    return record.model_copy(update={
        "claim": held,
        "source_ref": DERIVED_SOURCE_REF,
        "slot_enrichment": _audit(
            source_status,
            source_reason,
            "HOLD",
            reason_code,
            error_type=error_type,
        ),
    })


def _audit(
    source_status: str,
    source_reason: str | None,
    result_status: str,
    reason_code: str | None,
    *,
    error_type: str | None = None,
) -> dict[str, object]:
    audit: dict[str, object] = {
        "stage": "CLAIM_REPARSE",
        "source_parse_status": source_status,
        "source_parse_reason_detail": source_reason,
        "result_parse_status": result_status,
        "reason_code": reason_code,
    }
    if error_type is not None:
        audit["error_type"] = error_type
    return audit
