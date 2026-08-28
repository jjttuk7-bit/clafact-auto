from core.direct_value_coordinate_spec_bundle import build_coordinate_spec_bundle


def _row(claim_id: str, *, expression: str = "1명", time: str = "2024") -> dict[str, str]:
    return {
        "원본부모Claim번호": claim_id,
        "자식Claim번호": claim_id,
        "기사그룹ID": "A1",
        "원문": "2024년 전국 출생아 수는 1명이다.",
        "기사작성일": "2025-01-10",
        "지표": "출생아 수",
        "기사값": "1",
        "단위": "명",
        "기준시점": time,
        "주기": "Y",
        "지역": "전국",
        "계산방식": "DIRECT_VALUE",
        "파싱상태": "AUTO_OK",
        "대상수치표현": expression,
        "복구48최종사유": "NO_HARD_GUARD_CANDIDATE",
        "사용집합": "RULE_DISCOVERY",
    }


def test_bundle_accounts_for_every_scope_claim_once() -> None:
    rows = [_row("C1"), _row("C2", expression="", time="")]

    bundle = build_coordinate_spec_bundle(rows, expected_count=2)

    assert len(bundle.specs) == 2
    assert len(bundle.ready_records) == 1
    assert len(bundle.preverification_specs) == 1
    assert bundle.readiness_counts == {
        "COORDINATE_READY": 1,
        "PRE_VERIFICATION": 1,
    }
    assert len(bundle.manifest_sha256) == 64
