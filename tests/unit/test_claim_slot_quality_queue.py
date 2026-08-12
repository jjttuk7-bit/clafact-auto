def test_builds_reparse_queue_from_slot_quality_hold() -> None:
    from core.claim_slot_quality_queue import build_slot_quality_reparse_queue

    queue = build_slot_quality_reparse_queue([
        {
            "claim_id": "C1",
            "source_sentence": "지난달 가공식품 물가는 전년 동월 대비 3.1% 올랐다.",
            "reason_code": "CLAIM_PARSE_UNCERTAIN",
            "slot_quality": {
                "reason_code": "CLAIM_PARSE_UNCERTAIN",
                "detected_modifier": "가공식품",
            },
        },
        {"claim_id": "C2", "reason_code": "NO_EVIDENCE_COORDINATE_CANDIDATE"},
    ])

    assert queue == [{
        "claim_id": "C1",
        "source_sentence": "지난달 가공식품 물가는 전년 동월 대비 3.1% 올랐다.",
        "reason_code": "CLAIM_PARSE_UNCERTAIN",
        "detected_modifier": "가공식품",
    }]
