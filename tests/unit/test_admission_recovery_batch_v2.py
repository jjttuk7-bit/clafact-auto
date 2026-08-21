from datetime import date

from core.admission_recovery_batch_v2 import run_admission_recovery_batch_v2
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _Extractor:
    def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
        return ClaimSchema(
            claim_id="temporary",
            source_sentence=source_sentence,
            indicator="사망자 수",
            value=132600,
            unit="명",
            time="2025년",
            frequency="년",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        )


class _Service:
    def resolve(self, claim, *, article_date):
        return {"route_status": "AUTO", "claim_value": claim.value}


def test_v2_batch_serializes_slot_reparse_as_a_terminal_child() -> None:
    source = "반면 80대 사망자는 13만2600명으로 전년 대비 400명 줄었다."
    record = ClaimRegistryRecord(
        article_id="A1",
        sentence_id="1",
        article_published_at=date(2025, 8, 1),
        source_ref="registry",
        claim=ClaimSchema(
            claim_id="bad",
            source_sentence=source,
            indicator="사망자 수",
            value=80,
            unit="대",
            time="2025",
            frequency="Y",
            calculation="DIFFERENCE",
            comparison={"type": "YEAR_OVER_YEAR"},
            parse_status="AUTO_OK",
        ),
    )

    rows = run_admission_recovery_batch_v2(
        [record], extractor=_Extractor(), official_service=_Service()
    )

    assert rows[0]["recovery_action"] == "SLOT_REPARSE"
    assert rows[0]["official_resolution"]["route_status"] == "AUTO"
