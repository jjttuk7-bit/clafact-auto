import json
from pathlib import Path

from core.official_author_profiles import load_official_author_profiles, match_official_author_profile
from schemas.claim import ClaimSchema


def _claim(indicator: str, *, source_hint: str | None = None, population: str | None = None) -> ClaimSchema:
    return ClaimSchema(
        claim_id="c1",
        source_sentence=f"2024년 {indicator}은 70.3%였다.",
        indicator=indicator,
        value=70.3,
        unit="%",
        time="2024",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
        source_hint=source_hint,
        population=population,
    )


def test_matches_profile_by_semantic_fields_not_claim_id(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps({"profiles": [{
        "profile_id": "food_export",
        "author_name": "농림축산식품부",
        "indicator_terms": ["라면", "수출"],
        "source_hint_terms": ["농림축산식품부"],
        "trusted_hosts": ["mafra.go.kr"],
        "documents": [],
    }]}), encoding="utf-8")
    profiles = load_official_author_profiles(path)

    matched = match_official_author_profile(
        _claim("대미 라면 수출 증가율", source_hint="농림축산식품부"), profiles
    )

    assert matched is not None
    assert matched.profile_id == "food_export"


def test_rejects_ambiguous_profile_match(tmp_path: Path) -> None:
    payload = {"profiles": [{
        "profile_id": profile_id,
        "author_name": author,
        "indicator_terms": ["수출"],
        "source_hint_terms": [],
        "trusted_hosts": [host],
        "documents": [],
    } for profile_id, author, host in (
        ("one", "기관1", "one.go.kr"), ("two", "기관2", "two.go.kr")
    )]}
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    matched = match_official_author_profile(_claim("전체 수출"), load_official_author_profiles(path))

    assert matched is None
