from core.evidence_resolver import resolve_evidence_cell
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def test_indicator_selects_unique_measure_member_on_custom_axis() -> None:
    claim = ClaimSchema(
        claim_id="trade-balance",
        source_sentence="2025년 1월 무역수지는 18억9000만달러 적자였다.",
        indicator="무역수지",
        value=-1_890_000_000,
        unit="달러",
        time="2025년 1월",
        frequency="월",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    candidate = KosisCandidateSchema(
        org_id="301",
        tbl_id="DT_TRADE_BALANCE",
        tbl_name="지식재산권 무역수지(유형별)",
        core_item_ids=["T1"],
        core_item_names=["지식재산권 무역수지(유형별)"],
        dimension_ids=["ACCOUNT", "KIND"],
        dimension_names=["계정항목별", "구분코드별"],
        dimension_members={
            "ACCOUNT": ["합계", "산업재산권"],
            "KIND": ["수지", "수출", "수입"],
        },
        dimension_member_codes={
            "ACCOUNT": {"합계": "00", "산업재산권": "10"},
            "KIND": {"수지": "B", "수출": "E", "수입": "I"},
        },
        item_units={"T1": "백만달러"},
        unit_names=["백만달러"],
        frequency="월",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    cell = resolve_evidence_cell(claim, candidate)

    assert cell.status == "CONFIRMED"
    assert cell.dimension_members == {"ACCOUNT": "합계", "KIND": "수지"}
    assert cell.dimension_codes == {"ACCOUNT": "00", "KIND": "B"}


def test_indicator_does_not_guess_when_multiple_axis_members_match() -> None:
    claim = ClaimSchema(
        claim_id="exports",
        source_sentence="2025년 1월 수출은 10억달러였다.",
        indicator="상품수출액",
        value=1_000_000_000,
        unit="달러",
        time="2025년 1월",
        frequency="월",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    candidate = KosisCandidateSchema(
        org_id="301",
        tbl_id="DT_AMBIGUOUS_EXPORT",
        tbl_name="수출 통계",
        core_item_ids=["T1"],
        core_item_names=["수출 통계"],
        dimension_ids=["KIND"],
        dimension_names=["구분코드별"],
        dimension_members={"KIND": ["수출", "재수출"]},
        dimension_member_codes={"KIND": {"수출": "E", "재수출": "RE"}},
        item_units={"T1": "백만달러"},
        unit_names=["백만달러"],
        frequency="월",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    cell = resolve_evidence_cell(claim, candidate)

    assert cell.status == "UNRESOLVED"
