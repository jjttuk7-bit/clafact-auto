from datetime import date

from core.admission_recovery_batch import run_admission_recovery_batch
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _Extractor:
    def extract(self, source_sentence: str, *, article_published_at: date | None = None) -> ClaimSchema:
        return ClaimSchema(
            claim_id="placeholder", source_sentence=source_sentence, indicator="고용률",
            value=61 if "61%" in source_sentence else 60, unit="%", time="2024년", frequency="년",
            calculation="DIRECT_VALUE", parse_status="AUTO_OK",
        )


class _Service:
    def resolve(self, claim: ClaimSchema, *, article_date: date) -> dict[str, object]:
        return {"resolved_claim_id": claim.claim_id, "date": article_date.isoformat()}


def test_recovery_batch_emits_one_auditable_row_per_derived_child() -> None:
    record = ClaimRegistryRecord(
        article_id="article-1", sentence_id="sentence-1", article_published_at=date(2025, 1, 1),
        source_ref="registry",
        claim=ClaimSchema(
            claim_id="parent", source_sentence="2023년 고용률은 60%였고 2024년 고용률은 61%였다.",
            parse_status="HOLD", parse_reason="MULTI_CLAIM_SPLIT_REQUIRED",
        ),
    )

    rows = run_admission_recovery_batch([record], extractor=_Extractor(), official_service=_Service())

    assert len(rows) == 2
    assert {row["parent_claim_id"] for row in rows} == {"parent"}
    assert {row["recovery_action"] for row in rows} == {"MULTI_CLAIM_SPLIT"}
    assert {row["admission_route"] for row in rows} == {"KOSIS_PIPELINE_ELIGIBLE"}
    assert all(row["official_resolution"] is not None for row in rows)
