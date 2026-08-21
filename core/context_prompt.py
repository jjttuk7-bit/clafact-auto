"""Target-preserving Structured Output prompts for article-context recovery."""

from __future__ import annotations

import json

from schemas.claim import ClaimSchema


def build_context_prompt(claim: ClaimSchema, article_context: str) -> str:
    return json.dumps(
        {
            "target_sentence": claim.source_sentence,
            "article_context": article_context.strip(),
            "instruction": "기사 본문은 부족한 슬롯 보강에만 사용하고 target_sentence 하나만 구조화",
        },
        ensure_ascii=False,
    )
