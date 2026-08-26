from datetime import date

from core.official_evidence_service import CatalogResolution, OfficialEvidenceService
from core.semantic_indicator_alignment import align_claim_indicator_to_concept
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema
from schemas.verdict import VerdictSchema


def _claim(indicator="총인구", source="행정안전부 집계 결과 출생자 수는 24만2334명이었다."):
    return ClaimSchema(
        claim_id="claim_birth", source_sentence=source, indicator=indicator,
        value=242334, unit="명", time="2024", frequency="년",
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )


def _concept(alias="출생자 수"):
    return StandardConceptSchema(
        concept_id="C000019", canonical_name="출생아 수", standard_key="birth_count",
        matched_alias=alias, status="MATCHED",
    )


def test_aligns_only_when_matched_alias_is_in_source_and_parsed_indicator_is_not():
    aligned = align_claim_indicator_to_concept(_claim(), _concept())
    assert aligned.indicator == "출생아 수"
    unchanged = align_claim_indicator_to_concept(
        _claim(indicator="총인구", source="2024년 총인구는 5천만명이었다."), _concept()
    )
    assert unchanged.indicator == "총인구"
    ambiguous = align_claim_indicator_to_concept(
        _claim(source="출생자 수는 10명이고 총인구는 20명이었다."), _concept()
    )
    assert ambiguous.indicator == "총인구"


def test_official_service_uses_source_grounded_aligned_indicator_for_all_stages():
    observed = []
    class Fetcher:
        def fetch(self, _cell, *, article_date):
            raise AssertionError("no candidate means fetch must not run")
    service = OfficialEvidenceService(
        concept_mapper=lambda _claim: _concept(),
        catalog_resolver=lambda claim, _concept: observed.append(("catalog", claim.indicator)) or CatalogResolution([]),
        candidate_selector=lambda claim, _concept, candidates: observed.append(("selector", claim.indicator)) or candidates,
        official_fetcher=Fetcher(),
    )
    result = service.resolve(_claim(), article_date=date(2025, 1, 2))
    assert observed == [("catalog", "출생아 수"), ("selector", "출생아 수")]
    assert result.verdict.route_status == "HOLD"
