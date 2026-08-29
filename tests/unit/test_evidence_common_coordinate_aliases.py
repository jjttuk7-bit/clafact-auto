from core.evidence_resolver import resolve_evidence_cell
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def _claim(**updates: object) -> ClaimSchema:
    data: dict[str, object] = {
        "claim_id": "COMMON-COORDINATE",
        "source_sentence": "2025년 2월 취업자는 2817만9000명이었다.",
        "indicator": "취업자 수",
        "value": 28_179_000,
        "unit": "명",
        "time": "2025년 2월",
        "frequency": "월",
        "calculation": "DIRECT_VALUE",
        "parse_status": "AUTO_OK",
    }
    data.update(updates)
    return ClaimSchema(**data)


def test_population_repeating_indicator_does_not_create_a_fake_coordinate() -> None:
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_EMPLOYED_TOTAL",
        tbl_name="성별 경제활동인구 총괄",
        core_item_ids=["T30"],
        core_item_names=["취업자"],
        dimension_ids=["B"],
        dimension_names=["성별"],
        dimension_members={"B": ["계", "남자", "여자"]},
        dimension_member_codes={"B": {"계": "0", "남자": "2", "여자": "3"}},
        item_units={"T30": "천명"},
        unit_names=["천명"],
        frequency="월",
        binding_scope_terms=["15세 이상"],
        metadata_status="OFFICIAL_METADATA_READY",
    )

    cell = resolve_evidence_cell(
        _claim(population="15세 이상 전체 취업자"),
        candidate,
    )

    assert cell.status == "CONFIRMED"
    assert cell.dimension_members == {"B": "계"}


def test_trade_partner_dimension_selects_country_axis() -> None:
    candidate = KosisCandidateSchema(
        org_id="134",
        tbl_id="DT_EXPORT_BY_COUNTRY",
        tbl_name="국가별 수출액, 수입액",
        core_item_ids=["T1"],
        core_item_names=["수출액"],
        dimension_ids=["COUNTRY"],
        dimension_names=["국가별"],
        dimension_members={"COUNTRY": ["중국", "미국", "일본"]},
        dimension_member_codes={"COUNTRY": {"중국": "CN", "미국": "US", "일본": "JP"}},
        item_units={"T1": "천달러"},
        unit_names=["천달러"],
        frequency="년",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    cell = resolve_evidence_cell(
        _claim(
            source_sentence="2021년 대중 수출액은 1629억1300만달러였다.",
            indicator="수출액",
            value=162_913_000_000,
            unit="달러",
            time="2021년",
            frequency="년",
            dimension={"trade_partner": "중국"},
        ),
        candidate,
    )

    assert cell.status == "CONFIRMED"
    assert cell.dimension_members == {"COUNTRY": "중국"}
    assert cell.dimension_codes == {"COUNTRY": "CN"}


def test_youth_alias_selects_confirmed_domestic_employment_age_member() -> None:
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_YOUTH_UNEMPLOYMENT",
        tbl_name="성/연령별 실업률",
        core_item_ids=["T80"],
        core_item_names=["실업률"],
        dimension_ids=["B", "G"],
        dimension_names=["성별", "연령계층별"],
        dimension_members={"B": ["계", "남자", "여자"], "G": ["계", "15 - 29세", "30 - 39세"]},
        dimension_member_codes={"B": {"계": "0", "남자": "2", "여자": "3"}, "G": {"계": "00", "15 - 29세": "75", "30 - 39세": "30"}},
        item_units={"T80": "%"},
        unit_names=["%"],
        frequency="월",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    cell = resolve_evidence_cell(
        _claim(
            source_sentence="2024년 12월 청년 실업률은 5.9%였다.",
            indicator="실업률",
            value=5.9,
            unit="%",
            time="2024년 12월",
            dimension={"age_group": "청년"},
            population="청년",
        ),
        candidate,
    )

    assert cell.status == "CONFIRMED"
    assert cell.dimension_members == {"B": "계", "G": "15 - 29세"}
