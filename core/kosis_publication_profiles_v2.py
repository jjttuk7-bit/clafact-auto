"""Official KOSTAT release families for recurring CLAFACT domains."""

from __future__ import annotations


PROFILES_V2 = {
    "전산업생산지수": ("213", "산업활동동향"),
    "광업제조업동향조사": ("213", "산업활동동향"),
    "서비스업동향조사": ("213", "산업활동동향"),
    "지역별고용조사": ("210", "지역별고용조사"),
    "농업면적조사": ("213", "벼 재배면적조사 결과"),
    "사망원인통계": ("213", "사망원인통계 결과"),
}


def install_publication_profiles_v2() -> None:
    """Register only official survey-to-release search paths."""
    import core.kosis_publication as publication
    publication._KOSTAT_RELEASE_PROFILES.update(PROFILES_V2)
