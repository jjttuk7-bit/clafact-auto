from pathlib import Path

from core.catalog_overlay_v2 import load_catalog_with_overlay_v2


def test_catalog_overlay_adds_repeated_domain_official_tables() -> None:
    catalog = load_catalog_with_overlay_v2(
        Path("data/kosis_catalog/catalog_350.json"),
        Path("data/kosis_catalog/catalog_overlay_v2.json"),
    )

    identities = {(candidate.org_id, candidate.tbl_id) for candidate in catalog}
    assert ("101", "DT_1B8000G") in identities
    assert ("101", "DT_1DA7001S") in identities
    assert ("101", "DT_1JH20201") in identities


def test_catalog_overlay_replaces_duplicate_identity() -> None:
    catalog = load_catalog_with_overlay_v2(
        Path("data/kosis_catalog/catalog_350.json"),
        Path("data/kosis_catalog/catalog_overlay_v2.json"),
    )

    identities = [(candidate.org_id, candidate.tbl_id) for candidate in catalog]
    assert len(identities) == len(set(identities))
