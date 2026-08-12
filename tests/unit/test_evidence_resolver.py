from core.evidence_resolver import resolve_evidence_cell
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def candidate(**updates: object) -> KosisCandidateSchema:
    data: dict[str, object] = {"org_id": "101", "tbl_id": "DT_EMP", "tbl_name": "고용", "core_item_ids": ["T1"], "core_item_names": ["고용률"], "dimension_ids": ["SIDO"], "dimension_names": ["시도별"], "dimension_members": {"SIDO": ["서울", "부산"]}, "dimension_member_codes": {"SIDO": {"서울": "11", "부산": "26"}}, "unit_names": ["%"], "frequency": "YEAR", "metadata_status": "READY"}
    data.update(updates)
    return KosisCandidateSchema(**data)


def claim(**updates: object) -> ClaimSchema:
    data: dict[str, object] = {"claim_id": "C1", "source_sentence": "2024년 서울 고용률은 70%였다.", "indicator": "고용률", "unit": "%", "time": "2024", "frequency": "YEAR", "region": "서울", "parse_status": "AUTO_OK"}
    data.update(updates)
    return ClaimSchema(**data)


def test_resolve_evidence_cell_confirms_full_coordinate() -> None:
    cell = resolve_evidence_cell(claim(), candidate())
    assert cell.status == "CONFIRMED"
    assert cell.itm_id == "T1"
    assert cell.obj_id == "SIDO"
    assert cell.member_code == "서울"
    assert cell.canonical_key == "ORG=101|TBL=DT_EMP|ITM=T1|OBJ=SIDO|MEMBER=서울|PRD_SE=YEAR|PRD_DE=2024"


def test_resolve_evidence_cell_holds_when_item_is_not_found() -> None:
    cell = resolve_evidence_cell(claim(indicator="실업률"), candidate())
    assert cell.status == "UNRESOLVED"


def test_resolve_evidence_cell_marks_multiple_items_ambiguous() -> None:
    cell = resolve_evidence_cell(candidate=candidate(core_item_ids=["A", "B"], core_item_names=["고용률", "고용률"]), claim=claim())
    assert cell.status == "AMBIGUOUS"


def test_resolve_evidence_cell_does_not_confirm_unresolved_required_member() -> None:
    cell = resolve_evidence_cell(
        claim(indicator="가구 수", region=None, unit="가구"),
        candidate(
            core_item_names=["가구수"],
            dimension_ids=["A"],
            dimension_names=["가구원수별"],
            dimension_members={"A": ["1인가구", "2인가구"]},
            unit_names=["천가구"],
        ),
    )
    assert cell.status == "UNRESOLVED"


def test_resolve_evidence_cell_confirms_singleton_dimension_without_claim_member() -> None:
    cell = resolve_evidence_cell(
        claim(region=None),
        candidate(
            dimension_ids=["TOTAL"],
            dimension_names=["전체"],
            dimension_members={"TOTAL": ["계"]},
            dimension_member_codes={"TOTAL": {"계": "00"}},
        ),
    )
    assert cell.status == "CONFIRMED"
    assert cell.obj_id == "TOTAL"
    assert cell.member_code == "계"



def test_resolve_evidence_cell_accepts_structured_dimension_slot() -> None:
    cell = resolve_evidence_cell(
        claim(region=None, dimension={"raw": "전체"}),
        candidate(
            dimension_ids=["TOTAL"],
            dimension_names=["전체"],
            dimension_members={"TOTAL": ["계"]},
            dimension_member_codes={"TOTAL": {"계": "00"}},
        ),
    )

    assert cell.status == "CONFIRMED"

def test_resolve_evidence_cell_holds_when_selected_dimension_has_no_api_code() -> None:
    cell = resolve_evidence_cell(
        claim(region=None),
        candidate(
            tbl_id="DT_NO_MEMBER_CODE",
            dimension_ids=["TOTAL"],
            dimension_names=["전체"],
            dimension_members={"TOTAL": ["계"]},
        ),
    )

    assert cell.status == "UNRESOLVED"

def test_resolve_evidence_cell_confirms_explicit_two_dimension_coordinate() -> None:
    cell = resolve_evidence_cell(
        claim(region="서울", population="15-29세"),
        candidate(
            dimension_ids=["C1", "C2"],
            dimension_names=["시도별", "연령별"],
            dimension_members={"C1": ["서울", "부산"], "C2": ["15-29세", "30-39세"]},
            dimension_member_codes={"C1": {"서울": "11", "부산": "26"}, "C2": {"15-29세": "15", "30-39세": "30"}},
        ),
    )
    assert cell.status == "CONFIRMED"
    assert cell.dimension_members == {"C1": "서울", "C2": "15-29세"}


def test_resolve_evidence_cell_does_not_use_registered_coordinate_fallback() -> None:
    cell = resolve_evidence_cell(
        claim(indicator="취업자 수", unit="명", time="2025년 3월", frequency="월", region=None),
        candidate(
            tbl_id="DT_1DA7028S", core_item_ids=["T30"], core_item_names=["취업자 수"],
            dimension_ids=["B", "J"], dimension_names=["성별", "종사상지위"],
            dimension_members={"B": ["계"], "J": ["계"]},
            dimension_member_codes={}, unit_names=["천명"], frequency="월",
        ),
    )

    assert cell.status == "UNRESOLVED"

def test_resolve_evidence_cell_confirms_official_metadata_total_coordinate() -> None:
    """A known official snapshot coordinate must resolve without guessing dimensions."""
    cell = resolve_evidence_cell(
        claim(
            indicator="취업자 수",
            unit="명",
            time="2025년 3월",
            frequency="월",
            region=None,
        ),
        candidate(
            tbl_id="DT_1DA7028S",
            tbl_name="경제활동인구조사",
            core_item_ids=["T30"],
            core_item_names=["취업자 수"],
            dimension_ids=["B", "J"],
            dimension_names=["성별", "종사상지위"],
            dimension_members={"B": ["계", "남자", "여자"], "J": ["계", "상용근로자"]},
            unit_names=["천명"],
            frequency="월",
        ),
    )

    assert cell.status == "UNRESOLVED"




def test_resolve_evidence_cell_uses_claim_frequency_for_multi_frequency_table() -> None:
    cell = resolve_evidence_cell(
        claim(indicator="취업자 수", unit="명", time="2025년 3월", frequency="월", region=None),
        candidate(
            tbl_id="DT_1DA7028S",
            core_item_ids=["T30"],
            core_item_names=["취업자 수"],
            dimension_ids=["B", "J"],
            dimension_members={"B": ["계", "남자"], "J": ["계", "상용근로자"]},
            unit_names=["천명"],
            frequency="월 | 분기 | 년",
        ),
    )

    assert cell.prd_se == "월"


def test_resolve_evidence_cell_uses_registered_cpi_year_on_year_coordinate() -> None:
    cell = resolve_evidence_cell(
        claim(
            indicator="소비자 물가",
            unit="%",
            time="2025년 10월",
            frequency="월",
            region=None,
        ),
        candidate(
            tbl_id="DT_1J22042",
            tbl_name="월별 소비자물가 등락률",
            core_item_ids=["T02", "T03", "T04"],
            core_item_names=["전월비", "전년동월비(%)", "전년누계비(%)"],
            dimension_ids=["I"],
            dimension_names=["지수종류"],
            dimension_members={"I": ["총지수", "생활물가지수"]},
            unit_names=["%"],
            frequency="월",
        ),
    )

    assert cell.status == "UNRESOLVED"


def test_resolve_evidence_cell_uses_base_indicator_for_growth_rate_claim() -> None:
    cell = resolve_evidence_cell(
        claim(
            indicator="소비자물가 상승률",
            unit="%",
            time="2025년 10월",
            frequency="월",
            region=None,
            comparison={"type": "YEAR_OVER_YEAR"},
            calculation="GROWTH_RATE",
        ),
        candidate(
            tbl_id="DT_CPI",
            core_item_ids=["T"],
            core_item_names=["소비자물가지수"],
            dimension_ids=["C1"],
            dimension_names=["지수종류"],
            dimension_members={"C1": ["총지수"]},
            dimension_member_codes={"C1": {"총지수": "T10"}},
            unit_names=["2020=100"],
            frequency="월",
        ),
    )

    assert cell.status == "CONFIRMED"
    assert cell.itm_id == "T"