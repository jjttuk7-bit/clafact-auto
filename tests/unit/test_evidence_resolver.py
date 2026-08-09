from core.evidence_resolver import resolve_evidence_cell
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def candidate(**updates: object) -> KosisCandidateSchema:
    data: dict[str, object] = {"org_id": "101", "tbl_id": "DT_EMP", "tbl_name": "고용", "core_item_ids": ["T1"], "core_item_names": ["고용률"], "dimension_ids": ["SIDO"], "dimension_names": ["시도별"], "dimension_members": {"SIDO": ["서울", "부산"]}, "unit_names": ["%"], "frequency": "YEAR", "metadata_status": "READY"}
    data.update(updates)
    return KosisCandidateSchema(**data)


def claim(**updates: object) -> ClaimSchema:
    data: dict[str, object] = {"claim_id": "C1", "source_sentence": "2024년 서울 고용률은 70%였다.", "indicator": "고용률", "unit": "%", "time": "2024", "frequency": "YEAR", "region": "서울", "parse_status": "AUTO_OK"}
    data.update(updates)
    return ClaimSchema(**data)


def test_resolve_evidence_cell_confirms_full_coordinate() -> None:
    cell = resolve_evidence_cell(claim(), candidate())
    assert cell.status == "CONFIRMED"
    assert cell.itm_id == "T1"
    assert cell.obj_id == "SIDO"
    assert cell.member_code == "서울"
    assert cell.canonical_key == "ORG=101|TBL=DT_EMP|ITM=T1|OBJ=SIDO|MEMBER=서울|PRD_SE=YEAR|PRD_DE=2024"


def test_resolve_evidence_cell_holds_when_item_is_not_found() -> None:
    cell = resolve_evidence_cell(claim(indicator="실업률"), candidate())
    assert cell.status == "UNRESOLVED"


def test_resolve_evidence_cell_marks_multiple_items_ambiguous() -> None:
    cell = resolve_evidence_cell(candidate=candidate(core_item_ids=["A", "B"], core_item_names=["고용률", "고용률"]), claim=claim())
    assert cell.status == "AMBIGUOUS"


def test_resolve_evidence_cell_does_not_confirm_unresolved_required_member() -> None:
    cell = resolve_evidence_cell(
        claim(indicator="가구 수", region=None, unit="가구"),
        candidate(
            core_item_names=["가구수"],
            dimension_ids=["A"],
            dimension_names=["가구원수별"],
            dimension_members={"A": ["1인가구", "2인가구"]},
            unit_names=["천가구"],
        ),
    )
    assert cell.status == "UNRESOLVED"


def test_resolve_evidence_cell_confirms_singleton_dimension_without_claim_member() -> None:
    cell = resolve_evidence_cell(
        claim(region=None),
        candidate(
            dimension_ids=["TOTAL"],
            dimension_names=["전체"],
            dimension_members={"TOTAL": ["계"]},
        ),
    )
    assert cell.status == "CONFIRMED"
    assert cell.obj_id == "TOTAL"
    assert cell.member_code == "계"



def test_resolve_evidence_cell_confirms_explicit_two_dimension_coordinate() -> None:
    cell = resolve_evidence_cell(
        claim(region="서울", population="15-29세"),
        candidate(
            dimension_ids=["C1", "C2"],
            dimension_names=["시도별", "연령별"],
            dimension_members={"C1": ["서울", "부산"], "C2": ["15-29세", "30-39세"]},
        ),
    )
    assert cell.status == "CONFIRMED"
    assert cell.dimension_members == {"C1": "서울", "C2": "15-29세"}
