from datetime import date

from core.dynamic_kosis_verifier import _value_provenance
from core.kosis_fetcher import KosisValue
from core.kosis_publication import PublicationEvidence
from schemas.evidence import EvidenceCellSchema


def test_range_publication_and_row_change_date_are_preserved_in_provenance() -> None:
    cell = EvidenceCellSchema(
        org_id="101",
        tbl_id="DT_1DA7002S",
        itm_id="T20",
        dimension_codes={"A": "00"},
        prd_se="M",
        prd_de="1999-06",
        unit="%",
        canonical_key="101:DT_1DA7002S:T20:A=00:M:1999-06",
        status="CONFIRMED",
    )
    publication = PublicationEvidence(
        status="VERIFIED",
        published_at=date(2025, 7, 16),
        source_url="https://www.kostat.go.kr/board.es?act=view&list_no=437607",
        retrieved_at="2026-08-23T00:00:00Z",
        content_hash="a" * 64,
        evidence_scope="CALCULATION_RANGE",
        reference_period="2025-06",
        coverage_start_period="1999-06",
        coverage_end_period="2025-06",
    )
    official = KosisValue(
        60.3,
        "SUCCESS",
        "b" * 64,
        "API",
        publication=publication,
        value_last_changed_at=date(2009, 3, 18),
    )

    provenance = _value_provenance(cell, official)

    assert provenance.value_last_changed_at == date(2009, 3, 18)
    assert provenance.publication is not None
    assert provenance.publication.evidence_scope == "CALCULATION_RANGE"
    assert provenance.publication.reference_period == "2025-06"
    assert provenance.publication.coverage_start_period == "1999-06"
    assert provenance.publication.coverage_end_period == "2025-06"
