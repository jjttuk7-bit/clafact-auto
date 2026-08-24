from core.hard_guard_diagnostics import summarize_hard_guard_rejections
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def _claim() -> ClaimSchema:
    return ClaimSchema(
        claim_id="C1",
        source_sentence="2024년 서울 고용률은 70%였다.",
        indicator="고용률",
        value=70.0,
        unit="%",
        time="2024",
        frequency="년",
        region="서울",
        dimension={"sex": "여성"},
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )


def _candidate(table_id: str, **updates: object) -> KosisCandidateSchema:
    payload: dict[str, object] = {
        "org_id": "101",
        "tbl_id": table_id,
        "tbl_name": "고용률",
        "core_item_ids": ["T1"],
        "core_item_names": ["고용률"],
        "dimension_names": ["시도별", "성별"],
        "dimension_members": {"A": ["서울특별시"], "B": ["여자"]},
        "dimension_member_codes": {
            "A": {"서울특별시": "11"},
            "B": {"여자": "3"},
        },
        "unit_names": ["%"],
        "frequency": "년",
        "start_period": "2020",
        "end_period": "2025",
        "metadata_status": "OFFICIAL_METADATA_READY",
    }
    payload.update(updates)
    return KosisCandidateSchema(**payload)


def test_summarizes_candidate_passes_and_every_reject_code() -> None:
    candidates = [
        _candidate("PASS"),
        _candidate("FREQUENCY", frequency="월"),
        _candidate("UNIT", unit_names=["명"]),
        _candidate(
            "DIMENSION",
            dimension_members={"A": ["서울특별시"], "B": ["남자"]},
            dimension_member_codes={
                "A": {"서울특별시": "11"},
                "B": {"남자": "2"},
            },
        ),
    ]

    result = summarize_hard_guard_rejections(_claim(), candidates)

    assert result == {
        "hard_guard_candidate_count": 4,
        "hard_guard_passed_count": 1,
        "hard_guard_reject_DIMENSION_MEMBER_CONFLICT": 1,
        "hard_guard_reject_FREQUENCY_CONFLICT": 1,
        "hard_guard_reject_UNIT_CONFLICT": 1,
    }
