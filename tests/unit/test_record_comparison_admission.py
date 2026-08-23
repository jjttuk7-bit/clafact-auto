from datetime import date

from core.admission_recovery_v3 import recover_registry_record_v3
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _UnusedExtractor:
    def extract(self, source_sentence: str, **kwargs):
        raise AssertionError("source-backed record split must not resample the Claim")


class _Official:
    def __init__(self) -> None:
        self.claims: list[ClaimSchema] = []

    def resolve(self, claim: ClaimSchema, *, article_date: date):
        self.claims.append(claim)
        return {"route_status": "AUTO"}


def test_record_children_reenter_the_same_official_service() -> None:
    claim = ClaimSchema(
        claim_id="parent",
        source_sentence="\ubc18\ub3c4\uccb4 \uc218\ucd9c\uc561\uc774 1419\uc5b5\ub2ec\ub7ec\ub85c \uc5ed\ub300 \ucd5c\ub300\uce58\ub97c \uae30\ub85d\ud588\ub2e4.",
        indicator="\ubc18\ub3c4\uccb4 \uc218\ucd9c\uc561",
        value=1419,
        unit="\uc5b5\ub2ec\ub7ec",
        time="2024\ub144",
        frequency="\ub144",
        calculation="DIRECT_VALUE",
        comparison={"type": "RECORD_HIGH"},
        parse_status="HOLD",
        parse_reason="RECORD_COMPARISON_REQUIRES_SEPARATE_CLAIM",
    )
    record = ClaimRegistryRecord(
        article_id="A1", sentence_id="1", claim=claim,
        article_published_at=date(2025, 1, 2), source_ref="test",
    )
    official = _Official()

    result = recover_registry_record_v3(
        record, extractor=_UnusedExtractor(), official_service=official
    )

    assert result.recovery_action == "RECORD_COMPARISON_SPLIT"
    assert [entry.admission_route for entry in result.entries] == [
        "KOSIS_PIPELINE_ELIGIBLE", "KOSIS_PIPELINE_ELIGIBLE",
    ]
    assert [claim.calculation for claim in official.claims] == [
        "DIRECT_VALUE", "RECORD_HIGH",
    ]
    assert all(entry.record.slot_enrichment["parent_claim_id"] == "parent" for entry in result.entries)
