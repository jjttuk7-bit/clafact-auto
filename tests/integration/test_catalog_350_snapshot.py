from pathlib import Path

from core.data_loader import load_kosis_catalog


def test_catalog_350_snapshot_loads_all_tables() -> None:
    catalog = load_kosis_catalog(Path("data/kosis_catalog/catalog_350.json"))
    assert len(catalog) == 350
    assert any(candidate.tbl_id == "DT_2OENA01" for candidate in catalog)
