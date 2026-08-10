"""Write reproducible E2E batch results and coverage report from local inputs."""
import json
from pathlib import Path
import sys

from core.claim_registry_loader import load_claim_registry
from core.e2e_batch_runner import run_e2e_batch, summarize_e2e_batch
from core.verification_profile_loader import load_verification_profiles
from schemas.concept import StandardConceptSchema


def run(registry_path: Path, profiles_path: Path, concepts_path: Path, output_dir: Path) -> tuple[Path, Path]:
    registry = load_claim_registry(registry_path)
    profiles = load_verification_profiles(profiles_path)
    concepts_payload = json.loads(concepts_path.read_text(encoding="utf-8"))
    concepts = {(row["article_id"], row["sentence_id"]): StandardConceptSchema.model_validate(row["concept"]) for row in concepts_payload}
    results = run_e2e_batch(registry.records, profiles, concepts)
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "e2e_results.jsonl"
    report_path = output_dir / "coverage_report.json"
    results_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results), encoding="utf-8")
    report = summarize_e2e_batch(results)
    report["registry_load_errors"] = [{"line_number": error.line_number, "reason_code": error.reason_code} for error in registry.errors]
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return results_path, report_path


if __name__ == "__main__":
    run(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
