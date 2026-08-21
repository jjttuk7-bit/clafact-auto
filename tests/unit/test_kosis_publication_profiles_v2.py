from core.kosis_publication_profiles_v2 import install_publication_profiles_v2
import core.kosis_publication as publication


def test_repeated_domain_release_profiles_are_registered() -> None:
    install_publication_profiles_v2()
    profiles = publication._KOSTAT_RELEASE_PROFILES
    assert profiles["전산업생산지수"][1] == "산업활동동향"
    assert profiles["지역별고용조사"][1] == "지역별고용조사"
    assert profiles["농업면적조사"][1] == "벼 재배면적조사 결과"
