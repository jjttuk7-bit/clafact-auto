from core.deterministic_slot_enrichment_batch import (
    build_deterministic_enrichment_report,
    enrich_registry_records_deterministically,
)


def _record(sentence: str, status: str = "AUTO_OK") -> dict:
    return {
        "article_id": "A1",
        "sentence_id": "1",
        "claim": {
            "claim_id": "registry:test:A1:1",
            "source_sentence": sentence,
            "indicator": "테스트 지표",
            "value": 10.0,
            "unit": "%",
            "time": "2025-01",
            "frequency": "월",
            "parse_status": status,
        },
    }


def test_batch_enriches_explicit_direct_and_year_over_year_claims() -> None:
    records, summary = enrich_registry_records_deterministically(
        [
            _record("2024년 출생아 수는 24만2334명이었다."),
            _record("수출은 전년 동월 대비 3% 증가했다."),
        ]
    )

    assert records[0]["claim"]["calculation"] == "DIRECT_VALUE"
    assert records[0]["deterministic_slot_enrichment"]["status"] == "ENRICHED"
    assert records[1]["claim"]["comparison"] == {"type": "YEAR_OVER_YEAR"}
    assert records[1]["claim"]["calculation"] == "GROWTH_RATE"
    assert summary["ready_for_catalog_search"] == 2


def test_batch_holds_ambiguous_direction_without_using_external_provider() -> None:
    records, summary = enrich_registry_records_deterministically([_record("수출은 3% 감소했다.")])

    assert records[0]["claim"]["parse_status"] == "HOLD"
    assert records[0]["claim"]["parse_reason"] == "AMBIGUOUS_COMPARISON"
    assert records[0]["deterministic_slot_enrichment"] == {
        "status": "HOLD",
        "reason_code": "AMBIGUOUS_COMPARISON",
        "catalog_search_ready": False,
    }
    assert summary["held_records"] == 1


def test_batch_preserves_non_auto_claim_without_modifying_source_slots() -> None:
    source = _record("수출은 3% 감소했다.", status="HUMAN_REVIEW")

    records, summary = enrich_registry_records_deterministically([source])

    assert records[0]["claim"] == source["claim"]
    assert records[0]["deterministic_slot_enrichment"]["status"] == "SKIPPED"
    assert summary["skipped_records"] == 1

def test_report_is_derived_from_enriched_records() -> None:
    records, _ = enrich_registry_records_deterministically(
        [
            _record("2024년 출생아 수는 24만2334명이었다."),
            _record("수출은 전년 동월 대비 3% 증가했다."),
            _record("수출은 3% 감소했다."),
            _record("검토 필요", status="HUMAN_REVIEW"),
        ]
    )

    report = build_deterministic_enrichment_report(records)

    assert report["total_records"] == 4
    assert report["enrichment_status_counts"] == {"ENRICHED": 2, "HOLD": 1, "SKIPPED": 1}
    assert report["parse_status_counts"] == {"AUTO_OK": 2, "HOLD": 1, "HUMAN_REVIEW": 1}
    assert report["slot_filled_counts"] == {"comparison": 1, "calculation": 2, "condition": 0}
    assert report["hold_reason_counts"] == {"AMBIGUOUS_COMPARISON": 1}
