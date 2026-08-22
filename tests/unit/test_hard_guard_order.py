from datetime import date

import core.dynamic_kosis_verifier as verifier
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def test_hard_guard_rejection_prevents_semantic_scoring(monkeypatch) -> None:
    claim = ClaimSchema(
        claim_id="guard-order",
        source_sentence="2024년 취업자 수는 2,800만 명이었다.",
        indicator="취업자 수",
        value=28_000_000,
        unit="명",
        time="2024년",
        frequency="년",
        parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="employment",
        canonical_name="취업자 수",
        standard_key="employment",
        status="MATCHED",
    )
    monthly = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_MONTHLY",
        tbl_name="월별 취업자",
        core_item_ids=["T"],
        core_item_names=["취업자 수"],
        unit_names=["천명"],
        frequency="월",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    monkeypatch.setattr(
        verifier,
        "semantic_match",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Hard Guard must run before semantic scoring")
        ),
    )

    result = verifier.verify_claim_against_kosis(
        claim,
        concept,
        [monthly],
        article_date=date(2025, 1, 1),
        official_fetcher=object(),
    )

    assert result.reason_code == "NO_HARD_GUARD_CANDIDATE"
