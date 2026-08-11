from datetime import date

from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _record(claim_id: str) -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="A-1",
        sentence_id="2",
        article_published_at=date(2026, 8, 1),
        source_ref="article://A-1",
        claim=ClaimSchema(
            claim_id=claim_id,
            source_sentence="A source sentence",
            indicator="employment",
            value=10,
            unit="persons",
            time="2026-07",
            frequency="M",
            region="national",
            dimension={"age": "all"},
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        ),
    )


def test_build_review_queues_routes_each_actionable_reason_without_mutating_results() -> None:
    from core.review_queue_builder import build_review_queues

    reasons = {
        "PARSE_CONDITION_UNRESOLVED": "parse",
        "CONCEPT_NOT_FOUND": "concept",
        "NO_HARD_GUARD_CANDIDATE": "catalog",
        "EVIDENCE_CELL_UNRESOLVED": "evidence",
        "PUBLICATION_POLICY_HOLD": "publication_policy",
        "KOSIS_VALUE_TRANSPORT_TIMEOUT": "retry",
    }
    records = {_record(f"claim-{index}").claim.claim_id: _record(f"claim-{index}") for index in range(len(reasons))}
    results = [
        {
            "claim_id": claim_id,
            "route_status": "HOLD",
            "reason_code": reason,
            "candidate_metadata": {"table_id": "DT_TEST"},
        }
        for claim_id, reason in zip(records, reasons, strict=True)
    ]

    queues, summary = build_review_queues(results, records)

    assert set(queues) == set(reasons.values())
    assert all(len(rows) == 1 for rows in queues.values())
    assert queues["catalog"][0]["owner_role"] == "KOSIS_CATALOG_CURATOR"
    assert queues["retry"][0]["next_action"] == "Retry the official KOSIS request with the recorded coordinate."
    assert queues["concept"][0]["slots"]["indicator"] == "employment"
    assert queues["concept"][0]["candidate_metadata"] == {"table_id": "DT_TEST"}
    assert summary["total_actionable"] == len(results)
    assert summary["route_counts"] == {"HOLD": len(results)}
    assert results[0]["reason_code"] == "PARSE_CONDITION_UNRESOLVED"


def test_build_review_queues_excludes_auto_rows_and_reconciles_human_review() -> None:
    from core.review_queue_builder import build_review_queues

    record = _record("claim-1")
    queues, summary = build_review_queues(
        [
            {"claim_id": "claim-1", "route_status": "HUMAN_REVIEW", "reason_code": "NO_HARD_GUARD_CANDIDATE"},
            {"claim_id": "claim-2", "route_status": "AUTO", "reason_code": "MATCH"},
        ],
        {"claim-1": record},
    )

    assert list(queues) == ["catalog"]
    assert queues["catalog"][0]["route_status"] == "HUMAN_REVIEW"
    assert summary["total_actionable"] == 1
    assert summary["route_counts"] == {"HUMAN_REVIEW": 1}
