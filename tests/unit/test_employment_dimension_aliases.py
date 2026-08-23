import pytest

from core.evidence_resolver import resolve_evidence_cell
from core.hard_guard import apply_hard_guard
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def _claim(**updates: object) -> ClaimSchema:
    payload: dict[str, object] = {
        "claim_id": "EMPLOYMENT-ALIAS",
        "source_sentence": "2025년 1분기 고졸 실업률은 5.5%였다.",
        "indicator": "실업률", "value": 5.5, "unit": "%",
        "time": "2025년 1분기", "frequency": "분기", "region": "전국",
        "calculation": "DIRECT_VALUE", "parse_status": "AUTO_OK",
    }
    payload.update(updates)
    return ClaimSchema(**payload)


def _candidate(**updates: object) -> KosisCandidateSchema:
    payload: dict[str, object] = {
        "org_id": "101", "tbl_id": "DT_1DA7103S", "tbl_name": "성/교육정도별 실업률",
        "core_item_ids": ["T80"], "core_item_names": ["실업률"],
        "dimension_ids": ["B", "H1"], "dimension_names": ["성별", "교육정도별"],
        "dimension_members": {"B": ["계", "남자", "여자"], "H1": ["계", "고졸", "전문대졸", "대졸이상"]},
        "dimension_member_codes": {"B": {"계": "0", "남자": "2", "여자": "3"}, "H1": {"계": "00", "고졸": "30", "전문대졸": "401", "대졸이상": "402"}},
        "unit_names": ["%"], "item_units": {"T80": "%"}, "frequency": "월|분기|년",
        "start_period": "2000 3/4", "end_period": "2026 2/4", "metadata_status": "OFFICIAL_METADATA_READY",
    }
    payload.update(updates)
    return KosisCandidateSchema(**payload)


@pytest.mark.parametrize(("phrase", "member", "code"), [
    ("고등학교 졸업", "고졸", "30"),
    ("4년제 대학 이상 졸업자", "대졸이상", "402"),
])
def test_education_phrase_maps_to_official_member(phrase: str, member: str, code: str) -> None:
    claim = _claim(population=phrase, dimension={"학력": phrase})
    candidate = _candidate()
    assert apply_hard_guard(claim, candidate).passed is True
    cell = resolve_evidence_cell(claim, candidate)
    assert cell.status == "CONFIRMED"
    assert cell.dimension_members == {"B": "계", "H1": member}
    assert cell.dimension_codes == {"B": "0", "H1": code}


def test_decade_phrase_maps_to_official_age_range() -> None:
    claim = _claim(source_sentence="2025년 3월 40대 취업자는 4만9000명 줄었다.", indicator="취업자 수", value=-49_000, unit="명", time="2025년 3월", frequency="월", population="취업자", dimension={"age": "40대"})
    candidate = _candidate(tbl_id="DT_1DA7024S", tbl_name="성/연령별 취업자", core_item_ids=["T30"], core_item_names=["취업자"], dimension_ids=["B", "G"], dimension_names=["성별", "연령계층별"], dimension_members={"B": ["계", "남자", "여자"], "G": ["계", "40 - 49세"]}, dimension_member_codes={"B": {"계": "0", "남자": "2", "여자": "3"}, "G": {"계": "00", "40 - 49세": "40"}}, unit_names=["천명"], item_units={"T30": "천명"})
    assert apply_hard_guard(claim, candidate).passed is True
    cell = resolve_evidence_cell(claim, candidate)
    assert cell.status == "CONFIRMED"
    assert cell.dimension_members["G"] == "40 - 49세"
    assert cell.dimension_codes["G"] == "40"


def test_korean_age_group_key_maps_decade_to_official_age_range() -> None:
    claim = _claim(source_sentence="2025년 5월 30대 취업자는 13만2000명 늘었다.", indicator="취업자 수", value=132_000, unit="명", time="2025년 5월", frequency="월", population="취업자", dimension={"연령대": "30대"})
    candidate = _candidate(tbl_id="DT_1DA7002S", tbl_name="연령별 경제활동인구 총괄", core_item_ids=["T30"], core_item_names=["취업자"], dimension_ids=["G"], dimension_names=["연령계층별"], dimension_members={"G": ["15세 이상 전체", "30 - 39세"]}, dimension_member_codes={"G": {"15세 이상 전체": "00", "30 - 39세": "30"}}, unit_names=["천명"], item_units={"T30": "천명"})

    assert apply_hard_guard(claim, candidate).passed is True
    cell = resolve_evidence_cell(claim, candidate)

    assert cell.status == "CONFIRMED"
    assert cell.dimension_members == {"G": "30 - 39세"}
    assert cell.dimension_codes == {"G": "30"}


def test_temporary_worker_definition_maps_to_one_official_status_coordinate() -> None:
    claim = _claim(source_sentence="임시직(1개월 이상 1년 미만) 취업자가 1만9000명 감소했다.", indicator="취업자 수", value=-19_000, unit="명", time="2024년 12월", frequency="월", population="임금 근로자", dimension={"고용계약기간": "1개월 이상 1년 미만", "고용형태": "임시직"})
    candidate = _candidate(tbl_id="DT_1DA7010S", tbl_name="종사상지위별 취업자", core_item_ids=["T30"], core_item_names=["취업자"], dimension_ids=["J"], dimension_names=["종사상지위별"], dimension_members={"J": ["계", "임금근로자", "-상용근로자", "-임시근로자", "-일용근로자"]}, dimension_member_codes={"J": {"계": "00", "임금근로자": "30", "-상용근로자": "41", "-임시근로자": "51", "-일용근로자": "52"}}, unit_names=["천명"], item_units={"T30": "천명"})
    assert apply_hard_guard(claim, candidate).passed is True
    cell = resolve_evidence_cell(claim, candidate)
    assert cell.status == "CONFIRMED"
    assert cell.dimension_members == {"J": "-임시근로자"}
    assert cell.dimension_codes == {"J": "51"}
