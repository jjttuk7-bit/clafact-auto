from pathlib import Path

import pytest

from core.controlled_registry_pilot import derive_controlled_pilot, write_pilot_artifacts
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _BaechuExtractor:
    def extract(self, source_sentence: str) -> ClaimSchema:
        return ClaimSchema(
            claim_id="provider",
            source_sentence=source_sentence,
            indicator="배추 물가",
            value=-34.5,
            unit="%",
            time="2025년 10월",
            frequency="monthly",
            comparison={"basis": "전년 동월 대비", "direction": "하락"},
            parse_status="AUTO_OK",
        )


class _RaisingExtractor:
    def extract(self, source_sentence: str) -> ClaimSchema:
        raise RuntimeError("provider unavailable")


def _record(article_id: str = "A1", sentence_id: str = "S1") -> ClaimRegistryRecord:
    return ClaimRegistryRecord.model_validate(
        {
            "article_id": article_id,
            "sentence_id": sentence_id,
            "source_ref": "fixture",
            "claim": {
                "claim_id": f"source:{article_id}:{sentence_id}",
                "source_sentence": "2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다.",
                "parse_status": "HOLD",
            },
        }
    )


def _standard_path(tmp_path: Path) -> Path:
    path = tmp_path / "standard.json"
    path.write_text(
        '[{"concept_id":"CPI_DETAIL:A02A01701","canonical_name":"배추 소비자물가지수","standard_key":"cpi_detail:A02A01701","aliases":["배추 물가"]}]',
        encoding="utf-8",
    )
    return path


def test_pilot_limits_source_records_and_preserves_source_identity(tmp_path: Path) -> None:
    result = derive_controlled_pilot(
        [_record(), _record("A2", "S2")], _BaechuExtractor(), _standard_path(tmp_path), limit=1
    )

    assert len(result.records) == 1
    assert result.records[0].article_id == "A1"
    assert result.records[0].sentence_id == "S1"


def test_pilot_rejects_non_positive_limit(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="PILOT_LIMIT_MUST_BE_POSITIVE"):
        derive_controlled_pilot([_record()], _BaechuExtractor(), _standard_path(tmp_path), limit=0)


def test_pilot_converts_provider_failure_to_hold_without_dropping_record(tmp_path: Path) -> None:
    result = derive_controlled_pilot([_record()], _RaisingExtractor(), _standard_path(tmp_path))

    assert result.records[0].claim.parse_status == "HOLD"
    assert result.reason_counts["EXTRACTION_FAILED"] == 1


def test_pilot_creates_concept_sidecar_from_concept_seed(tmp_path: Path) -> None:
    result = derive_controlled_pilot([_record()], _BaechuExtractor(), _standard_path(tmp_path))

    assert result.concepts[("A1", "S1")].standard_key == "cpi_detail:A02A01701"


def test_write_pilot_artifacts_rejects_output_inside_source_directory(tmp_path: Path) -> None:
    source_path = tmp_path / "source" / "registry.jsonl"
    source_path.parent.mkdir()
    source_path.write_text("", encoding="utf-8")
    result = derive_controlled_pilot([_record()], _BaechuExtractor(), _standard_path(tmp_path))

    with pytest.raises(ValueError, match="PILOT_OUTPUT_MUST_NOT_OVERLAP_SOURCE"):
        write_pilot_artifacts(result, source_path, source_path.parent)