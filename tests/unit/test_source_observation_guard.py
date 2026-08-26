from datetime import date

from core.source_observation_guard import observation_preverification_reason
from core.unified_claim_pipeline import verify_registry_record
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _claim(source):
    return ClaimSchema(
        claim_id="claim_growth", source_sentence=source, indicator="경제성장률",
        value=1.4, unit="%", time="2025", frequency="년",
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )


def test_forecast_is_not_treated_as_an_observed_direct_value():
    assert observation_preverification_reason(
        _claim("한국은행은 올해 성장률이 1.4%까지 떨어질 것으로 전망했다.")
    ) == "NON_OBSERVED_FORECAST"
    assert observation_preverification_reason(
        _claim("통계청은 지난해 경제성장률이 1.4%로 집계됐다고 밝혔다.")
    ) is None


def test_forecast_stops_before_official_service():
    class Extractor:
        pass
    class Official:
        def resolve(self, *_args, **_kwargs):
            raise AssertionError("forecast must not call an official value lookup")
    record = ClaimRegistryRecord(
        article_id="article", sentence_id="1", article_published_at=date(2025, 2, 1),
        source_ref="fixture", claim=_claim("한국은행은 올해 성장률이 1.4%까지 떨어질 것으로 전망했다."),
    )
    entry = verify_registry_record(
        record, extractor=Extractor(), official_service=Official(), allow_structured_recovery=False,
    )[0]
    assert entry.terminal_status == "HUMAN_REVIEW"
    assert entry.reason_code == "NON_OBSERVED_FORECAST"
