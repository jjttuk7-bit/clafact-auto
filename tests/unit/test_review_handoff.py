from core.review_handoff import build_review_payload
from core.verdict_engine import make_verdict

def test_build_review_payload_for_hold() -> None:
    verdict = make_verdict("C1", 1.0, [], None)
    payload = build_review_payload(verdict)
    assert payload.route_status == "HOLD" and payload.claim_id == "C1"


def test_hold_payload_can_be_submitted_through_review_console_adapter() -> None:
    class RecordingConsole:
        def __init__(self) -> None:
            self.submitted = []

        def submit(self, payload: object) -> str:
            self.submitted.append(payload)
            return "review-001"

    payload = build_review_payload(make_verdict("C1", 1.0, [], None))
    console = RecordingConsole()

    receipt = console.submit(payload)

    assert receipt == "review-001"
    assert console.submitted == [payload]