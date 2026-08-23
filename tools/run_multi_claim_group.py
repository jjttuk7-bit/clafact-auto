"""Run only the frozen employment multi-Claim gold group; never the full Registry."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings
from core.canonical_pipeline import create_claim_extractor
from core.claim_registry_loader import load_claim_registry
from core.issue_group_executor import ContextGroupExecutor
from core.issue_group_harness import ClaimIssueRecord, IssueGroup
from core.multi_claim_group_harness import (
    GoldClaimCase,
    load_gold_cases,
    write_multi_claim_evaluation_csv,
)
from schemas.claim_registry import ClaimRegistryRecord


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 20:
        parser.error("LIMIT_MUST_BE_BETWEEN_1_AND_20")

    cases = load_gold_cases(args.goldset)
    if len(cases) != 20:
        parser.error(f"FROZEN_GOLDSET_MUST_HAVE_20_CASES:{len(cases)}")
    selected = cases[: args.limit]
    loaded = load_claim_registry(args.registry)
    if loaded.errors:
        parser.error(f"SOURCE_REGISTRY_ERRORS:{len(loaded.errors)}")
    source_sentences = _load_source_sentences(args.source_registry)
    joined = _join_source_sentences(loaded.records, source_sentences)
    by_claim_id = {record.claim.claim_id: record for record in joined}
    missing = [case.parent_claim_id for case in selected if case.parent_claim_id not in by_claim_id]
    if missing:
        parser.error(f"GOLD_CLAIM_NOT_IN_CANONICAL_REGISTRY:{','.join(missing)}")

    extractor = create_claim_extractor(Settings())
    executor = ContextGroupExecutor(joined, extractor=extractor)
    results = [
        executor(_issue(case), ("CLAIM_SPLIT", "CLAIM_PARSE"))
        for case in selected
    ]
    code_version = args.code_version
    data_version = args.data_version or _combined_hash(
        args.goldset, args.registry, args.source_registry
    )
    write_multi_claim_evaluation_csv(
        selected,
        results,
        args.output,
        code_version=code_version,
        data_version=data_version,
    )
    _write_jsonl(args.output.with_suffix(".jsonl"), results)
    print(
        json.dumps(
            {
                "selected": len(selected),
                "parent_pass": sum(result.get("status") == "PASS" for result in results),
                "parent_review": sum(result.get("status") != "PASS" for result in results),
                "children": sum(len(result.get("children") or []) for result in results),
                "official_lookup_attempted": False,
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goldset", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--source-registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--code-version", default="multi-claim-role-grouping-v1")
    parser.add_argument("--data-version")
    return parser


def _load_source_sentences(path: Path) -> dict[str, str]:
    sources: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        claim_id = str(payload.get("original_claim_id") or "")
        sentence = str(payload.get("source_sentence") or "").strip()
        if not claim_id or not sentence:
            raise ValueError(f"INVALID_SOURCE_IDENTITY_ROW:{line_number}")
        if claim_id in sources:
            raise ValueError(f"DUPLICATE_SOURCE_IDENTITY:{claim_id}")
        sources[claim_id] = sentence
    return sources


def _join_source_sentences(
    records: list[ClaimRegistryRecord],
    source_sentences: dict[str, str],
) -> list[ClaimRegistryRecord]:
    joined: list[ClaimRegistryRecord] = []
    for record in records:
        sentence = source_sentences.get(record.claim.claim_id)
        if sentence is None:
            joined.append(record)
            continue
        claim = record.claim.model_copy(update={"source_sentence": sentence})
        joined.append(record.model_copy(update={"claim": claim}))
    return joined


def _issue(case: GoldClaimCase) -> ClaimIssueRecord:
    return ClaimIssueRecord(
        article_id=case.article_id,
        sentence_id=case.sentence_id,
        parent_claim_id=case.parent_claim_id,
        claim_id=case.parent_claim_id,
        source_sentence=case.source_sentence,
        current_status="HOLD",
        current_reason="MULTI_CLAIM_SPLIT_REQUIRED",
        current_stop_stage="CLAIM_SPLIT",
        primary_group=IssueGroup.CONTEXT,
        domain="고용",
    )


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
        encoding="utf-8",
    )
    temporary.replace(path)


def _combined_hash(*paths: Path) -> str:
    digest = sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
