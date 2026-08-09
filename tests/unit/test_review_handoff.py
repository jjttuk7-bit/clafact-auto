from core.review_handoff import build_review_payload
from core.verdict_engine import make_verdict

def test_build_review_payload_for_hold() -> None:
    verdict = make_verdict("C1", 1.0, [], None)
    payload = build_review_payload(verdict)
    assert payload.route_status == "HOLD" and payload.claim_id == "C1"
