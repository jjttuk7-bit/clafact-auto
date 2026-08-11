from datetime import date
from pathlib import Path

from core.e2e_batch_runner import run_e2e_batch
from core.verification_profile_loader import load_verification_profiles
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord
from schemas.concept import StandardConceptSchema


def test_official_cpi_rate_profile_matches_article_time_snapshot() -> None:
    record = ClaimRegistryRecord(
        article_id="cpi-202510",
        sentence_id="1",
        article_published_at=date(2025, 11, 4),
        source_ref="test",
        claim=ClaimSchema(
            claim_id="cpi-202510-rate",
            source_sentence="지난달 소비자물가 상승률이 2.4%를 기록했다.",
            indicator="소비자물가",
            value=2.4,
            unit="%",
            time="2025-10",
            frequency="월",
            population="전체",
            dimension={"raw": "전체"},
            parse_status="AUTO_OK",
        ),
    )
    profiles = load_verification_profiles(
        Path("data/verification_profiles/consumer_price_yoy_v1.json")
    )
    concept = StandardConceptSchema(
        concept_id="consumer-price",
        canonical_name="소비자물가",
        standard_key="consumer_price",
        status="MATCHED",
    )

    result = run_e2e_batch(
        [record],
        profiles,
        {(record.article_id, record.sentence_id): concept},
        snapshot_paths=[Path("data/kosis_snapshots/official_cpi_202510.json")],
    )

    assert result[0]["route_status"] == "AUTO"
    assert result[0]["verdict"] == "MATCH"
    assert result[0]["official_value"] == 2.4
