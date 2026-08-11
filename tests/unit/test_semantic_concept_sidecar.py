import json

from core.data_loader import SemanticStandardRecord
from core.semantic_concept_sidecar import build_concept_sidecar, write_concept_sidecar
from schemas.claim_registry import ClaimRegistryRecord


def _record(article_id: str, sentence_id: str, indicator: str) -> ClaimRegistryRecord:
    return ClaimRegistryRecord.model_validate({
        "article_id": article_id,
        "sentence_id": sentence_id,
        "article_published_at": "2025-01-01",
        "source_ref": "test",
        "claim": {
            "claim_id": f"{article_id}:{sentence_id}",
            "source_sentence": indicator,
            "indicator": indicator,
            "parse_status": "AUTO_OK",
        },
    })


def test_sidecar_materializes_deterministic_matched_and_unresolved_concepts(tmp_path) -> None:
    records = [_record("A2", "2", "미상 지표"), _record("A1", "1", "취업자 수")]
    standards = [SemanticStandardRecord("C1", "취업자 수", "employment_count", ["취업자 수"])]

    rows = build_concept_sidecar(records, standards)
    path = write_concept_sidecar(rows, tmp_path / "concepts.json")

    assert [(row["article_id"], row["concept"]["status"]) for row in rows] == [("A1", "MATCHED"), ("A2", "UNRESOLVED")]
    assert json.loads(path.read_text(encoding="utf-8")) == rows
