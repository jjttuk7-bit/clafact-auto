"""OpenAI reparse using only a title and bounded sentence neighborhood."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from core.claim_parser import StructuredClaimExtractor, parse_claim
from core.openai_function_claim_extractor import (
    OpenAIAuthenticationError,
    OpenAIConfigurationError,
)
from schemas.claim_registry import ClaimRegistryRecord


DERIVED_SOURCE_REF = "gold_standard_v1_openai_context_reparse_v1"


def reparse_records_with_limited_context(
    records: Iterable[ClaimRegistryRecord],
    extractor: StructuredClaimExtractor,
    contexts_by_article: Mapping[str, Mapping[str, Any]],
    *,
    neighborhood_chars: int = 500,
) -> tuple[list[ClaimRegistryRecord], dict[str, int]]:
    """Reparse records without ever sending an article's full body to the extractor."""
    if neighborhood_chars < 0:
        raise ValueError("neighborhood_chars must be non-negative")

    source_records = list(records)
    output = [
        _reparse_one(record, extractor, contexts_by_article, neighborhood_chars)
        for record in source_records
    ]
    counters = Counter(
        "context_unavailable"
        if result.claim.parse_reason
        in {"ARTICLE_DATE_REQUIRED", "ARTICLE_CONTEXT_TARGET_NOT_FOUND"}
        else "reparse_errors"
        if result.claim.parse_reason == "CLAIM_CONTEXT_REPARSE_FAILED"
        else "reparsed_auto_ok"
        if result.claim.parse_status == "AUTO_OK"
        else "reparsed_hold"
        for result in output
    )
    return output, {
        "total_records": len(source_records),
        "reparsed_auto_ok": counters["reparsed_auto_ok"],
        "reparsed_hold": counters["reparsed_hold"],
        "reparse_errors": counters["reparse_errors"],
        "context_unavailable": counters["context_unavailable"],
    }


def _reparse_one(
    record: ClaimRegistryRecord,
    extractor: StructuredClaimExtractor,
    contexts_by_article: Mapping[str, Mapping[str, Any]],
    neighborhood_chars: int,
) -> ClaimRegistryRecord:
    source_status = record.claim.parse_status
    source_reason = record.claim.parse_reason
    if record.article_published_at is None:
        return _held_record(record, source_status, source_reason, "ARTICLE_DATE_REQUIRED")

    context = _limited_context(
        contexts_by_article.get(record.article_id),
        record.claim.source_sentence,
        neighborhood_chars,
    )
    if context is None:
        return _held_record(
            record,
            source_status,
            source_reason,
            "ARTICLE_CONTEXT_TARGET_NOT_FOUND",
        )

    try:
        parsed = parse_claim(
            record.claim.source_sentence,
            extractor,
            article_published_at=record.article_published_at,
            article_context=context,
        ).model_copy(
            update={
                "claim_id": record.claim.claim_id,
                "source_sentence": record.claim.source_sentence,
            }
        )
    except (OpenAIAuthenticationError, OpenAIConfigurationError):
        raise
    except Exception as error:
        return _held_record(
            record,
            source_status,
            source_reason,
            "CLAIM_CONTEXT_REPARSE_FAILED",
            error_type=type(error).__name__,
        )

    return record.model_copy(
        update={
            "claim": parsed,
            "source_ref": DERIVED_SOURCE_REF,
            "slot_enrichment": _audit(
                source_status,
                source_reason,
                parsed.parse_status,
                parsed.parse_reason,
            ),
        }
    )


def _limited_context(
    article: Mapping[str, Any] | None,
    target_sentence: str,
    neighborhood_chars: int,
) -> str | None:
    if article is None:
        return None
    title = article.get("title")
    body = article.get("body")
    if not isinstance(title, str) or not isinstance(body, str):
        return None
    target_index = body.find(target_sentence)
    if target_index < 0:
        return None
    start = max(0, target_index - neighborhood_chars)
    end = min(len(body), target_index + len(target_sentence) + neighborhood_chars)
    return f"제목: {title}\n대상 문장 주변부: {body[start:end]}"


def _held_record(
    record: ClaimRegistryRecord,
    source_status: str,
    source_reason: str | None,
    reason_code: str,
    *,
    error_type: str | None = None,
) -> ClaimRegistryRecord:
    held = record.claim.model_copy(
        update={"parse_status": "HOLD", "parse_reason": reason_code}
    )
    return record.model_copy(
        update={
            "claim": held,
            "source_ref": DERIVED_SOURCE_REF,
            "slot_enrichment": _audit(
                source_status,
                source_reason,
                "HOLD",
                reason_code,
                error_type=error_type,
            ),
        }
    )


def _audit(
    source_status: str,
    source_reason: str | None,
    result_status: str,
    reason_code: str | None,
    *,
    error_type: str | None = None,
) -> dict[str, object]:
    audit: dict[str, object] = {
        "stage": "CLAIM_CONTEXT_REPARSE",
        "source_parse_status": source_status,
        "source_parse_reason_detail": source_reason,
        "result_parse_status": result_status,
        "reason_code": reason_code,
    }
    if error_type is not None:
        audit["error_type"] = error_type
    return audit
