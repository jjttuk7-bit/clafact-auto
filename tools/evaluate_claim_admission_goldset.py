"""Evaluate structured Admission routing against a finalized local Gold Set."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from config.settings import Settings
from core.openai_admission_router import OpenAIAdmissionRouter
from core.context_claim_reparse_batch import _limited_context
from schemas.claim import ClaimSchema


def summarize_predictions(rows: list[dict[str, str]]) -> dict[str, Any]:
    correct = sum(row["gold_label"] == row["predicted_label"] for row in rows)
    confusion = Counter(f'{row["gold_label"]} -> {row["predicted_label"]}' for row in rows)
    return {
        "evaluated": len(rows),
        "correct": correct,
        "accuracy": correct / len(rows) if rows else 0.0,
        "confusion": dict(sorted(confusion.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("goldset_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--article-context", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.goldset_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    selected = rows[args.start:] if args.limit is None else rows[args.start:args.start + args.limit]
    contexts = _load_contexts(args.article_context) if args.article_context else {}
    settings = Settings()
    router = OpenAIAdmissionRouter(api_key=settings.openai_api_key, model=settings.openai_model)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / "predictions.jsonl"
    output_path.write_text("", encoding="utf-8")
    predictions: list[dict[str, str]] = []
    for row in selected:
        payload = {name: row.get(name) for name in ClaimSchema.model_fields}
        payload["parse_status"] = row["parse_status_before_admission"]
        payload["parse_reason"] = row.get("parse_reason_before_admission")
        claim = ClaimSchema.model_validate(payload)
        decision = router.route(
            claim, article_context=_limited_context(contexts.get(row["article_id"]), claim.source_sentence, 500)
        )
        prediction = {
            "sample_id": row["sample_id"],
            "claim_id": claim.claim_id,
            "gold_label": row["admission_label"],
            "predicted_label": decision.label,
            "predicted_reason_code": decision.reason_code,
        }
        predictions.append(prediction)
        with output_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(prediction, ensure_ascii=False) + "\n")
    report = {
        "goldset_path": str(args.goldset_path),
        "start": args.start,
        "limit": args.limit,
        "scope": "title + target sentence neighborhood (500 chars) + existing Claim slots only; no full article, KOSIS values, or verdict sent to OpenAI",
        **summarize_predictions(predictions),
    }
    (args.output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


def _load_contexts(path: Path) -> dict[str, dict[str, Any]]:
    return {
        row["article_id"]: row
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for row in [json.loads(line)]
        if isinstance(row.get("title"), str) and isinstance(row.get("body"), str)
    }

if __name__ == "__main__":
    main()
