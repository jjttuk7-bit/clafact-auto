import json
from datetime import date

from core.admission_recovery import recover_registry_record
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _Extractor:
    def __init__(self) -> None:
        self.inputs: list[str] = []

    def extract(self, source_sentence: str, *, article_published_at: date | None = None) -> ClaimSchema:
        self.inputs.append(source_sentence)
        return ClaimSchema(
            claim_id="placeholder",
            source_sentence=source_sentence,
            indicator="고용률",
            value=60,
            unit="%",
            time="2024년",
            frequency="년",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        )


class _OfficialService:
    def __init__(self) -> None:
        self.claims: list[ClaimSchema] = []

    def resolve(self, claim: ClaimSchema, *, article_date: date) -> object:
        self.claims.append(claim)
        return {"claim_id": claim.claim_id, "article_date": article_date.isoformat()}


def _record(*, source_sentence: str, parse_status: str = "HOLD", parse_reason: str | None = None) -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="article-1",
        sentence_id="sentence-1",
        article_published_at=date(2025, 1, 10),
        source_ref="registry",
        claim=ClaimSchema(
            claim_id="parent-claim",
            source_sentence=source_sentence,
            parse_status=parse_status,
            parse_reason=parse_reason,
        ),
    )


def test_multi_claim_recovery_creates_children_re_admits_and_resolves_each_child() -> None:
    extractor = _Extractor()
    service = _OfficialService()

    result = recover_registry_record(
        _record(source_sentence="2023년 고용률은 60%였고 2024년 고용률은 61%였다."),
        extractor=extractor,
        official_service=service,
    )

    assert result.recovery_action == "MULTI_CLAIM_SPLIT"
    assert [entry.parent_claim_id for entry in result.entries] == ["parent-claim", "parent-claim"]
    assert [entry.admission_route for entry in result.entries] == ["KOSIS_PIPELINE_ELIGIBLE"] * 2
    assert len(service.claims) == 2
    assert all(entry.official_resolution is not None for entry in result.entries)


def test_context_recovery_reparses_bounded_article_context_then_resolves_child() -> None:
    extractor = _Extractor()
    service = _OfficialService()

    result = recover_registry_record(
        _record(
            source_sentence="지난달 고용률은 60%였다.",
            parse_reason="'지난달'의 기준 시점이 제공되지 않아 시간을 확정할 수 없음",
        ),
        extractor=extractor,
        official_service=service,
        article_context="고용동향 발표. 2024년 12월 기준 지난달 고용률은 60%였다. 전국 기준이다.",
    )

    assert result.recovery_action == "CONTEXT_REPARSE"
    assert len(result.entries) == 1
    assert result.entries[0].admission_route == "KOSIS_PIPELINE_ELIGIBLE"
    prompt = json.loads(extractor.inputs[0])
    assert prompt["target_sentence"] == "지난달 고용률은 60%였다."
    assert prompt["article_context"] == "고용동향 발표. 2024년 12월 기준 지난달 고용률은 60%였다. 전국 기준이다."
    assert len(service.claims) == 1
