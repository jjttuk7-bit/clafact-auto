from core.catalog_binding import apply_catalog_binding
from core.kosis_catalog_adapter import hydrate_candidate, normalize_item_metadata
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def test_dimension_member_with_unit_is_not_misclassified_as_measurement_item() -> None:
    structure = normalize_item_metadata([
        {"TBL_ID": "DT_1B8000G", "OBJ_ID": "ITEM", "OBJ_NM": "항목", "ITM_ID": "T1", "ITM_NM": "출생사망혼인이혼"},
        {"TBL_ID": "DT_1B8000G", "OBJ_ID": "A", "OBJ_ID_SN": "2", "OBJ_NM": "종류별", "ITM_ID": "10", "ITM_NM": "출생아수(명)", "UNIT_NM": "명"},
    ], table_id="DT_1B8000G")
    assert structure.item_codes == {"출생사망혼인이혼": "T1"}
    assert structure.dimension_member_codes == {"A": {"출생아수(명)": "10"}}


def test_birth_binding_attaches_verified_member_unit_to_measurement_item() -> None:
    claim = ClaimSchema(
        claim_id="B", source_sentence="11월 출생아 수는 14.6% 늘었다.",
        indicator="출생아 수", value=14.6, unit="%", time="2024년 11월",
        frequency="월", comparison={"type": "YEAR_OVER_YEAR"},
        calculation="GROWTH_RATE", condition={"direction": "INCREASE"}, parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="B", canonical_name="출생아 수", standard_key="birth_count",
        matched_alias="출생아 수", status="MATCHED",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1B8000G", tbl_name="인구동향",
        core_item_ids=["T1"], core_item_names=["출생사망혼인이혼"],
        unit_names=["명", "건"], dimension_ids=["A"], dimension_names=["종류별"],
        dimension_members={"A": ["출생아수(명)", "사망자수(명)"]},
        dimension_member_codes={"A": {"출생아수(명)": "10", "사망자수(명)": "20"}},
        frequency="월", metadata_status="OFFICIAL_METADATA_READY",
    )
    selected = apply_catalog_binding(claim, concept, [candidate])[0]
    assert selected.dimension_member_codes == {"A": {"출생아수(명)": "10"}}
    assert selected.unit_names == ["명"]
    assert selected.item_units == {"T1": "명"}
