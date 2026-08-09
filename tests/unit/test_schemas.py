import pytest
from pydantic import ValidationError

from schemas.candidate import HardGuardResult, KosisCandidateSchema, MatchResult
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema
from schemas.evidence import CalculationPlan, EvidenceCellSchema
from schemas.verdict import VerdictSchema


def make_cell() -> EvidenceCellSchema:
    return EvidenceCellSchema(
        org_id="101",
        tbl_id="DT_TEST",
        itm_id="T1",
        prd_se="Y",
        prd_de="2024",
        canonical_key="ORG=101|TBL=DT_TEST|ITM=T1|OBJ=None|MEMBER=None|PRD_SE=Y|PRD_DE=2024",
        status="CONFIRMED",
    )


def test_claim_schema_accepts_twelve_semantic_slots() -> None:
    claim = ClaimSchema(
        claim_id="C1",
        source_sentence="2024년 전국 고용률은 70%였다.",
        indicator="고용률",
        value=70.0,
        unit="%",
        time="2024",
        frequency="YEAR",
        region="전국",
        population="15세 이상",
        dimension={"sex": "전체"},
        comparison=None,
        calculation="DIRECT_VALUE",
        condition=None,
        source_hint="KOSIS",
        parse_status="AUTO_OK",
    )

    assert claim.value == 70.0


def test_claim_schema_rejects_unknown_parse_status() -> None:
    with pytest.raises(ValidationError):
        ClaimSchema(claim_id="C1", source_sentence="문장", parse_status="UNKNOWN")


def test_standard_concept_contract_preserves_mapping_status() -> None:
    concept = StandardConceptSchema(
        concept_id="C0001",
        canonical_name="고용률",
        standard_key="employment_rate",
        matched_alias="고용률",
        status="MATCHED",
    )

    assert concept.status == "MATCHED"


def test_kosis_candidate_contract_supports_catalog_dimensions() -> None:
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_TEST",
        tbl_name="테스트 표",
        core_item_ids=["T1"],
        core_item_names=["고용률"],
        dimension_ids=["SEX"],
        dimension_names=["성별"],
        dimension_members={"SEX": ["전체"]},
        unit_names=["%"],
        metadata_status="READY",
    )

    assert candidate.core_item_ids == ["T1"]


def test_hard_guard_contract_records_rejection_codes() -> None:
    result = HardGuardResult(passed=False, reject_codes=["UNIT_CONFLICT"])

    assert result.passed is False


def test_match_result_requires_explicit_route_status() -> None:
    result = MatchResult(
        candidate_tbl_id="DT_TEST",
        semantic_score=0.9,
        top1_top2_margin=0.2,
        route_status="AUTO",
    )

    assert result.route_status == "AUTO"


def test_evidence_cell_requires_resolution_status() -> None:
    assert make_cell().status == "CONFIRMED"


def test_calculation_plan_limits_known_calculation_types() -> None:
    plan = CalculationPlan(
        calculation_type="DIRECT_VALUE",
        required_cells=[make_cell()],
        operator="=",
        tolerance=0.01,
    )

    assert plan.calculation_type == "DIRECT_VALUE"


def test_calculation_plan_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        CalculationPlan(calculation_type="AVERAGE", required_cells=[])


def test_verdict_carries_all_required_versions() -> None:
    verdict = VerdictSchema(
        claim_id="C1",
        claim_value=70.0,
        evidence_values=[70.0],
        calculated_value=70.0,
        verdict="MATCH",
        route_status="AUTO",
        reason_code="DIRECT_MATCH",
        explanation="값이 일치합니다.",
        evidence_cells=[make_cell()],
        dataset_version="dataset-1",
        semantic_standard_version="standard-1",
        kosis_catalog_version="catalog-1",
        matching_version="matcher-1",
        calculation_version="calc-1",
    )

    assert verdict.verdict == "MATCH"
