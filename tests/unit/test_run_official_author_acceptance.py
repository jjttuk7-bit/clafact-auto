from tools.run_official_author_acceptance import build_rice_area_claim


def test_build_rice_area_claim_is_a_complete_direct_value_claim() -> None:
    claim = build_rice_area_claim()

    assert claim.parse_status == "AUTO_OK"
    assert claim.indicator == "재배면적"
    assert claim.value == 677_597
    assert claim.unit == "ha"
    assert claim.time == "2025"
    assert claim.region == "전국"
    assert claim.calculation == "DIRECT_VALUE"


def test_evaluation_accepts_engine_trace_events_and_evidence_values() -> None:
    from tools.run_official_author_acceptance import _evaluation

    payload = {
        "catalog_diagnostics": {"attempted_queries": 2},
        "verdict": {
            "route_status": "AUTO",
            "verdict": "MATCH",
            "evidence_values": [677_597.0],
            "execution_trace": {"events": [{"stage": "EVIDENCE_CELL"}]},
            "official_value_provenance": [{
                "source": "OFFICIAL_AUTHOR_RELEASE",
                "official_author_evidence": {
                    "published_at": "2025-08-28",
                    "source_url": "https://www.kostat.go.kr/boardDownload.es?bid=229&list_no=438232&seq=3",
                    "document_hash": "sha256:" + "a" * 64,
                },
            }],
        },
    }

    assert _evaluation(payload) == []