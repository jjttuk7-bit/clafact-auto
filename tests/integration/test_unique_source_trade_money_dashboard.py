from datetime import date
from types import SimpleNamespace

from core.unified_claim_pipeline import verify_article
from schemas.claim import ClaimSchema


class _MisscaledExtractor:
    def extract(self, source_sentence: str, **kwargs) -> ClaimSchema:
        return ClaimSchema(
            claim_id="misscaled-dashboard-money",
            source_sentence=source_sentence,
            indicator="무역 수지",
            value=10.56,
            unit="십억 달러",
            time=None,
            frequency="연간 누계",
            calculation="DIRECT_VALUE",
            condition={"direction": "DECREASE", "sign": "DEFICIT"},
            parse_status="HOLD",
            parse_reason="MISSING_REQUIRED_SLOTS:time",
        )


class _OfficialService:
    def __init__(self) -> None:
        self.claims: list[ClaimSchema] = []

    def resolve(self, claim: ClaimSchema, *, article_date: date):
        self.claims.append(claim)
        return SimpleNamespace(
            verdict=SimpleNamespace(route_status="AUTO", reason_code=None)
        )


def test_dashboard_repairs_misscaled_money_before_official_lookup() -> None:
    service = _OfficialService()

    result = verify_article(
        "연간 누계 무역 수지는 10억5600만달러 적자다.",
        article_published_at=date(2025, 2, 21),
        extractor=_MisscaledExtractor(),
        official_service=service,
    )

    claim = result.entries[0].claim
    assert claim.value == -1_056_000_000
    assert claim.unit == "달러"
    assert claim.time == "2025-01-01/2025-02-20"
    assert claim.frequency == "CUMULATIVE_PERIOD"
    assert claim.parse_status == "AUTO_OK"
    assert len(service.claims) == 1
