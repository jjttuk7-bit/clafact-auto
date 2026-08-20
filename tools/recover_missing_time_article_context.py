"""Recover bounded batches of full article context for missing-time claims."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.article_context_recovery import (
    ArticleContextSource,
    recover_article_contexts,
    select_unrecovered_sources,
)
from core.article_source_fetcher import ArticleSourceFetcher
from schemas.claim_registry import ClaimRegistryRecord


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--context-catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--resume-from", type=Path)
    args = parser.parse_args()

    records = [
        ClaimRegistryRecord.model_validate_json(line)
        for line in args.registry.read_text(encoding="utf-8").splitlines()
        if line
    ]
    catalog = {
        row["article_id"]: row
        for line in args.context_catalog.read_text(encoding="utf-8").splitlines()
        if line
        for row in [json.loads(line)]
    }
    recovered_ids = _recovered_ids(args.resume_from)
    candidates = _missing_time_sources(records, catalog)
    selected = select_unrecovered_sources(candidates, recovered_ids, limit=args.limit)
    contexts, report = recover_article_contexts(selected, ArticleSourceFetcher())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "recovered_context.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in contexts) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "report.json").write_text(
        json.dumps(
            {
                **report,
                "limit": args.limit,
                "resume_source": str(args.resume_from) if args.resume_from else None,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _recovered_ids(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    return {
        json.loads(line)["article_id"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    }


def _missing_time_sources(
    records: list[ClaimRegistryRecord], catalog: dict[str, dict[str, object]]
) -> list[ArticleContextSource]:
    seen: set[str] = set()
    sources: list[ArticleContextSource] = []
    for record in records:
        if record.article_id in seen or record.claim.parse_status == "AUTO_OK":
            continue
        if record.claim.time is not None and "time" not in (record.claim.parse_reason or ""):
            continue
        article = catalog.get(record.article_id)
        if article is None or record.claim.source_sentence in str(article.get("body", "")):
            continue
        sources.append(
            ArticleContextSource(
                article_id=record.article_id,
                title=str(article["title"]),
                article_published_at=str(article["article_published_at"]),
                source_url=str(article["url"]),
            )
        )
        seen.add(record.article_id)
    return sources


if __name__ == "__main__":
    main()


