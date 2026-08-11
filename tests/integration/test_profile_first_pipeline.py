from datetime import date
from pathlib import Path

from core.e2e_batch_runner import run_e2e_batch
from core.verification_profile_loader import load_verification_profiles
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord
from schemas.concept import StandardConceptSchema


def test_verified_employment_profile_reaches_auto_verdict_from_official_snapshot() -> None:
    record = ClaimRegistryRecord(
        article_id="employment-article",
        sentence_id="1",
        article_published_at=date(2025, 4, 30),
        source_ref="test",
        claim=ClaimSchema(
            claim_id="employment-202503",
            source_sentence="2025 March employment total was 28,589 thousand persons.",
            indicator="employment",
            value=28589,
            unit="thousand persons",
            time="2025-03",
            frequency="monthly",
            region="전국",
            population="전체",
            dimension={"raw": "전체"},
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        ),
    )
    profile = load_verification_profiles(Path("data/verification_profiles/employment_count_v1.json"))
    concept = StandardConceptSchema(
        concept_id="employment",
        canonical_name="employment",
        standard_key="employment_count",
        status="MATCHED",
    )

    results = run_e2e_batch(
        [record], profile, {(record.article_id, record.sentence_id): concept},
        snapshot_paths=[Path("data/kosis_snapshots/official_employment_count_202503.json")],
    )

    assert results[0]["route_status"] == "AUTO"
    assert results[0]["verdict"] == "MATCH"
    assert results[0]["official_value"] == 28589
