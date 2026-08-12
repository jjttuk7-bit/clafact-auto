from core.semantic_matcher import semantic_match
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def claim(**updates: object) -> ClaimSchema:
    data: dict[str, object] = {"claim_id": "C1", "source_sentence": "2024년 고용률은 70%였다.", "indicator": "고용률", "unit": "%", "time": "2024", "frequency": "YEAR", "region": "전국", "parse_status": "AUTO_OK"}
    data.update(updates)
    return ClaimSchema(**data)


def candidate(tbl_id: str, name: str, **updates: object) -> KosisCandidateSchema:
    data: dict[str, object] = {"org_id": "101", "tbl_id": tbl_id, "tbl_name": name, "core_item_names": [name], "unit_names": ["%"], "frequency": "YEAR", "start_period": "2020", "end_period": "2024", "metadata_status": "READY"}
    data.update(updates)
    return KosisCandidateSchema(**data)


def test_semantic_match_auto_routes_clear_high_score_winner() -> None:
    result = semantic_match(claim(), [candidate("A", "고용률"), candidate("B", "소비자물가")])
    assert result[0].candidate_tbl_id == "A"
    assert result[0].route_status == "AUTO"


def test_semantic_match_holds_when_top_two_margin_is_low() -> None:
    result = semantic_match(claim(), [candidate("A", "고용률"), candidate("B", "고용률")], min_margin=0.1)
    assert result[0].route_status == "HOLD"
    assert result[0].reason_code == "AMBIGUOUS_MARGIN"
    assert result[0].top1_top2_margin == 0.0


def test_semantic_match_excludes_hard_guard_rejects_before_scoring() -> None:
    result = semantic_match(claim(unit="명"), [candidate("A", "고용률")])
    assert result == []


def test_semantic_match_holds_below_score_threshold() -> None:
    result = semantic_match(claim(), [candidate("A", "고용륩")], minimum_score=0.99)
    assert result[0].route_status == "HOLD"
    assert result[0].reason_code == "LOW_SEMANTIC_SCORE"


def test_semantic_match_rewards_convertible_units() -> None:
    result = semantic_match(
        claim(indicator="가구수", unit="가구"),
        [candidate("A", "가구수", unit_names=["천가구"])],
    )
    assert result[0].semantic_score == 1.0


def test_semantic_match_normalizes_korean_whitespace_before_scoring() -> None:
    result = semantic_match(
        claim(indicator="소비자 물가", unit="%", time="2025년 10월", frequency="월"),
        [candidate("DT_1J22042", "월별 소비자물가 등락률", frequency="월", start_period="2020", end_period="2025")],
    )

    assert result[0].route_status == "AUTO"


def test_semantic_match_prefers_total_table_for_dimensionless_national_aggregate() -> None:
    export_claim = claim(
        source_sentence="지난해 수출은 전년 대비 8.2% 증가했다.", indicator="수출액",
        unit="%", time="2024", frequency="년", region=None,
        calculation="GROWTH_RATE", comparison={"type": "YEAR_OVER_YEAR"},
    )
    results = semantic_match(export_claim, [
        candidate("DT_COSMETICS", "화장품 수입 및 수출액 현황", core_item_names=["수출액"], unit_names=["천불"], frequency="년"),
        candidate("DT_TOTAL_TRADE", "수출입총괄", core_item_names=["수출금액"], unit_names=["천불"], frequency="월|년"),
    ])

    assert results[0].candidate_tbl_id == "DT_TOTAL_TRADE"
    assert results[0].route_status == "AUTO"