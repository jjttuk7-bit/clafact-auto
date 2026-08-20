"""Non-routing diagnostics for whether a result is likely KOSIS-applicable."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any


_NON_KOSIS_OR_PRIVATE = re.compile(
    r"미 노동부|미국 노동부|KAIDA|한국수입자동차협회|카이즈유|키움증권|"
    r"HMG그룹|테슬라|벤츠|BMW|압타밀|백산수|회사 매출|기업.*전망"
)
_RELATIVE_PERIOD = re.compile(r"지난달|이달|올해|작년")
_OFFICIAL_RELEASE = re.compile(r"통계청|국가데이터처|관세청|한국은행|산업통상자원부")


def classify_result_applicability(result: Mapping[str, Any]) -> dict[str, Any]:
    """Classify diagnostic applicability without altering pipeline outcome."""
    sentence = str(result.get("source_sentence") or "")
    if _NON_KOSIS_OR_PRIVATE.search(sentence):
        label = "LIKELY_NON_KOSIS_OR_PRIVATE"
        rationale = "Foreign, private, or company-specific source cue found in Claim text."
    elif _RELATIVE_PERIOD.search(sentence) and not _OFFICIAL_RELEASE.search(sentence):
        label = "CONTEXT_REQUIRED"
        rationale = "Relative period requires article or release context before coordinate resolution."
    else:
        label = "KOSIS_AUTO_CANDIDATE"
        rationale = "No pre-diagnostic exclusion cue found; official pipeline result remains authoritative."
    return {
        "label": label,
        "rationale": rationale,
        "changes_pipeline_route": False,
        "diagnostic_version": "1.0",
    }


def annotate_result_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Attach diagnostics while retaining every existing pipeline field verbatim."""
    annotated: list[dict[str, Any]] = []
    for row in rows:
        copy = dict(row)
        copy["applicability_diagnosis"] = classify_result_applicability(copy)
        annotated.append(copy)
    return annotated
