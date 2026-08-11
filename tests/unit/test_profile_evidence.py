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

    assert len(evidence) == 1
    assert evidence[0].profile_id == "employment-count-national-total-monthly-v1"
    assert evidence[0].sample_value == 28589
    assert evidence[0].official_coordinate.dimension_codes == {"C1": "0", "C2": "00"}
