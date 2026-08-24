import pytest

from tools.merge_bounded_ledger_rows import merge_selected_rows


def test_replaces_only_selected_rows_and_preserves_master_order() -> None:
    master = [
        {"Claim번호": "C1", "상태": "old-1", "기존": "keep-1"},
        {"Claim번호": "C2", "상태": "old-2", "기존": "keep-2"},
        {"Claim번호": "C3", "상태": "old-3", "기존": "keep-3"},
    ]
    rebuilt = [
        {"Claim번호": "C1", "상태": "new-1", "기존": "changed", "새근거": "e1"},
        {"Claim번호": "C2", "상태": "new-2", "기존": "changed", "새근거": "e2"},
        {"Claim번호": "C3", "상태": "new-3", "기존": "changed", "새근거": "e3"},
    ]

    merged = merge_selected_rows(master, rebuilt, {"C2"})

    assert [row["Claim번호"] for row in merged] == ["C1", "C2", "C3"]
    assert merged[0] == master[0]
    assert merged[1] == rebuilt[1]
    assert merged[2] == master[2]


def test_rejects_selected_identity_missing_from_either_input() -> None:
    master = [{"Claim번호": "C1"}]
    rebuilt = [{"Claim번호": "C1"}]

    with pytest.raises(ValueError, match="SELECTED_CLAIM_NOT_FOUND:C2"):
        merge_selected_rows(master, rebuilt, {"C2"})


def test_rejects_duplicate_claim_identity() -> None:
    duplicated = [{"Claim번호": "C1"}, {"Claim번호": "C1"}]

    with pytest.raises(ValueError, match="DUPLICATE_CLAIM_ID"):
        merge_selected_rows(duplicated, [{"Claim번호": "C1"}], {"C1"})
