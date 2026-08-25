"""Deterministic UI labels for the official source that supplied a value."""

from __future__ import annotations

from dataclasses import dataclass

from schemas.verdict import VerdictSchema


@dataclass(frozen=True, slots=True)
class OfficialSourcePresentation:
    value_label: str
    evidence_label: str
    evidence_count: int
    provenance_rows: list[dict[str, str]]


def build_official_source_presentation(
    verdict: VerdictSchema,
) -> OfficialSourcePresentation:
    """Describe the value source without conflating KOSIS and author documents."""
    document_provenance = [
        item
        for item in verdict.official_value_provenance
        if item.source == "OFFICIAL_DOCUMENT"
    ]
    if verdict.evidence_cells or (
        verdict.evidence_values
        and not document_provenance
    ):
        value_label = "KOSIS 공식값"
        evidence_label = "KOSIS 공식 근거"
    elif document_provenance:
        value_label = "공식 작성기관 문서값"
        evidence_label = "공식 작성기관 문서 근거"
    else:
        value_label = "공식값"
        evidence_label = "공식 근거"

    rows = [
        {
            "출처 유형": "공식 작성기관 문서",
            "근거 식별자": item.evidence_key,
            "출처 URL": item.source_url,
            "조회 시각": item.retrieved_at,
            "응답 해시": item.content_hash,
        }
        for item in document_provenance
    ]
    return OfficialSourcePresentation(
        value_label=value_label,
        evidence_label=evidence_label,
        evidence_count=max(
            len(verdict.evidence_cells),
            len(verdict.official_value_provenance),
        ),
        provenance_rows=rows,
    )
