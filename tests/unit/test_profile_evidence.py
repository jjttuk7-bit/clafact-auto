import json
from pathlib import Path

import pytest


def test_load_profile_evidence_requires_a_snapshot_hash(tmp_path: Path) -> None:
    from core.profile_evidence_loader import load_profile_evidence

    path = tmp_path / "profile_evidence.json"
    path.write_text(
        json.dumps(
            {
                "profile_evidence_schema_version": "v1",
                "evidence": [
                    {
                        "profile_id": "employment-count-national-total-monthly-v1",
                        "official_coordinate": {
                            "org_id": "101", "tbl_id": "DT_1DA7028S", "itm_id": "T30",
                            "prd_se": "M", "dimension_codes": {"C1": "0", "C2": "00"},
                        },
                        "sample_period": "202503",
                        "sample_value": 28589,
                        "unit": "천명",
                        "snapshot_path": "data/kosis_snapshots/official_employment_count_202503.json",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="snapshot_sha256"):
        load_profile_evidence(path)


def test_employment_profile_evidence_uses_the_existing_official_snapshot() -> None:
    from core.profile_evidence_loader import load_profile_evidence

    evidence = load_profile_evidence(Path("data/verification_profiles/profile_evidence_v1.json"))

    evidence_by_profile = {row.profile_id: row for row in evidence}

    employment = evidence_by_profile["employment-count-national-total-monthly-v1"]
    assert employment.sample_value == 28589
    assert employment.official_coordinate.dimension_codes == {"C1": "0", "C2": "00"}

    consumer_price = evidence_by_profile["consumer-price-yoy-national-monthly-v1"]
    assert consumer_price.sample_value == 2.4
    assert consumer_price.official_coordinate.dimension_codes == {"I": "T10"}
