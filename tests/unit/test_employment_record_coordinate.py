from core.evidence_resolver import resolve_evidence_cell
from core.hard_guard import apply_hard_guard
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def _claim() -> ClaimSchema:
    return ClaimSchema(
        claim_id="employment-record",
        source_sentence="\uad6d\uc81c \ube44\uad50 \uae30\uc900 15~64\uc138 \uace0\uc6a9\ub960\uc740 70.3%\ub85c 6\uc6d4 \uae30\uc900 \uc5ed\ub300 \ucd5c\ub300\uc600\ub2e4.",
        indicator="\uace0\uc6a9\ub960", value=70.3, unit="%", time="2025\ub144 6\uc6d4", frequency="\uc6d4",
        population="15~64\uc138", dimension={"\uae30\uc900": "\uad6d\uc81c \ube44\uad50"},
        calculation="RECORD_HIGH", comparison={"type": "RECORD_HIGH"}, parse_status="AUTO_OK",
    )


def _candidate() -> KosisCandidateSchema:
    return KosisCandidateSchema(
        org_id="101", tbl_id="DT_EMP", tbl_name="\uc5f0\ub839\ubcc4 \uace0\uc6a9\ub960",
        core_item_ids=["T"], core_item_names=["\uace0\uc6a9\ub960"],
        dimension_ids=["G"], dimension_names=["\uc5f0\ub839\uacc4\uce35\ubcc4"],
        dimension_members={"G": ["15~64\uc138", "65\uc138 \uc774\uc0c1"]},
        dimension_member_codes={"G": {"15~64\uc138": "1564", "65\uc138 \uc774\uc0c1": "65"}},
        unit_names=["%"], item_units={"T": "%"}, frequency="\uc6d4",
        start_period="2000.01", end_period="2025.06", metadata_status="OFFICIAL_METADATA_READY",
    )


def test_hard_guard_treats_international_comparison_as_age_methodology_not_coordinate() -> None:
    result = apply_hard_guard(_claim(), _candidate())

    assert result.passed is True
    assert result.reject_codes == []


def test_evidence_coordinate_uses_population_age_despite_methodology_qualifier() -> None:
    cell = resolve_evidence_cell(_claim(), _candidate())

    assert cell.status == "CONFIRMED"
    assert cell.dimension_members == {"G": "15~64\uc138"}
    assert cell.dimension_codes == {"G": "1564"}
    assert cell.prd_de == "2025-06"
