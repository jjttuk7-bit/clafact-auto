from datetime import date

from core.direct_value_indicator_refinement_scope import build_indicator_refinement_scope
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _row(claim_id: str, source: str, indicator: str, value: str, unit: str) -> dict[str, str]:
    return {
        "자식Claim번호": claim_id, "원본부모Claim번호": claim_id,
        "원문": source, "지표": indicator, "기사값": value, "단위": unit,
        "기준시점": "2025", "주기": "Y", "계산방식": "DIRECT_VALUE",
        "원문근거표현": f"{value}{unit}", "복구48최종사유": "INDICATOR_REFINEMENT_REQUIRED",
        "사용집합": "RULE_DISCOVERY",
    }


def _record(row: dict[str, str]) -> ClaimRegistryRecord:
    expression = row["원문근거표현"]
    source = row["원문"]
    return ClaimRegistryRecord(
        article_id=row["자식Claim번호"], sentence_id="1",
        article_published_at=date(2025, 6, 1), source_ref="fixture",
        claim=ClaimSchema(
            claim_id=row["자식Claim번호"], source_sentence=source,
            indicator=row["지표"], value=float(row["기사값"]), unit=row["단위"],
            time="2025", frequency="Y", calculation="DIRECT_VALUE", parse_status="AUTO_OK",
        ),
        slot_enrichment={
            "target_link_status": "SOURCE_GROUNDED",
            "target_numeric_expression": expression,
            "target_numeric_start": source.index(expression),
            "target_numeric_end": source.index(expression) + len(expression),
            "target_numeric_role": "대상값",
            "indicator_unit_status": "INDICATOR_REFINEMENT_REQUIRED",
        },
    )


def test_scope_runs_only_refined_direct_claims_and_audits_moves() -> None:
    rows = [
        _row("C1", "순수출 성장 기여도는 0.3%p로 집계됐다.", "수출액", "0.3", "%p"),
        _row("C2", "전체 인구의 20%가 65세 이상이다.", "총인구", "20", "%"),
        _row("C3", "수입차에 25% 관세를 매겼다.", "수입액", "25", "%"),
    ]
    scope = build_indicator_refinement_scope(
        rows, [_record(row) for row in rows], expected_scope_count=3,
        expected_run_count=1,
    )
    assert scope.decision_counts == {
        "EXCLUDE_POLICY_RATE": 1,
        "KEEP_DIRECT_RECOVERED": 1,
        "MOVE_SHARE": 1,
    }
    assert len(scope.records) == 1
    assert scope.records[0].claim.indicator == "순수출 성장 기여도"
    assert scope.records[0].slot_enrichment["indicator_unit_status"] == "COMPATIBLE"
