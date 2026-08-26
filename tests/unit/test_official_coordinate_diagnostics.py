from core.official_coordinate_diagnostics import diagnose_official_coordinates
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def _claim(**updates) -> ClaimSchema:
    payload = {
        "claim_id": "c1",
        "source_sentence": "2025년 5월 쉬었음 인구는 239만 명이었다.",
        "indicator": "쉬었음 인구",
        "value": 2_390_000,
        "unit": "명",
        "time": "2025년 5월",
        "frequency": "월",
        "calculation": "DIRECT_VALUE",
        "parse_status": "AUTO_OK",
    }
    payload.update(updates)
    return ClaimSchema.model_validate(payload)


def _candidate(**updates) -> KosisCandidateSchema:
    payload = {
        "org_id": "101",
        "tbl_id": "T1",
        "tbl_name": "연령/활동상태별 비경제활동인구",
        "core_item_ids": ["I1"],
        "core_item_names": ["비경제활동인구"],
        "dimension_ids": ["G", "M"],
        "dimension_names": ["연령계층별", "활동상태별"],
        "dimension_members": {"G": ["계", "15 - 29세"], "M": ["쉬었음"]},
        "dimension_member_codes": {"G": {"계": "00", "15 - 29세": "75"}, "M": {"쉬었음": "905"}},
        "unit_names": ["천명"],
        "item_units": {"I1": "천명"},
        "frequency": "월",
        "start_period": "2003.01",
        "end_period": "2026.07",
        "metadata_status": "OFFICIAL_METADATA_READY",
    }
    payload.update(updates)
    return KosisCandidateSchema.model_validate(payload)


def test_diagnostics_preserves_hard_guard_reject_codes() -> None:
    result = diagnose_official_coordinates(
        _claim(frequency="분기"),
        [_candidate(frequency="월")],
    )

    assert result.failure_boundary == "HARD_GUARD_REJECTED"
    assert result.hard_guard_reject_counts == {"FREQUENCY_CONFLICT": 1}
    assert result.candidate_count == 1
    assert result.hard_guard_pass_count == 0


def test_diagnostics_distinguishes_unresolved_from_ambiguous_coordinate() -> None:
    unresolved = diagnose_official_coordinates(
        _claim(population="설명 문구"),
        [_candidate()],
    )
    ambiguous = diagnose_official_coordinates(
        _claim(dimension={"age": "15 - 29세"}),
        [_candidate(), _candidate(tbl_id="T2")],
    )

    assert unresolved.failure_boundary == "EVIDENCE_COORDINATE_UNRESOLVED"
    assert unresolved.unresolved_table_ids == ("T1",)
    assert ambiguous.failure_boundary == "EVIDENCE_COORDINATE_AMBIGUOUS"
    assert ambiguous.confirmed_table_ids == ("T1", "T2")
