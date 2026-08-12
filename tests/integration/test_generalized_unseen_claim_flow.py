from datetime import date

from core.catalog_discovery import discover_catalog_candidates
from core.catalog_metadata_refresh import refresh_item_metadata
from core.claim_parser import parse_claim
from core.dynamic_kosis_verifier import verify_claim_against_kosis
from core.kosis_fetcher import KosisValue
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


class _Extractor:
    def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
        return ClaimSchema(
            claim_id="provider-id",
            source_sentence=source_sentence,
            indicator="수출액",
            value=31,
            unit="%",
            time="올해 1분기",
            frequency="분기",
            dimension={"상품": "중고차"},
            comparison={"type": "YEAR_OVER_YEAR"},
            calculation="GROWTH_RATE",
            condition={"direction": "INCREASE"},
            parse_status="AUTO_OK",
        )


class _Search:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, query: str) -> list[KosisCandidateSchema]:
        self.queries.append(query)
        if query != "중고차 수출액":
            return []
        return [
            KosisCandidateSchema(
                org_id="360",
                tbl_id="DT_ITEM_EXPORT",
                tbl_name="품목별 수출액",
                metadata_status="LIVE_SEARCH_UNRESOLVED",
            )
        ]


class _Fetcher:
    def fetch(self, cell, *, article_date=None) -> KosisValue:
        return KosisValue(
            {"2024-Q1": 131.0, "2023-Q1": 100.0}[cell.prd_de],
            "SUCCESS",
            "integration",
            "API",
        )


def test_unseen_dimension_claim_reaches_deterministic_auto_without_profile() -> None:
    article_date = date(2024, 4, 30)
    claim = parse_claim(
        "올해 1분기 중고차 수출액은 지난해보다 31% 증가했다.",
        _Extractor(),
        article_published_at=article_date,
    )
    concept = StandardConceptSchema(
        concept_id="C000003",
        canonical_name="수출액",
        standard_key="export_value",
        kosis_search_terms=["수출입총괄"],
        status="MATCHED",
    )
    search = _Search()
    candidates = discover_catalog_candidates(claim, concept, [], search)

    def metadata(api_key, org_id, table_id, *, meta_type, retries, timeout_seconds):
        if meta_type == "PRD":
            return [{"PRD_SE": "분기", "STRT_PRD_DE": "2020 1/4", "END_PRD_DE": "2024 4/4"}]
        return [
            {"TBL_ID": table_id, "OBJ_ID": "ITEM", "OBJ_NM": "항목", "ITM_ID": "T1", "ITM_NM": "수출액", "UNIT_NM": "천달러"},
            {"TBL_ID": table_id, "OBJ_ID": "C1", "OBJ_NM": "상품", "ITM_ID": "USED_CAR", "ITM_NM": "중고차"},
        ]

    hydrated = refresh_item_metadata(
        candidates,
        "key",
        metadata_fetcher=metadata,
        max_candidates=1,
        retries=1,
        timeout_seconds=1,
    )
    verdict = verify_claim_against_kosis(
        claim,
        concept,
        hydrated,
        article_date=article_date,
        official_fetcher=_Fetcher(),
    )

    assert claim.time == "2024년 1분기"
    assert search.queries[0] == "중고차 수출액"
    assert [cell.prd_de for cell in verdict.evidence_cells] == ["2024-Q1", "2023-Q1"]
    assert verdict.route_status == "AUTO"
    assert verdict.verdict == "MATCH"
