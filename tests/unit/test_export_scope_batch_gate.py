from datetime import date

from core.dynamic_e2e_batch_runner import run_dynamic_e2e_batch
from schemas.claim_registry import ClaimRegistryRecord


def test_export_forecast_holds_before_catalog_search() -> None:
    record = ClaimRegistryRecord.model_validate({
        "article_id": "A1", "sentence_id": "1",
        "article_published_at": date(2025, 1, 7),
        "source_ref": "gold_standard_v1",
        "claim": {
            "claim_id": "A1_1",
            "source_sentence": "한은은 올해 수출 증가율을 1.5%로 내다보고 있다.",
            "indicator": "수출액", "value": 1.5, "unit": "%",
            "time": "2025", "frequency": "Y", "comparison": None,
            "calculation": "GROWTH_RATE", "parse_status": "AUTO_OK",
        },
    })

    class FailingSearch:
        def search(self, _query: str):
            raise AssertionError("forecast must hold before catalog search")

    result = run_dynamic_e2e_batch(
        [record], [], [], live_search=FailingSearch(),
    )[0]

    assert result["route_status"] == "HOLD"
    assert result["reason_code"] == "EXPORT_FORECAST_CLAIM"
    assert result["execution_trace"]["events"][-1]["stage"] == "CLAIM_PARSE"
    assert result["export_scope"] == {
        "route": "FORECAST",
        "reason_code": "EXPORT_FORECAST_CLAIM",
    }
