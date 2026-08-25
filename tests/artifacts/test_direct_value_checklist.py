from __future__ import annotations

import re
from pathlib import Path


HTML_PATH = (
    Path(__file__).resolve().parents[2]
    / "deliverables"
    / "CLAFACT_AUTO_8번_직접값_381건_전체체크리스트_20260825.html"
)


def _html() -> str:
    return HTML_PATH.read_text(encoding="utf-8")


def test_checklist_contains_all_ten_ordered_phases() -> None:
    html = _html()
    phase_ids = re.findall(r'id:\s*"phase-(\d+)"', html)
    assert phase_ids == [str(index) for index in range(10)]


def test_checkboxes_are_program_controlled() -> None:
    html = _html()
    assert 'class="task-check" type="checkbox" disabled' in html
    assert 'class="phase-check" type="checkbox" disabled' in html


def test_completion_requires_all_four_evidence_conditions() -> None:
    html = _html()
    assert "completionSummary.trim()" in html
    assert "evidenceReference.trim()" in html
    assert 'verificationResult === "PASS"' in html
    assert "criteriaConfirmed" in html


def test_state_is_versioned_and_can_be_exported_and_imported() -> None:
    html = _html()
    assert "clafact-direct-value-381-checklist-v1" in html
    assert 'id="export-state"' in html
    assert 'id="import-state"' in html
    assert 'id="import-file"' in html


def test_document_includes_381_scope_and_final_acceptance_equation() -> None:
    html = _html()
    assert "8번 직접값 381건" in html
    assert "판정 완료 + 정당한 보류 + 다른 유형 이동 + 검증 제외 = 381건" in html

