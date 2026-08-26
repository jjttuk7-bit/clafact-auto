import csv
from pathlib import Path

from tools.build_direct_value_generalization_baseline import build_baseline_rows


def test_builds_type8_only_baseline_and_applies_latest_rerun() -> None:
    ledger = [
        {
            "최종검증유형": "8번 직접값",
            "원본부모Claim번호": "A00001_1",
            "자식Claim번호": "c1",
            "최종상태": "HOLD",
            "최종사유코드": "NO_EVIDENCE_COORDINATE_CANDIDATE",
            "실패단계": "HARD_GUARD",
            "공식판정완료": "N",
            "판정": "",
        },
        {
            "최종검증유형": "8번 직접값 제외",
            "원본부모Claim번호": "A00002_1",
            "자식Claim번호": "c2",
        },
    ]
    rerun = [
        {
            "행구분": "동일패턴7건재실행",
            "대상Claim번호": "c1",
            "공식경로규칙": "RULE-EMPLOYMENT-MONTHLY",
            "개선후상태": "AUTO",
            "개선후사유": "WITHIN_TOLERANCE",
            "개선후실패단계": "VERDICT",
            "판정": "MATCH",
            "공식값": "100",
            "공식좌표JSON": "[]",
            "공식출처URL": "https://kosis.kr/example",
            "응답해시": "abc",
            "공표확인": "VERIFIED",
            "공식근거완료": "Y",
        }
    ]

    rows = build_baseline_rows(ledger, rerun, seed="test-seed")

    assert len(rows) == 1
    row = rows[0]
    assert row["기준선상태"] == "AUTO"
    assert row["기준선사유"] == "WITHIN_TOLERANCE"
    assert row["기준선공식판정완료"] == "Y"
    assert row["기준선적용규칙"] == "RULE-EMPLOYMENT-MONTHLY"
    assert row["최초실행상태"] == "HOLD"
    assert row["최초실행사유"] == "NO_EVIDENCE_COORDINATE_CANDIDATE"
    assert row["사용집합"] in {
        "RULE_DISCOVERY",
        "INTERMEDIATE_VALIDATION",
        "FINAL_BLIND",
    }


def test_rejects_rerun_for_unknown_claim() -> None:
    ledger = [{
        "최종검증유형": "8번 직접값",
        "원본부모Claim번호": "A00001_1",
        "자식Claim번호": "c1",
    }]
    rerun = [{"행구분": "동일패턴7건재실행", "대상Claim번호": "missing"}]

    try:
        build_baseline_rows(ledger, rerun)
    except ValueError as error:
        assert str(error) == "DIRECT_VALUE_RERUN_CLAIM_NOT_FOUND:missing"
    else:
        raise AssertionError("unknown rerun Claim was accepted")
