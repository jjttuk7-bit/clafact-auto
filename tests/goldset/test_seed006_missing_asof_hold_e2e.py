from datetime import date
from pathlib import Path

from core.kosis_fetcher import OfficialValueFetcher
from schemas.evidence import EvidenceCellSchema


def test_goldset_seed006_uses_adjudicated_asof_snapshot() -> None:
    cell = EvidenceCellSchema(org_id="101", tbl_id="DT_1YL20651E", itm_id="T20", prd_se="M", prd_de="202502", dimension_codes={"C1": "28"}, canonical_key="seed006", status="CONFIRMED")
    result = OfficialValueFetcher([Path("data/kosis_snapshots/official_goldset_v3_seed006.json")]).fetch(cell, article_date=date(2025, 3, 9))
    assert (result.status, result.value) == ("SUCCESS", 3027854)
