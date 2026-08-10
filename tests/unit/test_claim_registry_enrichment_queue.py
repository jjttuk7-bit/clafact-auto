from core.claim_registry_enrichment_queue import build_enrichment_queue


def test_enrichment_queue_marks_missing_required_slots_for_auto_claims() -> None:
    records = [
        {
            "article_id": "A1",
            "sentence_id": "2",
            "claim": {
                "parse_status": "AUTO_OK",
                "indicator": "고용률",
                "value": 70.0,
                "unit": "%",
                "time": "2025-01",
                "frequency": "월",
                "region": None,
                "population": None,
                "dimension": None,
                "comparison": None,
                "calculation": None,
                "condition": None,
                "source_hint": None,
            },
        }
    ]

    queue, summary = build_enrichment_queue(records)

    assert queue == [
        {
            "article_id": "A1",
            "sentence_id": "2",
            "parse_status": "AUTO_OK",
            "work_type": "SEMANTIC_SLOT_ENRICHMENT",
            "missing_slots": ["comparison", "calculation"],
        }
    ]
    assert summary == {"total_records": 1, "queued_records": 1, "work_type_counts": {"SEMANTIC_SLOT_ENRICHMENT": 1}}


def test_enrichment_queue_routes_non_auto_claims_to_structured_reparse() -> None:
    records = [
        {
            "article_id": "A2",
            "sentence_id": "1",
            "claim": {"parse_status": "HOLD", "indicator": None, "value": None, "unit": None, "time": None},
        }
    ]

    queue, summary = build_enrichment_queue(records)

    assert queue[0]["work_type"] == "STRUCTURED_REPARSE_OR_REVIEW"
    assert queue[0]["missing_slots"] == ["indicator", "value", "unit", "time", "comparison", "calculation"]
    assert summary["work_type_counts"] == {"STRUCTURED_REPARSE_OR_REVIEW": 1}
