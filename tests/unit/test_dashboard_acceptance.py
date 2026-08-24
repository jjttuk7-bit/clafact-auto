from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from core.dashboard_acceptance import (
    AcceptanceCase,
    apply_acceptance_to_ledger,
    evaluate_dashboard_result,
    select_completed_cases,
)


def _resolution(*, status: str = "AUTO", verdict: str = "MATCH", source: str = "API"):
    provenance = [
        SimpleNamespace(
            source=source,
            source_url="https://official.example/evidence",
            content_hash="abc123",
            retrieved_at="2026-08-24T12:00:00+09:00",
            publication=SimpleNamespace(status="VERIFIED"),
        )
    ]
    evidence = [SimpleNamespace(canonical_key="T1/2025", tbl_id="T1")]
    return SimpleNamespace(
        verdict=SimpleNamespace(
            route_status=status,
            verdict=verdict,
            reason_code="WITHIN_TOLERANCE",
            evidence_cells=evidence,
            evidence_values=[10.0],
            calculated_value=10.0,
            official_value_provenance=provenance,
        )
    )


def _entry(
    *,
    status: str = "AUTO",
    verdict: str = "MATCH",
    resolution=True,
    admission_route="KOSIS_PIPELINE_ELIGIBLE",
    indicator: str = "고용률",
    population=None,
    region=None,
    dimension=None,
):
    return SimpleNamespace(
        claim=SimpleNamespace(
            claim_id="child-1",
            indicator=indicator,
            population=population,
            region=region,
            dimension=dimension,
        ),
        terminal_status=status,
        reason_code=None if status == "AUTO" else "NO_HARD_GUARD_CANDIDATE",
        admission_route=admission_route,
        stage_results=(),
        official_resolution=(
            _resolution(status=status, verdict=verdict) if resolution else None
        ),
    )


def test_select_completed_cases_requires_registry_date() -> None:
    ledger = [
        {
            "Claim번호": "C1",
            "기사번호": "A1",
            "원문": "2025년 고용률은 70%였다.",
            "남은작업": "완료",
            "최신판정": "MATCH",
        },
        {
            "Claim번호": "C2",
            "기사번호": "A2",
            "원문": "보류 문장",
            "남은작업": "좌표 해결",
            "최신판정": "",
        },
    ]

    cases = select_completed_cases(ledger, {"C1": date(2025, 1, 2)})

    assert cases == [
        AcceptanceCase(
            parent_claim_id="C1",
            article_id="A1",
            article_published_at=date(2025, 1, 2),
            article_text="2025년 고용률은 70%였다.",
            expected_verdicts=("MATCH",),
        )
    ]


def test_acceptance_passes_only_when_every_dashboard_child_has_official_verdict() -> None:
    case = AcceptanceCase(
        parent_claim_id="C1",
        article_id="A1",
        article_published_at=date(2025, 1, 2),
        article_text="문장",
        expected_verdicts=("MATCH",),
    )
    result = SimpleNamespace(entries=[_entry()])

    accepted = evaluate_dashboard_result(case, result, run_id="dashboard-1")

    assert accepted.acceptance_status == "통과"
    assert accepted.actual_status == "AUTO"
    assert accepted.actual_verdicts == "MATCH"
    assert accepted.official_evidence_verified == "예"
    assert accepted.source_urls == "https://official.example/evidence"


def test_acceptance_fails_when_any_dashboard_child_holds() -> None:
    case = AcceptanceCase(
        parent_claim_id="C1",
        article_id="A1",
        article_published_at=date(2025, 1, 2),
        article_text="문장",
        expected_verdicts=("MATCH",),
    )
    result = SimpleNamespace(entries=[_entry(), _entry(status="HOLD", resolution=False)])

    accepted = evaluate_dashboard_result(case, result, run_id="dashboard-1")

    assert accepted.acceptance_status == "실패"
    assert accepted.actual_status == "HOLD"
    assert accepted.failure_reason == "NO_HARD_GUARD_CANDIDATE"


def test_acceptance_fails_when_dashboard_verdict_differs_from_ledger() -> None:
    case = AcceptanceCase(
        parent_claim_id="C1",
        article_id="A1",
        article_published_at=date(2025, 1, 2),
        article_text="문장",
        expected_verdicts=("MISMATCH",),
    )

    accepted = evaluate_dashboard_result(
        case, SimpleNamespace(entries=[_entry(verdict="MATCH")]), run_id="dashboard-1"
    )

    assert accepted.acceptance_status == "실패"
    assert accepted.failure_reason == "DASHBOARD_VERDICT_MISMATCH"


def test_acceptance_rejects_official_total_when_sentence_target_depends_on_context() -> None:
    case = AcceptanceCase(
        parent_claim_id="A02111_13",
        article_id="A02111",
        article_published_at=date(2025, 6, 12),
        article_text="고용률도 2011년 36.8%에서 지난달 48.3%로 불었다.",
        expected_verdicts=("MISMATCH",),
    )
    result = SimpleNamespace(entries=[_entry(population="전체")])

    accepted = evaluate_dashboard_result(case, result, run_id="dashboard-1")

    assert accepted.acceptance_status == "실패"
    assert accepted.actual_status == "HOLD"
    assert accepted.failure_stage == "CLAIM_PARSE"
    assert accepted.failure_reason == "DASHBOARD_CONTEXT_TARGET_UNRESOLVED"
    assert accepted.official_evidence_verified == "아니오"


def test_acceptance_allows_continuation_when_target_is_explicit_in_sentence() -> None:
    case = AcceptanceCase(
        parent_claim_id="C1",
        article_id="A1",
        article_published_at=date(2025, 6, 12),
        article_text="고용률도 15~64세는 70.3%였다.",
        expected_verdicts=("MATCH",),
    )
    result = SimpleNamespace(
        entries=[
            _entry(
                population="15~64세",
                dimension={"age": "15~64세"},
            )
        ]
    )

    accepted = evaluate_dashboard_result(case, result, run_id="dashboard-1")

    assert accepted.acceptance_status == "통과"
    assert accepted.actual_status == "AUTO"


def test_apply_acceptance_removes_false_completion_and_preserves_row_count() -> None:
    rows = [
        {"Claim번호": "C1", "남은작업": "완료", "현재문제묶음": "CONTEXT"},
        {"Claim번호": "C2", "남은작업": "좌표 해결", "현재문제묶음": "COORDINATE"},
    ]
    case = AcceptanceCase(
        parent_claim_id="C1",
        article_id="A1",
        article_published_at=date(2025, 1, 2),
        article_text="문장",
        expected_verdicts=("MATCH",),
    )
    failed = evaluate_dashboard_result(
        case,
        SimpleNamespace(entries=[_entry(status="HOLD", resolution=False)]),
        run_id="dashboard-1",
    )

    updated = apply_acceptance_to_ledger(rows, [failed], code_version="abc123")

    assert len(updated) == 2
    assert updated[0]["대시보드검증상태"] == "실패"
    assert updated[0]["대시보드기사작성일"] == "2025-01-02"
    assert updated[0]["대시보드코드버전"] == "abc123"
    assert updated[0]["남은작업"] == "대시보드 재현 실패"
    assert updated[0]["현재문제묶음"] == "HARD_GUARD"
    assert updated[1]["남은작업"] == "좌표 해결"


def test_natural_language_admission_failure_returns_to_context_group() -> None:
    case = AcceptanceCase(
        parent_claim_id="C1",
        article_id="A1",
        article_published_at=date(2025, 1, 2),
        article_text="문장",
        expected_verdicts=("MATCH",),
    )
    entry = _entry(
        status="HUMAN_REVIEW",
        resolution=False,
        admission_route="CONTEXT_REQUIRED",
    )
    entry.reason_code = "기준 시점이 문장에 없어 완전한 수치 주장을 확정할 수 없음"

    failed = evaluate_dashboard_result(
        case,
        SimpleNamespace(entries=[entry]),
        run_id="dashboard-1",
    )
    updated = apply_acceptance_to_ledger(
        [{"Claim번호": "C1", "남은작업": "완료", "현재문제묶음": "REGRESSION"}],
        [failed],
        code_version="abc123",
    )

    assert failed.failure_stage == "CLAIM_PARSE"
    assert updated[0]["대시보드중단단계"] == "CLAIM_PARSE"
    assert updated[0]["현재문제묶음"] == "CONTEXT"
