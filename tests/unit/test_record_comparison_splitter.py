from schemas.claim import ClaimSchema

from core.record_comparison_splitter import split_record_comparison_claim


def _record_claim() -> ClaimSchema:
    return ClaimSchema(
        claim_id="parent",
        source_sentence="\ubc18\ub3c4\uccb4 \uc218\ucd9c\uc561\uc774 1419\uc5b5\ub2ec\ub7ec\ub85c \uc5ed\ub300 \ucd5c\ub300\uce58\ub97c \uae30\ub85d\ud588\ub2e4.",
        indicator="\ubc18\ub3c4\uccb4 \uc218\ucd9c\uc561",
        value=1419,
        unit="\uc5b5\ub2ec\ub7ec",
        time="2024\ub144",
        frequency="\ub144",
        calculation="DIRECT_VALUE",
        comparison={"type": "RECORD_HIGH"},
        parse_status="HOLD",
        parse_reason="RECORD_COMPARISON_REQUIRES_SEPARATE_CLAIM",
    )


def test_splits_direct_value_and_record_assertion_with_stable_ids() -> None:
    first = split_record_comparison_claim(_record_claim())
    second = split_record_comparison_claim(_record_claim())

    assert [claim.calculation for claim in first] == ["DIRECT_VALUE", "RECORD_HIGH"]
    assert first[0].comparison is None
    assert first[1].comparison == {"type": "RECORD_HIGH"}
    assert all(claim.parse_status == "AUTO_OK" for claim in first)
    assert len({claim.claim_id for claim in first}) == 2
    assert [claim.claim_id for claim in first] == [claim.claim_id for claim in second]
    assert all(claim.source_sentence == _record_claim().source_sentence for claim in first)


def test_does_not_split_record_assertion_with_missing_source_value() -> None:
    claim = _record_claim().model_copy(update={"value": None, "unit": None})

    assert split_record_comparison_claim(claim) == [claim]
