from pathlib import Path

from core.claim_registry_loader import load_claim_registry
from core.multi_claim_group_harness import load_gold_cases
from tools.run_multi_claim_group import _join_source_sentences, _load_source_sentences


WORKTREE_ROOT = Path(__file__).resolve().parents[2]
MAIN_ROOT = WORKTREE_ROOT.parents[1] if WORKTREE_ROOT.parent.name == ".worktrees" else WORKTREE_ROOT
CANONICAL = (
    MAIN_ROOT / "artifacts/gold_openai_reparse_v1_20260813/claim_registry.jsonl"
)
SOURCE = WORKTREE_ROOT / "artifacts/clafact_final_completion_202608/01_source_registry.jsonl"
GOLD = WORKTREE_ROOT / "tests/goldset/multi_claim_employment_20.csv"


def test_canonical_slots_are_joined_to_preserved_korean_source_for_all_gold_cases() -> None:
    loaded = load_claim_registry(CANONICAL)
    assert loaded.errors == []
    joined = _join_source_sentences(
        loaded.records,
        _load_source_sentences(SOURCE),
    )
    by_id = {record.claim.claim_id: record for record in joined}

    for case in load_gold_cases(GOLD):
        assert by_id[case.parent_claim_id].claim.source_sentence == case.source_sentence
