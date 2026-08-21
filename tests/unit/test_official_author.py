from datetime import date

import pytest
from pydantic import ValidationError

from schemas.official_author import OfficialAuthorEvidenceSchema
from schemas.verdict import OfficialValueProvenanceSchema


DOCUMENT_HASH = "sha256:" + "a" * 64


def official_author_evidence(**updates: object) -> OfficialAuthorEvidenceSchema:
    data: dict[str, object] = {
        "source_url": "https://www.kostat.go.kr/board.es?bid=229&list_no=438232",
        "published_at": date(2025, 8, 28),
        "document_hash": DOCUMENT_HASH,
        "extraction_snippet": "2025년 벼 재배면적은 677,597ha이다.",
        "extraction_context": "2025년 재배면적조사 결과 표 1",
    }
    data.update(updates)
    return OfficialAuthorEvidenceSchema(**data)


def test_official_author_evidence_preserves_auditable_release_provenance() -> None:
    evidence = official_author_evidence()

    assert evidence.source_type == "OFFICIAL_AUTHOR_RELEASE"
    assert evidence.published_at == date(2025, 8, 28)
    assert evidence.document_hash == DOCUMENT_HASH
    assert "value" not in OfficialAuthorEvidenceSchema.model_fields


def test_official_author_evidence_rejects_uncontracted_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        official_author_evidence(generated_value=677597)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_url", "http://www.kostat.go.kr/board.es?bid=229"),
        ("source_url", "not-a-url"),
        ("document_hash", "sha256:abc123"),
        ("document_hash", "md5:" + "a" * 32),
    ],
)
def test_official_author_evidence_rejects_invalid_url_or_hash(
    field: str, value: str
) -> None:
    with pytest.raises(ValidationError):
        official_author_evidence(**{field: value})


def test_official_author_evidence_is_immutable() -> None:
    evidence = official_author_evidence()

    with pytest.raises(ValidationError, match="Instance is frozen"):
        evidence.source_url = "https://example.com/replaced"


def test_official_value_provenance_can_carry_official_author_evidence() -> None:
    evidence = official_author_evidence()

    provenance = OfficialValueProvenanceSchema(
        evidence_key="OFFICIAL_AUTHOR|2025|rice_area",
        source="OFFICIAL_AUTHOR_RELEASE",
        content_hash=DOCUMENT_HASH,
        official_author_evidence=evidence,
    )

    assert provenance.official_author_evidence == evidence