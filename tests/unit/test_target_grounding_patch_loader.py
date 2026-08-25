import hashlib

from core.source_target_grounding import merge_target_grounding_patch
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def test_merges_jsonl_patch_only_after_claim_and_source_hash_match() -> None:
    source = "20대 인구는 2020년 703만명이다."
    record = ClaimRegistryRecord(
        article_id="A02624",
        sentence_id="7",
        source_ref="frozen",
        claim=ClaimSchema(
            claim_id="A02624_7", source_sentence=source, parse_status="HUMAN_REVIEW"
        ),
    )
    patch = {
        "claim_id": "A02624_7",
        "source_sentence_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest().upper(),
        "slot_enrichment_patch": {
            "target_link_status": "SOURCE_GROUNDED",
            "target_numeric_expression": "703만명",
            "target_numeric_start": 14,
            "target_numeric_end": 19,
        },
    }

    merged = merge_target_grounding_patch(record, patch)

    assert merged.slot_enrichment["target_numeric_expression"] == "703만명"
