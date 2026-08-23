import pytest
from pydantic import ValidationError

from schemas.candidate import KosisCandidateSchema


def test_candidate_period_ranges_survive_serialization_round_trip() -> None:
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT",
        tbl_name="고용률",
        period_ranges={
            "월": {"start_period": "1999.06", "end_period": "2026.07"},
            "분기": {"start_period": "1999 3/4", "end_period": "2026 2/4"},
            "년": {"start_period": "2000", "end_period": "2025"},
        },
        metadata_status="OFFICIAL_METADATA_READY",
    )

    restored = KosisCandidateSchema.model_validate(candidate.model_dump())

    assert restored.period_ranges["월"].start_period == "1999.06"
    assert restored.period_ranges["분기"].end_period == "2026 2/4"
    assert restored.period_ranges["년"].start_period == "2000"


def test_period_range_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        KosisCandidateSchema(
            org_id="101",
            tbl_id="DT",
            tbl_name="고용률",
            period_ranges={"월": {"start_period": "1999.06", "guessed": True}},
            metadata_status="OFFICIAL_METADATA_READY",
        )
