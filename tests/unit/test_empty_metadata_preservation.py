from core.kosis_catalog_adapter import hydrate_candidates_from_official_metadata
from schemas.candidate import KosisCandidateSchema


def test_empty_official_metadata_preserves_existing_candidate() -> None:
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT",
        tbl_name="고용",
        core_item_ids=["T1"],
        core_item_names=["고용률"],
        metadata_status="OFFICIAL_METADATA_READY",
    )

    hydrated = hydrate_candidates_from_official_metadata(
        [candidate],
        lambda _org_id, _table_id: [],
    )

    assert hydrated == [candidate]
