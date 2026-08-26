from hashlib import sha256

import pytest

from core.direct_value_coordinate_publication_scope import (
    FINAL_BLIND,
    INTERMEDIATE_VALIDATION,
    RULE_DISCOVERY,
    build_scope_manifest,
)
from tools.build_direct_value_coordinate_publication_scope import build_scope_rows


def _row(claim_id: str, split_set: str, reason: str, source: str) -> dict[str, str]:
    return {
        "원본부모Claim번호": claim_id,
        "자식Claim번호": claim_id,
        "사용집합": split_set,
        "원문": source,
        "개선후사유": reason,
    }


def test_scope_selects_only_coordinate_and_publication_targets() -> None:
    rows = [
        _row("c1", RULE_DISCOVERY, "NO_HARD_GUARD_CANDIDATE", "발견 좌표"),
        _row("c2", INTERMEDIATE_VALIDATION, "NO_EVIDENCE_COORDINATE_CANDIDATE", "중간 좌표"),
        _row("c3", FINAL_BLIND, "AS_OF_UNAVAILABLE", "최종 공표"),
        _row("c4", RULE_DISCOVERY, "PUBLICATION_FETCH_FAILED", "발견 공표"),
        _row("c5", RULE_DISCOVERY, "CLAIM_PARSE_UNCERTAIN", "대상 아님"),
    ]

    manifest = build_scope_manifest(rows)

    assert [item.claim_id for item in manifest.records] == ["c1", "c2", "c3", "c4"]
    assert manifest.reason_counts == {
        "AS_OF_UNAVAILABLE": 1,
        "NO_EVIDENCE_COORDINATE_CANDIDATE": 1,
        "NO_HARD_GUARD_CANDIDATE": 1,
        "PUBLICATION_FETCH_FAILED": 1,
    }
    assert manifest.records[0].source_sentence_sha256 == sha256(
        "발견 좌표".encode("utf-8")
    ).hexdigest()


def test_scope_hides_final_blind_source_until_acceptance() -> None:
    manifest = build_scope_manifest(
        [_row("c1", FINAL_BLIND, "NO_HARD_GUARD_CANDIDATE", "보면 안 되는 원문")]
    )

    public = manifest.to_audit_dict(include_final_blind_source=False)

    assert public["records"][0]["source_sentence"] is None
    assert public["records"][0]["source_sentence_sha256"]


def test_scope_rejects_duplicate_claim_identity() -> None:
    rows = [
        _row("same", RULE_DISCOVERY, "NO_HARD_GUARD_CANDIDATE", "첫째"),
        _row("same", INTERMEDIATE_VALIDATION, "AS_OF_UNAVAILABLE", "둘째"),
    ]

    with pytest.raises(ValueError, match="DIRECT_VALUE_SCOPE_CLAIM_NOT_UNIQUE:same"):
        build_scope_manifest(rows)


def test_scope_builder_joins_registry_and_hides_blind_payload() -> None:
    ledger = [
        _row("c1", RULE_DISCOVERY, "NO_HARD_GUARD_CANDIDATE", "발견 원문"),
        _row("c2", FINAL_BLIND, "AS_OF_UNAVAILABLE", "최종 원문"),
    ]
    registry = [
        {"article_id": "A1", "claim": {"claim_id": "c1", "source_sentence": "발견 원문"}},
        {"article_id": "A2", "claim": {"claim_id": "c2", "source_sentence": "최종 원문"}},
    ]

    manifest, subsets = build_scope_rows(ledger, registry)

    assert [row["claim"]["claim_id"] for row in subsets[RULE_DISCOVERY]] == ["c1"]
    assert [row["claim"]["claim_id"] for row in subsets[FINAL_BLIND]] == ["c2"]
    assert manifest.to_audit_dict(include_final_blind_source=False)["records"][1][
        "source_sentence"
    ] is None


def test_scope_builder_rejects_registry_source_mismatch() -> None:
    ledger = [_row("c1", RULE_DISCOVERY, "NO_HARD_GUARD_CANDIDATE", "원장 원문")]
    registry = [
        {"article_id": "A1", "claim": {"claim_id": "c1", "source_sentence": "다른 원문"}}
    ]

    with pytest.raises(ValueError, match="DIRECT_VALUE_SCOPE_SOURCE_MISMATCH:c1"):
        build_scope_rows(ledger, registry)
