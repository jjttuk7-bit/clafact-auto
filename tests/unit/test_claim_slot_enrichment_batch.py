from core.claim_slot_enrichment_batch import enrich_auto_registry_records
from schemas.claim import ClaimSchema


class FakeExtractor:
    def extract(self, source_sentence: str) -> ClaimSchema:
        return ClaimSchema(
            claim_id="provider",
            source_sentence=source_sentence,
            indicator="provider indicator",
            value=1.0,
            unit="%",
            time="2025년 10월",
            comparison={"type": "YEAR_OVER_YEAR"},
            calculation="GROWTH_RATE",
            condition=None,
            parse_status="AUTO_OK",
        )


def _record(status: str) -> dict:
    return {
        "article_id": "A1",
        "sentence_id": "2",
        "claim": {
            "claim_id": "registry:x:A1:2",
            "source_sentence": "2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다.",
            "indicator": "배추 물가",
            "value": -34.5,
            "unit": "%",
            "time": "2025년 10월",
            "frequency": "월",
            "region": None,
            "population": None,
            "dimension": None,
            "comparison": None,
            "calculation": None,
            "condition": None,
            "source_hint": None,
            "parse_status": status,
            "parse_reason": None,
        },
    }


def test_batch_enricher_processes_only_auto_ok_records_and_adds_audit_status() -> None:
    records, summary = enrich_auto_registry_records(
        [_record("AUTO_OK"), _record("HOLD")], FakeExtractor()
    )

    assert len(records) == 2
    assert records[0]["claim"]["calculation"] == "GROWTH_RATE"
    assert records[0]["slot_enrichment"]["status"] == "ENRICHED"
    assert records[0]["slot_enrichment"]["catalog_search_ready"] is True
    assert records[1]["slot_enrichment"]["status"] == "SKIPPED"
    assert summary == {
        "total_records": 2,
        "processed_records": 1,
        "ready_for_catalog_search": 1,
        "held_records": 0,
        "skipped_records": 1,
        "error_records": 0,
    }

def test_batch_enricher_holds_ambiguous_direction_despite_provider_suggestion() -> None:
    records, summary = enrich_auto_registry_records(
        [_record("AUTO_OK") | {"claim": _record("AUTO_OK")["claim"] | {"source_sentence": "수출은 3% 감소했다."}}],
        FakeExtractor(),
    )

    assert records[0]["claim"]["parse_status"] == "HOLD"
    assert records[0]["claim"]["parse_reason"] == "AMBIGUOUS_COMPARISON"
    assert records[0]["slot_enrichment"] == {
        "status": "HOLD",
        "reason_code": "AMBIGUOUS_COMPARISON",
        "catalog_search_ready": False,
    }
    assert summary["held_records"] == 1
