import csv
from pathlib import Path

from core.direct_value_coordinate_spec_scope import build_coordinate_spec_scope


LEDGER = Path("deliverables/CLAFACT_AUTO_8번_직접값_230건_지표구체화18재처리원장_20260828.csv")


def test_latest_ledger_freezes_exactly_176_unresolved_direct_claims() -> None:
    with LEDGER.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    scope = build_coordinate_spec_scope(rows, expected_count=176)

    assert len(scope.records) == 176
    assert len({record.claim_id for record in scope.records}) == 176
    assert sum(scope.reason_counts.values()) == 176
    assert sum(scope.split_counts.values()) == 176
    assert len(scope.manifest_sha256) == 64


def test_scope_excludes_completed_excluded_and_moved_claims() -> None:
    base = {
        "원본부모Claim번호": "P1", "자식Claim번호": "C1", "원문": "2024년 값은 1명이다.",
        "사용집합": "RULE_DISCOVERY", "복구48최종사유": "NO_HARD_GUARD_CANDIDATE",
    }
    completed = base | {"자식Claim번호": "C2", "개선후공식판정완료": "Y"}
    excluded = base | {"자식Claim번호": "C3", "Claim구조재판정결과": "EXCLUDE_FORECAST"}
    moved = base | {"자식Claim번호": "C4", "지표구체화18결과": "MOVE_SHARE"}

    scope = build_coordinate_spec_scope([base, completed, excluded, moved], expected_count=1)

    assert [record.claim_id for record in scope.records] == ["C1"]
