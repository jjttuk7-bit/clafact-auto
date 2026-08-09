from core.evidence_presentation import build_evidence_rows, build_kosis_table_url
from schemas.evidence import EvidenceCellSchema


def _cell(period: str) -> EvidenceCellSchema:
    return EvidenceCellSchema(
        org_id="101", tbl_id="DT_1J22112", itm_id="T", prd_se="M", prd_de=period,
        dimension_codes={"C1": "T10", "C2": "A02A01701"}, canonical_key=period, status="CONFIRMED",
    )


def test_builds_direct_kosis_table_url_from_evidence_coordinate() -> None:
    assert build_kosis_table_url(_cell("202510")) == "https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1J22112&conn_path=I2"


def test_builds_display_rows_with_official_values_and_coordinates() -> None:
    rows = build_evidence_rows([_cell("202510"), _cell("202410")], [136.62, 208.57])

    assert rows[0]["KOSIS 공식값"] == 136.62
    assert rows[1]["기간"] == "2024-10"
    assert rows[0]["좌표"] == "ITM=T | C1=T10 | C2=A02A01701"
