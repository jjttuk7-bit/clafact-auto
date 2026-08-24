"""Freeze one bounded group of operational Catalog failures for reprocessing."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


def select_catalog_failures(
    rows: Iterable[Mapping[str, Any]], *, expected_count: int
) -> list[dict[str, Any]]:
    """Select exact Catalog operational failures and reject an unexpected scope."""
    selected = [dict(row) for row in rows if row.get("reason_code") == "KOSIS_CATALOG_UNAVAILABLE"]
    if len(selected) != expected_count:
        raise ValueError(f"EXPECTED_{expected_count}_CATALOG_FAILURES_GOT_{len(selected)}")
    ids = [str(row.get("claim_id") or "") for row in selected]
    if any(not claim_id for claim_id in ids) or len(set(ids)) != len(ids):
        raise ValueError("CATALOG_FAILURE_IDS_INVALID")
    return selected


def freeze_catalog_failures(
    rows: Iterable[Mapping[str, Any]],
    *,
    jsonl_path: Path,
    csv_path: Path,
    expected_count: int,
) -> list[dict[str, Any]]:
    """Persist immutable JSONL input and a compact human-readable before CSV."""
    selected = select_catalog_failures(rows, expected_count=expected_count)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in selected),
        encoding="utf-8",
    )
    headers = (
        "기사번호", "문장번호", "부모Claim번호", "자식Claim번호", "원문",
        "지표", "기사수치", "단위", "시점", "개선전중단사유",
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        for row in selected:
            claim = row.get("claim") if isinstance(row.get("claim"), Mapping) else {}
            writer.writerow({
                "기사번호": row.get("article_id") or "",
                "문장번호": row.get("sentence_id") or "",
                "부모Claim번호": row.get("parent_claim_id") or "",
                "자식Claim번호": row.get("claim_id") or "",
                "원문": claim.get("source_sentence") or row.get("source_sentence") or "",
                "지표": claim.get("indicator") or "",
                "기사수치": claim.get("value") if claim.get("value") is not None else "",
                "단위": claim.get("unit") or "",
                "시점": claim.get("time") or "",
                "개선전중단사유": row.get("reason_code") or "",
            })
    return selected
