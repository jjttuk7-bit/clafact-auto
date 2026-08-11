from pathlib import Path

from core.verification_profile_loader import load_verification_profiles


def test_cpi_detail_growth_profiles_are_loadable_and_exact() -> None:
    profiles = load_verification_profiles(Path("data/verification_profiles/cpi_detail_growth_v1.json"))
    assert len(profiles) == 5
    assert {profile.claim_key for profile in profiles} == {"cpi_detail:A02A01701", "cpi_detail:A02A01708", "cpi_detail:A01A01101", "cpi_detail:A03A01601", "cpi_detail:A05A01405"}
    assert all(profile.calculation_type == "GROWTH_RATE" for profile in profiles)


def test_cpi_detail_growth_profiles_declare_monthly_applicability() -> None:
    profiles = load_verification_profiles(Path("data/verification_profiles/cpi_detail_growth_v1.json"))

    assert {profile.frequency_constraint for profile in profiles} == {"M"}
