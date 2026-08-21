from tools.audit_goal_completion import build_goal_audit


def test_goal_audit_reports_all_five_acceptance_thresholds() -> None:
    report = build_goal_audit()
    assert report["semantic_standard"]["newly_matched"] >= 268
    assert report["official_author_fallback"]["covered_claims"] >= 135
    assert report["coordinate_guard"]["covered_claims"] >= 120
    assert report["multi_claim_reentry"]["covered_sources"] >= 641
    assert report["context_reparse"]["covered_claims"] >= 539
    assert report["goal_acceptance_passed"] is True
