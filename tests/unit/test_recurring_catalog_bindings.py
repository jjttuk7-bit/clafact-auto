from datetime import date

from core.catalog_binding import apply_catalog_binding
from core.kosis_fetcher import KosisValue
from core.official_evidence_service import OfficialEvidenceService
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def _claim(**updates):
    values = dict(
        claim_id="C1", source_sentence="2025년 6월 소비자물가지수는 116.31이었다.",
        indicator="소비자물가지수", value=116.31, unit="2020=100",
        time="2025년 6월", frequency="월", calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    values.update(updates)
    return ClaimSchema(**values)


def _concept(key: str):
    return StandardConceptSchema(
        concept_id="C1", canonical_name=key, standard_key=key,
        matched_alias=key, status="MATCHED",
    )


def _candidate(table: str, items: list[tuple[str, str]], **updates):
    values = dict(
        org_id="101", tbl_id=table, tbl_name=table,
        core_item_ids=[item_id for item_id, _ in items],
        core_item_names=[name for _, name in items],
        unit_names=["ha"], frequency="년", metadata_status="OFFICIAL_METADATA_READY",
    )
    values.update(updates)
    return KosisCandidateSchema(**values)


def test_rice_binding_selects_verified_table_and_exact_measurement_item():
    claim = _claim(
        source_sentence="올해 벼 재배 면적은 67만8000ha다.", indicator="벼 재배 면적",
        value=678000, unit="ha", time="2025년", frequency="연간",
        dimension={"작물": "벼"},
    )
    candidates = [
        _candidate("DT_1ZGA531", [("T1", "벼 재배면적")]),
        _candidate("DT_1ET0012", [("T03", "합계"), ("T06", "벼 계"), ("T09", "논벼")]),
    ]

    selected = apply_catalog_binding(claim, _concept("cultivated_area"), candidates)

    assert [item.tbl_id for item in selected] == ["DT_1ET0012"]
    assert selected[0].core_item_ids == ["T06"]
    assert selected[0].core_item_names == ["벼 계"]


def test_restaurant_cpi_binding_is_more_specific_than_aggregate_cpi():
    claim = _claim(
        source_sentence="지난달 외식 물가는 전년 대비 3.0% 올랐다.",
        indicator="외식 물가", value=3.0, unit="%", calculation="GROWTH_RATE",
    )
    candidates = [
        _candidate("DT_1J22003", [("T", "소비자물가지수")], unit_names=["2020=100"], frequency="월"),
        _candidate("DT_1J22112", [("T", "소비자물가지수")], unit_names=["2020=100"], frequency="월"),
    ]

    selected = apply_catalog_binding(claim, _concept("restaurant_consumer_price"), candidates)

    assert [item.tbl_id for item in selected] == ["DT_1J22112"]


def test_official_service_applies_binding_after_catalog_resolution():
    claim = _claim()
    concept = _concept("consumer_price")
    seen = []

    class Fetcher:
        def fetch(self, cell, *, article_date=None):
            return KosisValue(116.31, "SUCCESS", "hash", "API")

    service = OfficialEvidenceService(
        concept_mapper=lambda _claim: concept,
        catalog_resolver=lambda _claim, _concept: [
            _candidate("WRONG", [("T", "소비자물가지수")], unit_names=["2020=100"], frequency="월"),
            _candidate("DT_1J22003", [("T", "소비자물가지수")], unit_names=["2020=100"], frequency="월"),
        ],
        official_fetcher=Fetcher(),
        candidate_selector=lambda claim, concept, candidates: (
            seen.append([item.tbl_id for item in candidates])
            or apply_catalog_binding(claim, concept, candidates)
        ),
    )

    resolution = service.resolve(claim, article_date=date(2025, 7, 2))

    assert seen == [["WRONG", "DT_1J22003"]]
    assert [item.tbl_id for item in resolution.candidates] == ["DT_1J22003"]
