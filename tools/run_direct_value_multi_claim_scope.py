"""Run one approved direct-value multi-Claim batch through the canonical pipeline."""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
from datetime import date
from hashlib import sha256
import json
import platform
from pathlib import Path
from typing import Any

from config.settings import Settings
from core.canonical_pipeline import build_canonical_pipeline
from core.direct_value_multi_claim_scope import (
    DirectValueMultiClaimCase,
    load_direct_value_multi_claim_scope,
    run_scope_with_checkpoint,
)
from core.unified_claim_pipeline import PipelineEntry
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_csv", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--expected-parents", type=int, default=360)
    parser.add_argument("--approved-external-limit", type=int, default=236)
    parser.add_argument("--live-budget-seconds", type=float, default=45.0)
    parser.add_argument("--checkpoint", type=Path)
    args = parser.parse_args()

    scope = load_direct_value_multi_claim_scope(
        args.source_csv,
        expected_parent_count=args.expected_parents,
        approved_external_limit=args.approved_external_limit,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = args.checkpoint or args.output_dir / "checkpoint.jsonl"
    settings = Settings()
    signature = _execution_signature(scope.source_sha256, settings)
    pipeline = build_canonical_pipeline(
        settings,
        live_time_budget_seconds=args.live_budget_seconds,
    )

    def execute(case: DirectValueMultiClaimCase) -> dict[str, Any]:
        entries = pipeline.verify_record(
            _record_from_case(case),
            article_context=case.source_sentence,
        )
        children = [_serialize_entry(entry) for entry in entries]
        status, reason_code = _grouping_parent_status(children)
        return {
            "parent_claim_id": case.parent_claim_id,
            "source_sentence_sha256": sha256(
                case.source_sentence.encode("utf-8")
            ).hexdigest().upper(),
            "expressions": list(case.expressions),
            "status": status,
            "reason_code": reason_code,
            "children": children,
        }

    rows = run_scope_with_checkpoint(
        scope.grouping_cases,
        execute,
        checkpoint,
        signature=signature,
        start=args.start,
        limit=args.limit,
    )
    batch_path = args.output_dir / f"batch_{args.start:03d}_{len(rows):02d}.jsonl"
    _atomic_write(
        batch_path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )
    report = {
        "safe_parent_count": len(scope.parents),
        "single_parent_count": len(scope.single_cases),
        "external_grouping_parent_count": len(scope.grouping_cases),
        "approved_external_limit": args.approved_external_limit,
        "batch_start": args.start,
        "batch_count": len(rows),
        "batch_pass": sum(row.get("status") == "PASS" for row in rows),
        "batch_review": sum(row.get("status") != "PASS" for row in rows),
        "child_count": sum(len(row.get("children") or []) for row in rows),
        "signature": signature,
        "checkpoint": str(checkpoint.resolve()),
        "batch_output": str(batch_path.resolve()),
    }
    _atomic_write(
        args.output_dir / f"batch_{args.start:03d}_summary.json",
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    )
    print(json.dumps(report, ensure_ascii=False))


def _record_from_case(case: DirectValueMultiClaimCase) -> ClaimRegistryRecord:
    row = case.source_row
    claim = ClaimSchema(
        claim_id=case.parent_claim_id,
        source_sentence=case.source_sentence,
        indicator=_required(row, "지표"),
        value=float(_required(row, "기사값")),
        unit=_required(row, "단위"),
        time=_optional(row, "기준시점"),
        frequency=_optional(row, "주기"),
        region=_optional(row, "지역"),
        population=_optional(row, "대상집단"),
        dimension=_json_optional(row.get("차원")),
        comparison=_json_optional(row.get("비교조건")),
        calculation=_optional(row, "계산방식") or "DIRECT_VALUE",
        condition=_json_optional(row.get("조건")),
        source_hint=_optional(row, "출처힌트"),
        parse_status="AUTO_OK",
        parse_reason=None,
    )
    enrichment = _json_optional(row.get("숫자역할파이프라인보강JSON")) or {}
    return ClaimRegistryRecord(
        article_id=_optional(row, "기사번호") or case.parent_claim_id.split("_")[0],
        sentence_id=_optional(row, "문장번호") or case.parent_claim_id,
        article_published_at=date.fromisoformat(_required(row, "기사작성일")[:10]),
        source_ref="direct_value_multi_claim_scope_v1",
        claim=claim,
        slot_enrichment=enrichment,
        source_metadata={
            "multi_claim_scope_parent_id": case.parent_claim_id,
            "multi_claim_scope_expressions": json.dumps(
                list(case.expressions),
                ensure_ascii=False,
            ),
        },
    )


def _serialize_entry(entry: PipelineEntry) -> dict[str, Any]:
    return {
        "parent_claim_id": entry.parent_claim_id,
        "child_claim_id": entry.claim.claim_id,
        "recovery_action": entry.recovery_action,
        "admission_route": entry.admission_route,
        "terminal_status": entry.terminal_status,
        "reason_code": entry.reason_code,
        "diagnostic_id": entry.diagnostic_id,
        "claim": entry.claim.model_dump(mode="json"),
        "official_resolution": _jsonable(entry.official_resolution),
        "lineage_record": _jsonable(entry.lineage_record),
        "stage_results": _jsonable(entry.stage_results),
        "slot_audit": _jsonable(entry.slot_audit),
    }


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    raise TypeError(f"MULTI_CLAIM_RESULT_NOT_SERIALIZABLE:{type(value).__name__}")


def _json_optional(raw: object) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("MULTI_CLAIM_SLOT_JSON_MUST_BE_OBJECT")
    return value


def _required(row: dict[str, str], key: str) -> str:
    value = _optional(row, key)
    if value is None:
        raise ValueError(f"MULTI_CLAIM_REQUIRED_FIELD_MISSING:{key}")
    return value


def _optional(row: dict[str, str], key: str) -> str | None:
    value = str(row.get(key) or "").strip()
    return value or None


def _grouping_parent_status(children: list[dict[str, Any]]) -> tuple[str, str | None]:
    if not children:
        return "HUMAN_REVIEW", "CLAIM_GROUPING_INCOMPLETE"
    for child in children:
        reason = str(child.get("reason_code") or "")
        if reason.startswith("GROUPING_"):
            return "HUMAN_REVIEW", reason
    if all(child.get("recovery_action") == "MULTI_CLAIM_SPLIT" for child in children):
        return "PASS", None
    reason = next((child.get("reason_code") for child in children if child.get("reason_code")), None)
    return "HUMAN_REVIEW", reason or "CLAIM_GROUPING_INCOMPLETE"


def _execution_signature(source_sha256: str, settings: Settings) -> str:
    digest = sha256()
    digest.update(source_sha256.encode("ascii"))
    manifest = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "claim_provider": settings.claim_provider,
        "openai_model": settings.openai_model,
        "hcx_extraction_mode": settings.hcx_extraction_mode,
        "versions": {
            name: getattr(settings, name)
            for name in (
                "dataset_version", "preprocess_version", "claim_schema_version",
                "semantic_standard_version", "kosis_catalog_version",
                "matching_version", "calculation_version",
            )
        },
    }
    digest.update(json.dumps(manifest, sort_keys=True).encode("utf-8"))
    roots = (
        PROJECT_ROOT / "core", PROJECT_ROOT / "schemas", PROJECT_ROOT / "config",
        PROJECT_ROOT / "data/semantic_standard", PROJECT_ROOT / "data/kosis_catalog",
        PROJECT_ROOT / "data/official_author",
    )
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            digest.update(path.relative_to(PROJECT_ROOT).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    digest.update(Path(__file__).read_bytes())
    return digest.hexdigest().upper()


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


if __name__ == "__main__":
    main()
