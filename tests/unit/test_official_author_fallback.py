from datetime import date
import hashlib

from core.official_author_fallback import KostatOfficialReleaseAdapter
from core.kosis_publication import PublicationEvidence
from core.kostat_release_value_fetcher import KostatReleaseDocument
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def _claim() -> ClaimSchema:
    return ClaimSchema(claim_id="rice", source_sentence="", indicator="벼 재배면적", value=1.0, unit="ha", time="2025년", region="한국", parse_status="AUTO_OK")


class Search:
    def find(self, *_args):
        return PublicationEvidence(status="VERIFIED", source_url="https://kostat.go.kr/release")


class Retriever:
    def __init__(self, document): self.document = document
    def fetch_document(self, **_kwargs): return self.document


def _document() -> KostatReleaseDocument:
    raw = b"%PDF-test"
    return KostatReleaseDocument(
        release_url="https://kostat.go.kr/release", source_url="https://kostat.go.kr/release.pdf",
        published_at=date(2025, 8, 28), document_hash="sha256:" + hashlib.sha256(raw).hexdigest(),
        retrieved_at="2025-08-28T00:00:00Z", document_bytes=raw,
    )


def test_national_claim_rejects_north_korea_document_scope(monkeypatch) -> None:
    monkeypatch.setattr("core.kosis_publication.extract_official_release_value", lambda *_args, **_kwargs: 1.0)
    monkeypatch.setattr("core.kostat_release_value_fetcher._extract_pdf_text", lambda _raw: "북한 2025년 벼 재배면적 1 ha")
    monkeypatch.setattr("core.kostat_release_value_fetcher.extract_unambiguous_release_value", lambda *_args, **_kwargs: 1.0)
    adapter = KostatOfficialReleaseAdapter(release_search=Search(), document_fetcher=Retriever(_document()))
    result = adapter.fetch(claim=_claim(), concept=StandardConceptSchema(concept_id="c", canonical_name="c", standard_key="crop_area", status="MATCHED"), indicator_search_terms=("재배면적",), article_date=date(2025, 9, 1))
    assert result is None


def test_national_claim_rejects_provincial_document_scope(monkeypatch) -> None:
    monkeypatch.setattr("core.kosis_publication.extract_official_release_value", lambda *_args, **_kwargs: 1.0)
    monkeypatch.setattr("core.kostat_release_value_fetcher._extract_pdf_text", lambda _raw: "전라남도 2025년 벼 재배면적 1 ha")
    monkeypatch.setattr("core.kostat_release_value_fetcher.extract_unambiguous_release_value", lambda *_args, **_kwargs: 1.0)
    adapter = KostatOfficialReleaseAdapter(release_search=Search(), document_fetcher=Retriever(_document()))
    result = adapter.fetch(claim=_claim(), concept=StandardConceptSchema(concept_id="c", canonical_name="c", standard_key="crop_area", status="MATCHED"), indicator_search_terms=("재배면적",), article_date=date(2025, 9, 1))
    assert result is None

def test_national_value_context_allows_province_appendix(monkeypatch) -> None:
    monkeypatch.setattr("core.kosis_publication.extract_official_release_value", lambda *_args, **_kwargs: 1.0)
    monkeypatch.setattr("core.kostat_release_value_fetcher.extract_unambiguous_release_value", lambda *_args, **_kwargs: 1.0)
    monkeypatch.setattr("core.kostat_release_value_fetcher._extract_pdf_text", lambda _raw: "전국 2025년 벼 재배면적 1 ha. 부록 전라남도 수치")
    adapter = KostatOfficialReleaseAdapter(release_search=Search(), document_fetcher=Retriever(_document()))
    result = adapter.fetch(claim=_claim(), concept=StandardConceptSchema(concept_id="c", canonical_name="c", standard_key="crop_area", status="MATCHED"), indicator_search_terms=("재배면적",), article_date=date(2025, 9, 1))
    assert result is not None


def test_incidental_korea_mention_is_not_a_national_scope(monkeypatch) -> None:
    monkeypatch.setattr("core.kosis_publication.extract_official_release_value", lambda *_args, **_kwargs: 1.0)
    monkeypatch.setattr("core.kostat_release_value_fetcher.extract_unambiguous_release_value", lambda *_args, **_kwargs: 1.0)
    monkeypatch.setattr("core.kostat_release_value_fetcher._extract_pdf_text", lambda _raw: "한국 통계 설명. 2025년 벼 재배면적 1 ha")
    adapter = KostatOfficialReleaseAdapter(release_search=Search(), document_fetcher=Retriever(_document()))
    result = adapter.fetch(claim=_claim(), concept=StandardConceptSchema(concept_id="c", canonical_name="c", standard_key="crop_area", status="MATCHED"), indicator_search_terms=("재배면적",), article_date=date(2025, 9, 1))
    assert result is None

def test_kostat_search_includes_structured_crop_dimension() -> None:
    class RecordingSearch:
        def __init__(self) -> None:
            self.stats_name: str | None = None
        def find(self, stats_name, *_args):
            self.stats_name = stats_name
            return None

    search = RecordingSearch()
    claim = _claim().model_copy(update={"indicator": "재배면적", "dimension": {"작물": "벼"}})
    adapter = KostatOfficialReleaseAdapter(release_search=search, document_fetcher=Retriever(None))

    result = adapter.fetch(
        claim=claim,
        concept=StandardConceptSchema(concept_id="c", canonical_name="c", standard_key="crop_area", status="MATCHED"),
        indicator_search_terms=("재배면적",),
        article_date=date(2025, 9, 1),
    )

    assert result is None
    assert search.stats_name == "벼 재배면적"

def test_document_level_explicit_national_sampling_declaration_validates_value_scope() -> None:
    from core.official_author_fallback import _document_scope_for_value

    text = (
        "조사체계 및 방법: 전국 21,743개 표본조사구를 현지에서 실측 조사. "
        "2025년 벼 재배면적은 677,597ha이다."
    )

    assert _document_scope_for_value(
        text, period="2025", indicator="벼 재배면적", value=677_597.0, unit="ha"
    ) == "national"


def test_document_level_without_explicit_national_declaration_rejects_unscoped_value() -> None:
    from core.official_author_fallback import _document_scope_for_value

    text = "표본조사구를 현지에서 실측 조사. 2025년 벼 재배면적은 677,597ha이다."

    assert _document_scope_for_value(
        text, period="2025", indicator="벼 재배면적", value=677_597.0, unit="ha"
    ) is None