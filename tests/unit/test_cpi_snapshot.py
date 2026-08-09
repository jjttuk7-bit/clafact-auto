from datetime import date
from pathlib import Path

from core.kosis_fetcher import OfficialValueFetcher
from schemas.evidence import EvidenceCellSchema


def test_cpi_snapshot_returns_article_date_safe_official_value() -> None:
    cell = EvidenceCellSchema(
        org_id="101",
        tbl_id="DT_1J22042",
        itm_id="T03",
        dimension_members={"I": "총지수"},
        dimension_codes={"I": "T10"},
        prd_se="월",
        prd_de="2025-10",
        unit="%",
        canonical_key="ORG=101|TBL=DT_1J22042|ITM=T03|OBJ=I|MEMBER=총지수|PRD_SE=월|PRD_DE=2025-10",
        status="CONFIRMED",
    )

    result = OfficialValueFetcher([Path("data/kosis_snapshots/official_cpi_202510.json")]).fetch(
        cell,
        article_date=date(2025, 11, 4),
    )

    assert result.status == "SUCCESS"
    assert result.value == 2.4
    assert result.source == "SNAPSHOT"
