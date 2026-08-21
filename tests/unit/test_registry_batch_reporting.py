from pathlib import Path

from core.registry_batch_reporting import derive_registry_batch


def _record(*, status: str, sentence: str, enrichment_status: str, reason: str | None) -> dict:
    return {
        "article_id": "A1",
        "sentence_id": "S1" if status == "AUTO_OK" else "S2",
        "source_ref": "fixture",
        "claim": {
            "claim_id": f"claim:{status}",
            "source_sentence": sentence,
            "indicator": "취업자 수" if status == "AUTO_OK" else None,
            "value": 28000 if status == "AUTO_OK" else None,
            "unit": "천명" if status == "AUTO_OK" else None,
            "time": "2025년 3월" if status == "AUTO_OK" else None,
            "frequency": "월" if status == "AUTO_OK" else None,
            "region": "전국" if status == "AUTO_OK" else None,
            "population": "전체" if status == "AUTO_OK" else None,
            "dimension": {"raw": "성별"} if status == "AUTO_OK" else None,
            "comparison": None,
            "calculation": "DIRECT_VALUE" if status == "AUTO_OK" else None,
            "condition": None,
            "source_hint": "통계청" if status == "AUTO_OK" else None,
            "parse_status": status,
            "parse_reason": reason,
        },
        "slot_enrichment": {
            "status": enrichment_status,
            "reason_code": reason,
            "catalog_search_ready": status == "AUTO_OK",
        },
    }


def test_derive_batch_maps_only_auto_claims_and_reports_review_reasons(tmp_path: Path) -> None:
    standard_path = tmp_path / "standard.json"
    standard_path.write_text(
        '[{"concept_id":"EMP","canonical_name":"취업자 수","standard_key":"employment_count","aliases":[]}]',
        encoding="utf-8",
    )

    result = derive_registry_batch(
        [
            _record(
                status="AUTO_OK",
                sentence="취업자 수는 2,800만 명이다.",
                enrichment_status="ENRICHED",
                reason=None,
            ),
            _record(
                status="HOLD",
                sentence="수출은 3% 증가했고, 수입은 4% 감소했다.",
                enrichment_status="HOLD",
                reason="AMBIGUOUS_COMPARISON",
            ),
        ],
        standard_path,
    )

    assert len(result.records) == 2
    assert set(result.concepts) == {("A1", "S1")}
    assert result.concepts[("A1", "S1")].standard_key == "employment_count"
    assert result.quality_report["slot_completion"]["indicator"] == {"filled": 1, "total": 2, "rate": 0.5}
    assert result.quality_report["route_counts"] == {"AUTO_OK": 1, "HOLD": 1}
    assert result.quality_report["hold_reason_counts"] == {"AMBIGUOUS_COMPARISON": 1}
    assert result.quality_report["claim_split_candidates"] == 1
    assert len(result.review_queue) == 1
    assert result.review_queue[0]["reason_code"] == "AMBIGUOUS_COMPARISON"
