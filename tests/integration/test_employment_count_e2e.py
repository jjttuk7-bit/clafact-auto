from datetime import date
from pathlib import Path

from core.catalog_discovery import discover_catalog_candidates
from core.catalog_metadata_refresh import refresh_item_metadata
from core.data_loader import load_standard_concepts
from core.dynamic_kosis_verifier import verify_claim_against_kosis
from core.kosis_fetcher import OfficialValueFetcher
from core.kosis_publication import PublicationEvidence
from core.semantic_normalizer import normalize_concept
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _EmploymentCatalogSearch:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, query: str) -> list[KosisCandidateSchema]:
        self.queries.append(query)
        if "취업자" not in query:
            return []
        return [
            KosisCandidateSchema(
                org_id="101",
                tbl_id="DT_1DA7001S",
                tbl_name="경제활동인구조사",
                metadata_status="LIVE_SEARCH_UNRESOLVED",
            )
        ]


class _OfficialPublicationLookup:
    def fetch(self, org_id: str, table_id: str, *, period: str) -> PublicationEvidence:
        assert (org_id, table_id, period) == ("101", "DT_1DA7001S", "2024-12")
        return PublicationEvidence(
            status="VERIFIED",
            published_at=date(2025, 1, 15),
            source_url="https://mods.go.kr/board.es?act=view&bid=210&list_no=434801",
            retrieved_at="2025-01-15T00:00:00Z",
            content_hash="a" * 64,
        )


def test_employment_count_claim_reaches_auto_through_dynamic_kosis_e2e() -> None:
    claim = ClaimSchema(
        claim_id="employment-202412",
        source_sentence="2024년 12월 취업자 수는 2804만1000명이었다.",
        indicator="취업자 수",
        value=28_041_000,
        unit="명",
        time="2024년 12월",
        frequency="MONTHLY",
        region="한국",
        parse_status="AUTO_OK",
    )
    concept = normalize_concept(
        claim,
        load_standard_concepts(
            PROJECT_ROOT / "data/semantic_standard/concept_seed_v1.json"
        ),
    )
    assert concept.concept_id == "C000008"

    search = _EmploymentCatalogSearch()
    candidates = discover_catalog_candidates(claim, concept, [], search)

    def metadata(_api_key, _org_id, table_id, *, meta_type, retries, timeout_seconds):
        assert table_id == "DT_1DA7001S"
        if meta_type == "PRD":
            return [{"PRD_SE": "월", "STRT_PRD_DE": "2000.01", "END_PRD_DE": "2024.12"}]
        return [
            {"TBL_ID": table_id, "OBJ_ID": "ITEM", "OBJ_NM": "항목", "ITM_ID": "T30", "ITM_NM": "취업자 수", "UNIT_NM": "천명"},
            {"TBL_ID": table_id, "OBJ_ID": "B", "OBJ_NM": "성별", "ITM_ID": "0", "ITM_NM": "계"},
        ]

    hydrated = refresh_item_metadata(
        candidates,
        "key",
        metadata_fetcher=metadata,
        max_candidates=1,
        retries=1,
        timeout_seconds=1,
    )

    def api_lookup(cell):
        assert cell.tbl_id == "DT_1DA7001S"
        assert cell.itm_id == "T30"
        assert cell.dimension_codes == {"B": "0"}
        assert cell.prd_de == "2024-12"
        return [{"PRD_DE": "202412", "ITM_ID": "T30", "B": "0", "DT": "28041.1"}]

    verdict = verify_claim_against_kosis(
        claim,
        concept,
        hydrated,
        article_date=date(2025, 1, 16),
        official_fetcher=OfficialValueFetcher(
            [],
            api_lookup=api_lookup,
            prefer_api=True,
            publication_lookup=_OfficialPublicationLookup(),
            require_verified_release_metadata=True,
        ),
    )

    assert search.queries == ["취업자 수"]
    assert [(cell.tbl_id, cell.itm_id, cell.prd_de, cell.dimension_codes) for cell in verdict.evidence_cells] == [
        ("DT_1DA7001S", "T30", "2024-12", {"B": "0"}),
    ]
    assert verdict.evidence_values == [28_041.1]
    assert verdict.calculated_value == 28_041_100
    assert verdict.route_status == "AUTO"
    assert verdict.verdict == "MATCH"
    assert verdict.official_value_provenance[0].publication is not None
    assert verdict.official_value_provenance[0].publication.published_at == date(2025, 1, 15)