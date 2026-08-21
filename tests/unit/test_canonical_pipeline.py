from __future__ import annotations

from datetime import date

import core.canonical_pipeline as canonical
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _Extractor:
    def extract(self, source_sentence: str, *, article_published_at: date | None = None) -> ClaimSchema:
        return ClaimSchema(
            claim_id="claim-1",
            source_sentence=source_sentence,
            indicator="고용률",
            value=60,
            unit="%",
            time="2024년",
            frequency="년",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        )


class _Service:
    def resolve(self, claim: ClaimSchema, *, article_date: date):
        verdict = type("Verdict", (), {"route_status": "AUTO", "reason_code": "WITHIN_TOLERANCE"})()
        return type("Resolution", (), {"verdict": verdict})()


def test_runtime_exposes_the_same_article_and_record_contract() -> None:
    runtime = canonical.CanonicalPipeline(extractor=_Extractor(), official_service=_Service())
    published_at = date(2025, 1, 10)

    article_result = runtime.verify_article(
        "2024년 고용률은 60%였다.",
        article_published_at=published_at,
        article_id="article-1",
    )
    record = ClaimRegistryRecord(
        article_id="article-1",
        sentence_id="1",
        article_published_at=published_at,
        source_ref="test",
        claim=article_result.entries[0].claim,
    )
    record_entries = runtime.verify_record(record, article_context="기사 본문")

    assert article_result.entries[0].terminal_status == "AUTO"
    assert record_entries[0].terminal_status == "AUTO"
    assert type(article_result.entries[0]) is type(record_entries[0])


def test_factory_constructs_only_the_v3_official_engine(monkeypatch) -> None:
    extractor = _Extractor()
    service = _Service()
    captured = {}

    monkeypatch.setattr(canonical, "create_claim_extractor", lambda settings: extractor)

    def build(paths, **kwargs):
        captured["paths"] = paths
        captured.update(kwargs)
        return service

    monkeypatch.setattr(canonical, "build_official_evidence_service_v3", build)
    settings = type("Settings", (), {"kosis_api_key": "test-key"})()

    runtime = canonical.build_canonical_pipeline(settings, live_time_budget_seconds=12.0)

    assert runtime.extractor is extractor
    assert runtime.official_service is service
    assert captured["kosis_api_key"] == "test-key"
    assert captured["live_time_budget_seconds"] == 12.0
    assert captured["semantic_overlay_path"].name == "concept_overlay_v3.json"
    assert captured["catalog_overlay_path"].name == "catalog_overlay_v2.json"
