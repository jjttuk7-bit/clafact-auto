"""Leakage-safe deterministic split for direct-value generalization evidence."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable, Mapping


RULE_DISCOVERY = "RULE_DISCOVERY"
INTERMEDIATE_VALIDATION = "INTERMEDIATE_VALIDATION"
FINAL_BLIND = "FINAL_BLIND"
_SETS = (RULE_DISCOVERY, INTERMEDIATE_VALIDATION, FINAL_BLIND)


@dataclass(frozen=True, slots=True)
class GeneralizationSplitRecord:
    claim_id: str
    parent_claim_id: str
    article_id: str
    split_set: str
    split_seed: str


def split_claim_rows(
    rows: Iterable[Mapping[str, str]],
    *,
    seed: str = "clafact-direct-value-generalization-v1",
    ratios: tuple[float, float, float] = (0.70, 0.20, 0.10),
) -> list[GeneralizationSplitRecord]:
    """Assign complete articles to discovery, validation, or final blind sets."""

    materialized = list(rows)
    if not materialized:
        return []
    if len(ratios) != 3 or any(value <= 0 for value in ratios):
        raise ValueError("DIRECT_VALUE_SPLIT_RATIOS_INVALID")
    ratio_total = sum(ratios)
    normalized = tuple(value / ratio_total for value in ratios)

    by_article: dict[str, list[tuple[str, str]]] = defaultdict(list)
    seen: set[str] = set()
    for row in materialized:
        parent_id = str(row.get("원본부모Claim번호") or "").strip()
        claim_id = str(row.get("자식Claim번호") or parent_id).strip()
        if not parent_id or not claim_id:
            raise ValueError("DIRECT_VALUE_CLAIM_ID_MISSING")
        if claim_id in seen:
            raise ValueError(f"DIRECT_VALUE_CLAIM_ID_NOT_UNIQUE:{claim_id}")
        seen.add(claim_id)
        article_id = parent_id.split("_", maxsplit=1)[0]
        by_article[article_id].append((claim_id, parent_id))

    ordered_articles = sorted(
        by_article,
        key=lambda article_id: sha256(
            f"{seed}|{article_id}".encode("utf-8")
        ).hexdigest(),
    )
    target = {
        name: len(materialized) * ratio
        for name, ratio in zip(_SETS, normalized)
    }
    assigned_count = {name: 0 for name in _SETS}
    article_set: dict[str, str] = {}
    for name, article_id in zip(_SETS, ordered_articles):
        article_set[article_id] = name
        assigned_count[name] += len(by_article[article_id])

    for article_id in ordered_articles[len(_SETS):]:
        size = len(by_article[article_id])
        selected = min(
            _SETS,
            key=lambda name: (
                sum(
                    (
                        assigned_count[other]
                        + (size if other == name else 0)
                        - target[other]
                    ) ** 2
                    / target[other]
                    for other in _SETS
                ),
                _SETS.index(name),
            ),
        )
        article_set[article_id] = selected
        assigned_count[selected] += size

    result = [
        GeneralizationSplitRecord(
            claim_id=claim_id,
            parent_claim_id=parent_id,
            article_id=article_id,
            split_set=article_set[article_id],
            split_seed=seed,
        )
        for article_id, claims in by_article.items()
        for claim_id, parent_id in claims
    ]
    return sorted(result, key=lambda item: item.claim_id)
