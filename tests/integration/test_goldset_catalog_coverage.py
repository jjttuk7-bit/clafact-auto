import json
from pathlib import Path

from core.data_loader import load_kosis_catalog


def test_goldset_catalog_coverage_is_explicit() -> None:
    goldset = json.loads(Path("tests/goldset/fixtures/pilot20.json").read_text(encoding="utf-8"))
    catalog = load_kosis_catalog(Path("data/kosis_catalog/catalog_350.json"))
    catalog_ids = {candidate.tbl_id for candidate in catalog}
    gold_ids = {str(record["gold_table_id"]) for record in goldset if record["KOSIS_재현_상태"] == "KOSIS 재현 가능"}

    assert gold_ids & catalog_ids == {"DT_1DA7028S", "DT_1DA7102S", "DT_1ES4I001S", "DT_1J22042"}
    assert len(gold_ids - catalog_ids) == 8
