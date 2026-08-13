from datetime import date

from core.article_claim_pipeline import parse_article_claims
from schemas.claim import ClaimSchema


class _Extractor:
    def extract(self, sentence: str, *, article_published_at: date | None = None) -> ClaimSchema:
        return ClaimSchema(
            claim_id="placeholder", source_sentence=sentence, indicator="고용률", value=70,
            unit="%", time="2024년", frequency="년", calculation="DIRECT_VALUE", parse_status="AUTO_OK",
        )


def test_parse_article_claims_splits_multiple_numeric_clauses_before_12_slot_parse() -> None:
    claims = parse_article_claims(
        "2023년 고용률은 60%였고 2024년 고용률은 61%였다.",
        _Extractor(), article_published_at=date(2025, 1, 1),
    )

    assert [claim.source_sentence for claim in claims] == ["2023년 고용률은 60%", "2024년 고용률은 61%였다."]
    assert len({claim.claim_id for claim in claims}) == 2


def test_parse_article_claims_selects_numeric_sentences_from_full_article() -> None:
    claims = parse_article_claims(
        "정부가 통계를 발표했다. 2024년 취업자 수는 2804만 명이었다. 전망은 별도로 제시됐다.",
        _Extractor(), article_published_at=date(2025, 1, 1),
    )

    assert [claim.source_sentence for claim in claims] == ["2024년 취업자 수는 2804만 명이었다."]