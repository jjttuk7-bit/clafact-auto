from __future__ import annotations

from core.official_release_table import OfficialReleaseTable, resolve_direct_value
from schemas.claim import ClaimSchema


def _claim(**updates) -> ClaimSchema:
    claim = ClaimSchema(
        claim_id="c1",
        source_sentence="2025년 5월 쉬었음 인구는 239만명이다.",
        indicator="쉬었음 인구",
        value=2_390_000,
        unit="명",
        time="2025-05",
        frequency="M",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    return claim.model_copy(update=updates)


def _table() -> OfficialReleaseTable:
    return OfficialReleaseTable((
        ("< 연령계층별 쉬었음 인구 >",),
        ("(단위: 천명, %, 전년동월대비)",),
        ("", "2024.", "5", "", "2025.", "4", "", "2025.", "5", ""),
        ("증감", "증감", "증감", "증감률"),
        ("< 전 체 >", "2,334", "100.0", "87", "2,434", "100.0", "45", "2,390", "100.0", "56", "2.4"),
        ("20~29세", "366", "15.7", "9", "392", "16.1", "35", "378", "15.8", "12", "3.3"),
    ))


def test_resolves_total_row_at_exact_month_and_normalizes_thousand_persons() -> None:
    assert resolve_direct_value(_claim(), [_table()], reference_period="2025-05") == 2_390_000


def test_resolves_explicit_age_row_instead_of_total() -> None:
    claim = _claim(
        source_sentence="2025년 5월 20대 쉬었음 인구는 37만8000명이다.",
        value=378_000,
        population="20대",
    )
    assert resolve_direct_value(claim, [_table()], reference_period="2025-05") == 378_000


def test_fails_closed_for_wrong_period_or_ambiguous_different_values() -> None:
    other = OfficialReleaseTable((
        ("< 쉬었음 인구 >",), ("단위: 천명",),
        ("", "2025.", "5"), ("<전체>", "2,400"),
    ))
    assert resolve_direct_value(_claim(), [_table()], reference_period="2025-06") is None
    assert resolve_direct_value(_claim(), [_table(), other], reference_period="2025-05") is None

def test_resolves_official_thousand_people_in_article_ten_thousand_people_unit() -> None:
    claim = _claim(unit="만 명", value=239.0)
    assert resolve_direct_value(claim, [_table()], reference_period="2025-05") == 239.0

def test_fails_closed_when_claim_unit_family_is_not_recognized() -> None:
    claim = _claim(unit="상자", value=2_390.0)
    assert resolve_direct_value(claim, [_table()], reference_period="2025-05") is None
