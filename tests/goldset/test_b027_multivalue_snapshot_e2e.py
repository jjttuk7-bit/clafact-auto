from datetime import date
from pathlib import Path

from core.kosis_fetcher import OfficialValueFetcher
from schemas.evidence import EvidenceCellSchema


def test_goldset_b027_fetches_each_explicit_industry_code() -> None:
    fetcher = OfficialValueFetcher([Path("data/kosis_snapshots/official_goldset_asof_v3_news_b027.json")])
    common = {"org_id": "101", "tbl_id": "DT_1ES3B31J", "itm_id": "T00", "prd_se": "H", "prd_de": "202402", "status": "CONFIRMED"}
    total = fetcher.fetch(EvidenceCellSchema(**common, dimension_codes={"C1": "Q"}, canonical_key="Q"), article_date=date(2025, 10, 27))
    welfare = fetcher.fetch(EvidenceCellSchema(**common, dimension_codes={"C1": "872"}, canonical_key="872"), article_date=date(2025, 10, 27))

    assert (total.status, total.value) == ("SUCCESS", 3026.9)
    assert (welfare.status, welfare.value) == ("SUCCESS", 1593.8)
