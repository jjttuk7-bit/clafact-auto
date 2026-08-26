"""Merge actual generalization runs into the 230-row direct-value ledger."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable


EXTRA_FIELDS = (
    "일반화실행여부", "일반화실행출처", "적용공통규칙ID", "개선전후변화",
)


def extract_improvement(row: dict[str, Any]) -> dict[str, str]:
    resolution = row.get("official_resolution") if isinstance(row.get("official_resolution"), dict) else {}
    verdict = resolution.get("verdict") if isinstance(resolution.get("verdict"), dict) else {}
    provenance = verdict.get("official_value_provenance") if isinstance(verdict.get("official_value_provenance"), list) else []
    evidence = verdict.get("evidence_cells") if isinstance(verdict.get("evidence_cells"), list) else []
    events = ((verdict.get("execution_trace") or {}).get("events") or []) if isinstance(verdict, dict) else []
    failed = [event for event in events if event.get("status") == "HOLD"]
    stage = str(failed[-1].get("stage") or "") if failed else ("VERDICT" if row.get("terminal_status") == "AUTO" else "CLAIM_PARSE")
    rules: list[str] = []
    candidate_sources = {item.get("source_stat_id") for item in resolution.get("candidates") or []}
    if "OFFICIAL_STRUCTURAL_COORDINATE_RULE" in candidate_sources:
        rules.append("STRUCTURAL_COORDINATE_UNIQUE_V1")
    if "OFFICIAL_RECURRING_DOMAIN_BINDING" in candidate_sources:
        rules.append("OFFICIAL_RECURRING_BINDING_V1")
    claim = row.get("claim") or {}
    concept = resolution.get("concept") or {}
    alias = _key(str(concept.get("matched_alias") or ""))
    source = _key(str(claim.get("source_sentence") or ""))
    current = _key(str(claim.get("indicator") or ""))
    canonical = _key(str(concept.get("canonical_name") or ""))
    if alias and alias in source and canonical and canonical != current and current not in source:
        rules.append("SOURCE_GROUNDED_INDICATOR_V1")
    if row.get("reason_code") == "NON_OBSERVED_FORECAST":
        rules.append("OBSERVATION_STATUS_GUARD_V1")
    if any(item.get("source") == "OFFICIAL_DOCUMENT" for item in provenance):
        rules.append("OFFICIAL_AUTHOR_FALLBACK_V1")
    complete = _strict_official_complete(row, verdict, provenance, evidence)
    publications = [item.get("publication") for item in provenance if isinstance(item.get("publication"), dict)]
    return {
        "상태": str(row.get("terminal_status") or ""),
        "사유": str(row.get("reason_code") or ""),
        "실패단계": stage,
        "판정": str(verdict.get("verdict") or ""),
        "공식값": _text(verdict.get("calculated_value")),
        "공식좌표JSON": json.dumps(evidence, ensure_ascii=False, sort_keys=True),
        "공식출처URL": "|".join(dict.fromkeys(str(item.get("source_url")) for item in provenance if item.get("source_url"))),
        "응답해시": "|".join(dict.fromkeys(str(item.get("content_hash")) for item in provenance if item.get("content_hash"))),
        "공표확인": "VERIFIED" if publications and all(item.get("status") == "VERIFIED" for item in publications) else "",
        "공식판정완료": "Y" if complete else "N",
        "규칙ID": "|".join(dict.fromkeys(rules)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("summary_json", type=Path)
    parser.add_argument("run", type=Path, nargs="+")
    args = parser.parse_args()
    rows = _read_csv(args.baseline_csv)
    by_claim = {str(row.get("자식Claim번호") or row.get("원본부모Claim번호") or ""): row for row in rows}
    applied: dict[str, tuple[str, dict[str, Any]]] = {}
    for run_path in args.run:
        for result in _read_jsonl(run_path):
            claim_id = str(result.get("claim_id") or ((result.get("claim") or {}).get("claim_id")) or "")
            if claim_id in by_claim:
                applied[claim_id] = (str(run_path.resolve()), result)
    for claim_id, (run_path, result) in applied.items():
        improvement = extract_improvement(result)
        row = by_claim[claim_id]
        before = (row.get("기준선상태", ""), row.get("기준선사유", ""), row.get("기준선실패단계", ""))
        after = (improvement["상태"], improvement["사유"], improvement["실패단계"])
        row.update({
            "개선후상태": improvement["상태"], "개선후사유": improvement["사유"],
            "개선후실패단계": improvement["실패단계"], "개선후판정": improvement["판정"],
            "개선후공식값": improvement["공식값"], "개선후공식좌표JSON": improvement["공식좌표JSON"],
            "개선후공식출처URL": improvement["공식출처URL"], "개선후응답해시": improvement["응답해시"],
            "개선후공표확인": improvement["공표확인"], "개선후공식판정완료": improvement["공식판정완료"],
            "적용공통규칙ID": improvement["규칙ID"], "일반화실행여부": "Y",
            "일반화실행출처": run_path, "개선전후변화": "변경" if before != after else "동일",
        })
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) + [field for field in EXTRA_FIELDS if field not in rows[0]]
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)
    summary = {
        "total_claims": len(rows), "executed_claims": len(applied),
        "baseline_official_complete": sum(row.get("기준선공식판정완료") == "Y" for row in rows),
        "improved_official_complete": sum(row.get("개선후공식판정완료") == "Y" for row in rows),
        "new_official_complete": sum(row.get("기준선공식판정완료") != "Y" and row.get("개선후공식판정완료") == "Y" for row in rows),
        "changed_executions": sum(row.get("개선전후변화") == "변경" for row in rows),
        "rule_counts": dict(Counter(rule for row in rows for rule in str(row.get("적용공통규칙ID") or "").split("|") if rule)),
        "after_reason_counts": dict(Counter(row.get("개선후사유", "") for row in rows)),
        "output_csv": str(args.output_csv.resolve()),
        "csv_sha256": sha256(args.output_csv.read_bytes()).hexdigest(),
    }
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


def _strict_official_complete(row: dict[str, Any], verdict: dict[str, Any], provenance: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> bool:
    if row.get("terminal_status") != "AUTO" or verdict.get("verdict") not in {"MATCH", "MISMATCH"} or not provenance:
        return False
    if not all(item.get("source") in {"API", "OFFICIAL_DOCUMENT"} and item.get("source_url") and item.get("content_hash") and item.get("retrieved_at") and isinstance(item.get("publication"), dict) and item["publication"].get("status") == "VERIFIED" for item in provenance):
        return False
    if evidence:
        return Counter(str(item.get("canonical_key") or "") for item in evidence) == Counter(str(item.get("evidence_key") or "") for item in provenance)
    return all(item.get("source") == "OFFICIAL_DOCUMENT" for item in provenance)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle: return list(csv.DictReader(handle))
def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip(): yield json.loads(line)
def _text(value: Any) -> str: return "" if value is None else str(value)
def _key(value: str) -> str: return re.sub(r"[\s_~\-·/'‘’\"]+", "", value).casefold()


if __name__ == "__main__":
    main()
