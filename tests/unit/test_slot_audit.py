from core.slot_audit import audit_claim_slots
from schemas.claim import ClaimSchema


def _claim(**updates: object) -> ClaimSchema:
    payload: dict[str, object] = {
        "claim_id": "C1",
        "source_sentence": "2025년 2월 전국 취업자는 10만 명 증가했다.",
        "indicator": "취업자 수",
        "value": 100000,
        "unit": "명",
        "time": "2025년 2월",
        "frequency": "월",
        "region": "전국",
        "population": None,
        "dimension": None,
        "comparison": {
            "type": "YEAR_OVER_YEAR",
            "operand_source": "OFFICIAL_EVIDENCE",
        },
        "calculation": "DIFFERENCE",
        "condition": {"direction": "INCREASE"},
        "source_hint": None,
        "parse_status": "AUTO_OK",
    }
    payload.update(updates)
    return ClaimSchema.model_validate(payload)


def test_slot_audit_always_records_all_twelve_semantic_slots() -> None:
    result = audit_claim_slots(
        _claim(),
        provenance={"region": "CONTEXT", "frequency": "NORMALIZED"},
    )

    assert [entry.slot for entry in result.entries] == [
        "indicator",
        "value",
        "unit",
        "time",
        "frequency",
        "region",
        "population",
        "dimension",
        "comparison",
        "calculation",
        "condition",
        "source_hint",
    ]
    assert result.by_slot("region").status == "CONTEXT"
    assert result.by_slot("frequency").status == "NORMALIZED"
    assert result.by_slot("population").status == "NOT_APPLICABLE"
    assert result.eligible_for_official_search is True


def test_slot_audit_marks_required_missing_and_conflicting_slots() -> None:
    result = audit_claim_slots(
        _claim(time=None, parse_status="HOLD", parse_reason="MISSING_REQUIRED_SLOTS:time"),
        provenance={"unit": "CONFLICT"},
    )

    assert result.eligible_for_official_search is False
    assert result.by_slot("time").status == "MISSING"
    assert result.by_slot("unit").status == "CONFLICT"
    assert result.reason_codes == (
        "SLOT_CONFLICT:unit",
        "MISSING_REQUIRED_SLOTS:time",
    )
