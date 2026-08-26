from core.structural_candidate_selector import select_official_candidate
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def _claim(**updates):
    payload = {
        "claim_id": "claim_general",
        "source_sentence": "2025년 3월 취업자는 2858만9000명이었다.",
        "indicator": "취업자 수",
        "value": 28_589_000,
        "unit": "명",
        "time": "2025년 3월",
        "frequency": "월",
        "region": "전국",
        "calculation": "DIRECT_VALUE",
        "parse_status": "AUTO_OK",
    }
    payload.update(updates)
    return ClaimSchema(**payload)


def _concept():
    return StandardConceptSchema(
        concept_id="C000008",
        canonical_name="취업자 수",
        standard_key="employment_count",
        matched_alias="취업자 수",
        status="MATCHED",
    )


def _candidate(table_id, item_name="취업자 수", unit="천명"):
    return KosisCandidateSchema(
        org_id="101",
        tbl_id=table_id,
        tbl_name="고용동향",
        core_item_ids=["T30"],
        core_item_names=[item_name],
        dimension_ids=["B"],
        dimension_names=["성별"],
        dimension_members={"B": ["계"]},
        dimension_member_codes={"B": {"계": "0"}},
        unit_names=[unit],
        item_units={"T30": unit},
        frequency="월",
        metadata_status="CONFIRMED",
    )


def test_selects_only_unique_metadata_proven_coordinate():
    selected = select_official_candidate(
        _claim(), _concept(),
        [_candidate("RIGHT"), _candidate("WRONG", item_name="실업률", unit="%")],
    )
    assert [item.tbl_id for item in selected] == ["RIGHT"]
    assert selected[0].source_stat_id == "OFFICIAL_STRUCTURAL_COORDINATE_RULE"


def test_keeps_candidates_when_more_than_one_exact_coordinate_exists():
    candidates = [_candidate("A"), _candidate("B")]
    assert select_official_candidate(_claim(), _concept(), candidates) == candidates


def test_keeps_candidates_when_no_coordinate_is_confirmed():
    candidate = _candidate("A").model_copy(
        update={"dimension_members": {"B": ["남자", "여자"]},
                "dimension_member_codes": {"B": {"남자": "1", "여자": "2"}}}
    )
    assert select_official_candidate(_claim(), _concept(), [candidate]) == [candidate]
