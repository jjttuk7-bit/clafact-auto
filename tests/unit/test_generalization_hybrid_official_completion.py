from tools.compile_direct_value_generalization_results import _strict_official_complete


def _publication():
    return {"status": "VERIFIED"}


def test_hybrid_kosis_coordinate_and_exact_official_release_is_complete() -> None:
    row = {"terminal_status": "AUTO"}
    verdict = {"verdict": "MATCH"}
    evidence = [{"canonical_key": "KOSIS:CELL:1"}]
    provenance = [
        {
            "evidence_key": "KOSIS:CELL:1", "source": "API",
            "source_url": "https://kosis.kr/value", "content_hash": "a",
            "retrieved_at": "2026-08-27T00:00:00Z", "publication": _publication(),
        },
        {
            "evidence_key": "OFFICIAL_PUBLICATION_CLAIM:2025-05",
            "source": "OFFICIAL_DOCUMENT", "source_url": "https://kostat.go.kr/report.hwpx",
            "content_hash": "b", "retrieved_at": "2026-08-27T00:00:01Z",
            "publication": _publication(),
        },
    ]
    assert _strict_official_complete(row, verdict, provenance, evidence) is True


def test_hybrid_completion_still_requires_api_provenance_for_every_coordinate() -> None:
    row = {"terminal_status": "AUTO"}
    verdict = {"verdict": "MATCH"}
    evidence = [{"canonical_key": "KOSIS:CELL:1"}, {"canonical_key": "KOSIS:CELL:2"}]
    provenance = [{
        "evidence_key": "KOSIS:CELL:1", "source": "API",
        "source_url": "https://kosis.kr/value", "content_hash": "a",
        "retrieved_at": "2026-08-27T00:00:00Z", "publication": _publication(),
    }]
    assert _strict_official_complete(row, verdict, provenance, evidence) is False
