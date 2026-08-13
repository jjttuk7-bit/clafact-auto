from datetime import date
from pathlib import Path

import pytest

from core.catalog_discovery import build_catalog_discovery_queries, discover_catalog_candidates
from core.catalog_metadata_refresh import refresh_item_metadata
from core.data_loader import load_standard_concepts
from core.dynamic_kosis_verifier import verify_claim_against_kosis
from core.kosis_fetcher import OfficialValueFetcher
from core.kosis_metadata_repository import KosisMetadataRepository
from core.semantic_normalizer import normalize_concept
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _CpiCatalogSearch:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, query: str) -> list[KosisCandidateSchema]:
        self.queries.append(query)
        if "배추" not in query or "소비자물가지수" not in query:
            return []
        return [
            KosisCandidateSchema(
                org_id="101",
                tbl_id="DT_1J22112",
                tbl_name="품목별 소비자물가지수",
                metadata_status="LIVE_SEARCH_UNRESOLVED",
            )
        ]


def test_cabbage_price_claim_reaches_auto_through_contextual_dynamic_kosis_pipeline() -> None:
    claim = ClaimSchema(
        claim_id="claim_eeb4134b7158445d",
        source_sentence="2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다.",
        indicator="물가",
        value=-34.5,
        unit="%",
        time="2025년 10월",
        frequency="MONTHLY",
        dimension={"product": "배추"},
        comparison={"type": "YEAR_OVER_YEAR", "reference_period": "전년 동월"},
        calculation="GROWTH_RATE",
        condition={"direction": "DECREASE"},
        parse_status="AUTO_OK",
    )
    concept = normalize_concept(
        claim,
        load_standard_concepts(
            PROJECT_ROOT / "data/semantic_standard/concept_seed_v1.json"
        ),
    )

    assert concept.concept_id == "CPI_DETAIL:A02A01701"
    assert concept.canonical_name == "배추 소비자물가지수"
    assert concept.kosis_search_terms == [
        "배추 소비자물가지수",
        "품목별 소비자물가지수 배추",
    ]
    queries = build_catalog_discovery_queries(claim, concept)
    assert "배추 소비자물가지수" in queries
    assert "품목별 소비자물가지수 배추" in queries

    search = _CpiCatalogSearch()
    candidates = discover_catalog_candidates(claim, concept, [], search)
    repository = KosisMetadataRepository.from_manifests([
        PROJECT_ROOT / "data/kosis_snapshots/cpi_detail_metadata_v1_manifest.json"
    ])
    hydrated = refresh_item_metadata(
        candidates,
        None,
        metadata_fetcher=repository,
        allow_without_api_key=True,
        max_candidates=1,
    )
    verdict = verify_claim_against_kosis(
        claim,
        concept,
        hydrated,
        article_date=date(2025, 11, 4),
        official_fetcher=OfficialValueFetcher([
            PROJECT_ROOT / "data/kosis_snapshots/official_cpi_detail_current_axes_v1.json"
        ]),
    )

    assert [cell.prd_de for cell in verdict.evidence_cells] == ["2025-10", "2024-10"]
    assert all(cell.dimension_codes == {"C": "T10", "I": "A02A01701"} for cell in verdict.evidence_cells)
    assert verdict.evidence_values == [136.62, 208.57]
    assert verdict.calculated_value == pytest.approx(-34.49681162199741)
    assert [item.source for item in verdict.official_value_provenance] == ["SNAPSHOT", "SNAPSHOT"]
    assert all(len(item.content_hash) == 64 for item in verdict.official_value_provenance)
    assert [item.evidence_key for item in verdict.official_value_provenance] == [
        cell.canonical_key for cell in verdict.evidence_cells
    ]
    assert verdict.route_status == "AUTO"
    assert verdict.verdict == "MATCH"
