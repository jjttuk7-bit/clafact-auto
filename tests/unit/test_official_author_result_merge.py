import pytest

from tools.merge_official_author_fallback_results import replace_claim_rows


def test_replaces_only_expected_five_claim_rows_and_preserves_order() -> None:
    baseline = [{"claim_id": f"c{index}", "value": "old"} for index in range(15)]
    improved = [{"claim_id": f"c{index}", "value": "new"} for index in range(5, 10)]

    merged = replace_claim_rows(baseline, improved, expected_replacements=5)

    assert [row["claim_id"] for row in merged] == [f"c{index}" for index in range(15)]
    assert [row["value"] for row in merged[:5]] == ["old"] * 5
    assert [row["value"] for row in merged[5:10]] == ["new"] * 5
    assert [row["value"] for row in merged[10:]] == ["old"] * 5


def test_rejects_missing_duplicate_or_wrong_replacement_count() -> None:
    baseline = [{"claim_id": f"c{index}"} for index in range(15)]

    with pytest.raises(ValueError, match="REPLACEMENT_COUNT_MISMATCH"):
        replace_claim_rows(baseline, [{"claim_id": "c0"}], expected_replacements=5)
    with pytest.raises(ValueError, match="REPLACEMENT_IDS_INVALID"):
        replace_claim_rows(baseline, [{"claim_id": "c0"}] * 5, expected_replacements=5)
    with pytest.raises(ValueError, match="REPLACEMENT_ID_NOT_FOUND"):
        replace_claim_rows(
            baseline,
            [{"claim_id": claim_id} for claim_id in ("c0", "c1", "c2", "c3", "missing")],
            expected_replacements=5,
        )
