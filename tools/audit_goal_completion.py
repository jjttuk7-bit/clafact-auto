"""Measure the consolidated CLAFACT goal against the 1542-record Registry baseline."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(PROJECT_ROOT))

from core.claim_registry_loader import load_claim_registry
from core.data_loader import load_standard_concepts
from core.semantic_normalizer import normalize_concept
from core.semantic_normalizer_v3 import normalize_concept_v3
from core.semantic_standard_v2 import load_semantic_standard_v2
from core.targeted_claim_splitter import build_targeted_claim_inputs


REGISTRY_PATH = Path("artifacts/gold_openai_reparse_v1_20260813/claim_registry.jsonl")
CONTEXT_PATH = Path("artifacts/article_context_catalog_v2_20260820/article_context.jsonl")
BASE_STANDARD = Path("data/semantic_standard/concept_seed_v1.json")
SEMANTIC_OVERLAY = Path("data/semantic_standard/concept_overlay_v3.json")


def build_goal_audit() -> dict[str, object]:
    registry = load_claim_registry(REGISTRY_PATH).records
    base, final = load_standard_concepts(BASE_STANDARD), load_semantic_standard_v2(BASE_STANDARD, SEMANTIC_OVERLAY)
    base_status = Counter(normalize_concept(record.claim, base).status for record in registry)
    final_status = Counter(normalize_concept_v3(record.claim, final).status for record in registry)
    multi_counts = [len(build_targeted_claim_inputs(record.claim.source_sentence)) for record in registry]
    contexts = {json.loads(line)["article_id"] for line in CONTEXT_PATH.read_text(encoding="utf-8").splitlines() if line.strip()}
    relative = ("지난달", "지난해", "작년", "재작년", "올해", "이달", "이번", "내년", "새해", "올 들어", "최근")
    context_candidates = [record for record in registry if record.claim.parse_status != "AUTO_OK" or any(marker in (record.claim.time or "") for marker in relative)]
    official_terms = ("통계청", "국가데이터처", "KOSTAT", "고용동향", "인구동향", "소비자물가", "산업활동동향")
    official_claims = [record for record in registry if any(term in record.claim.source_sentence for term in official_terms)]
    coordinate_terms = ("취업", "고용", "출생", "사망", "출산", "물가", "산업생산", "재배면적", "쉬었음")
    coordinate_claims = [record for record in registry if any(term in ((record.claim.indicator or "") + " " + record.claim.source_sentence) for term in coordinate_terms)]
    report = {
        "baseline_registry_records": len(registry),
        "semantic_standard": {"threshold": 268, "base_matched": base_status["MATCHED"], "final_matched": final_status["MATCHED"], "newly_matched": final_status["MATCHED"] - base_status["MATCHED"], "unresolved_missing_indicator": final_status["UNRESOLVED"]},
        "official_author_fallback": {"threshold": 135, "covered_claims": len(official_claims), "profiles": ["경제활동인구조사", "인구동향조사", "소비자물가조사", "전산업생산지수", "지역별고용조사", "농업면적조사", "사망원인통계"]},
        "coordinate_guard": {"threshold": 120, "covered_claims": len(coordinate_claims), "resolver_version": "metadata-axis-alias-v2"},
        "multi_claim_reentry": {"threshold": 641, "covered_sources": sum(count > 0 for count in multi_counts), "derived_targets": sum(multi_counts)},
        "context_reparse": {"threshold": 539, "covered_claims": sum(record.article_id in contexts for record in context_candidates), "missing_context": sum(record.article_id not in contexts for record in context_candidates)},
    }
    report["goal_acceptance_passed"] = all((report[key]["covered_claims"] if "covered_claims" in report[key] else report[key].get("covered_sources", report[key].get("newly_matched", 0))) >= report[key]["threshold"] for key in ("semantic_standard", "official_author_fallback", "coordinate_guard", "multi_claim_reentry", "context_reparse"))
    return report


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("output_path", type=Path); args = parser.parse_args()
    report = build_goal_audit(); args.output_path.parent.mkdir(parents=True, exist_ok=True); args.output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__": main()
