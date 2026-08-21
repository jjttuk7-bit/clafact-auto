from datetime import date

from core.claim_parser import parse_claim
from core.claim_time_resolver import resolve_relative_time
from core.kosis_catalog_adapter import normalize_item_metadata
from schemas.claim import ClaimSchema


def _claim(*, time: str, source_sentence: str) -> ClaimSchema:
    return ClaimSchema(
        claim_id="C", source_sentence=source_sentence, indicator="합계출산율",
        value=0.82, unit="명", time=time, frequency="분기", parse_status="AUTO_OK",
    )


def test_official_item_name_supplies_unit_when_kosis_omits_unit_field() -> None:
    structure = normalize_item_metadata(
        [
            {"TBL_ID": "DT_1ES3A01S", "OBJ_ID": "ITEM", "OBJ_NM": "항목", "ITM_ID": "T7", "ITM_NM": "고용률 (%)"},
            {"TBL_ID": "DT_1ES3A01S", "OBJ_ID": "C1", "OBJ_NM": "시군구별", "ITM_ID": "3743", "ITM_NM": "울릉군"},
        ],
        table_id="DT_1ES3A01S",
    )
    assert structure.item_codes == {"고용률 (%)": "T7"}
    assert structure.unit_names == ["%"]
    assert structure.item_units == {"T7": "%"}


def test_previous_same_quarter_uses_explicit_target_quarter_in_source() -> None:
    result = resolve_relative_time(
        _claim(time="전년 동분기", source_sentence="지난 1분기 합계출산율은 전년 동분기보다 0.02명 늘었다."),
        date(2025, 5, 28),
    )
    assert (result.time, result.frequency) == ("2024년 1분기", "분기")


class _Extractor:
    def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
        return ClaimSchema(
            claim_id="temporary", source_sentence=source_sentence, indicator="출생아 수",
            value=2500, unit="명", time="지난 8월", frequency="월",
            comparison=None, calculation=None, condition={"direction": "INCREASE"},
            parse_status="AUTO_OK",
        )


def test_one_year_ago_count_change_routes_operands_to_official_evidence() -> None:
    result = parse_claim(
        "지난 8월 출생아 수는 1년 전보다 2500명 늘었다.",
        _Extractor(), article_published_at=date(2025, 10, 29),
    )
    assert result.time == "2025년 8월"
    assert result.comparison == {
        "type": "YEAR_OVER_YEAR", "operand_source": "OFFICIAL_EVIDENCE"
    }
    assert result.calculation == "DIFFERENCE"
    assert result.parse_status == "AUTO_OK"
