from __future__ import annotations

import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from streamlit.testing.v1 import AppTest

from schemas.claim import ClaimSchema


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app" / "streamlit_app.py"


def _set_provider_environment(
    monkeypatch,
    *,
    claim_provider: str,
    kosis_api_key: str = "",
    hcx_api_key: str = "",
    openai_api_key: str = "",
    hcx_extraction_mode: str = "structured_output",
) -> None:
    monkeypatch.setenv("CLAFACT_CLAIM_PROVIDER", claim_provider)
    monkeypatch.setenv("KOSIS_API_KEY", kosis_api_key)
    monkeypatch.setenv("HCX_API_KEY", hcx_api_key)
    monkeypatch.setenv("OPENAI_API_KEY", openai_api_key)
    monkeypatch.setenv("CLAFACT_HCX_EXTRACTION_MODE", hcx_extraction_mode)
    monkeypatch.setenv("CLAFACT_LLM_VERDICT_EXPLANATION_ENABLED", "false")


def _metric_values(app: AppTest) -> dict[str, str]:
    return {metric.label: metric.value for metric in app.metric}

@pytest.mark.parametrize(
    ("parse_status", "parse_reason"),
    [("HOLD", "SOURCE_CONTEXT_UNCLEAR"), ("HUMAN_REVIEW", "MULTIPLE_PLAUSIBLE_INTERPRETATIONS")],
)
def test_single_claim_preserves_parse_review_route_without_downstream_calls(
    monkeypatch, parse_status: str, parse_reason: str,
) -> None:
    _set_provider_environment(monkeypatch, claim_provider="openai", openai_api_key="openai-secret")

    class FakeExtractor:
        last_provider = "openai"

        def extract(self, source_sentence: str) -> ClaimSchema:
            return ClaimSchema(
                claim_id="review-claim", source_sentence=source_sentence,
                indicator="고용률", value=70, unit="%", time="2024", frequency="YEAR",
                region="전국", population="15세 이상 인구", dimension={"sex": "전체"},
                comparison={"basis": "전년"}, calculation="DIRECT_VALUE",
                condition={"seasonal_adjustment": "원계열"}, source_hint="KOSIS",
                parse_status=parse_status, parse_reason=parse_reason,
            )

    downstream_targets = (
        "core.cpi_growth_resolver.resolve_cpi_growth_plan",
        "core.growth_verdict.make_cpi_growth_verdict",
        "core.semantic_normalizer.normalize_concept",
        "core.catalog_search.search_semantic_catalog",
        "core.catalog_binding.apply_catalog_binding",
        "core.catalog_discovery.discover_catalog_candidates",
        "core.semantic_matcher.semantic_match",
        "core.kosis_fetcher.OfficialValueFetcher",
        "core.evidence_resolver.resolve_evidence_cell",
        "core.calculator.calculate",
    )
    downstream_mocks: list[MagicMock] = []
    with ExitStack() as stack:
        stack.enter_context(patch("core.claim_extractor_factory.create_claim_extractor", return_value=FakeExtractor()))
        for target in downstream_targets:
            downstream_mocks.append(stack.enter_context(patch(target)))
        app = AppTest.from_file("app/streamlit_app.py", default_timeout=15)
        app.run()
        app.text_area[0].input("2024년 전국 고용률은 70%였다.")
        app.text_input[0].input("2025-06-26")
        app.button[0].click()
        app.run()

    assert all(mock.call_count == 0 for mock in downstream_mocks)
    metrics = _metric_values(app)
    assert metrics["파싱 상태"] == {"HOLD": "보류", "HUMAN_REVIEW": "사람 검토 필요"}[parse_status]
    assert metrics["판정"] == "판정 보류"
    assert metrics["경로"] == {"HOLD": "보류", "HUMAN_REVIEW": "사람 검토 필요"}[parse_status]
    assert any(element.label == "구조화된 주장 상세" for element in app.expander)
    assert any(element.label == "판정 상세 JSON" for element in app.expander)
    assert any(element.value == "검토 콘솔 전달 데이터" for element in app.subheader)
    rendered_json = " ".join(str(element.value) for element in app.json)
    assert parse_status in rendered_json
    assert parse_reason in rendered_json


def test_streamlit_entrypoint_imports_core_when_only_app_directory_is_on_path() -> None:
    """Streamlit Cloud executes the app module from app/, not the repository root."""
    command = f"""
import runpy
import sys
from pathlib import Path

project_root = Path({str(PROJECT_ROOT)!r})
app_path = Path({str(APP_PATH)!r})
sys.path[:] = [str(app_path.parent)] + [
    entry for entry in sys.path if entry not in ("", str(project_root))
]
runpy.run_path(str(app_path), run_name="__streamlit_cloud_test__")
"""

    result = subprocess.run(
        [sys.executable, "-c", command],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr


def test_streamlit_mvp_renders_and_holds_invalid_article_date() -> None:
    app = AppTest.from_file("app/streamlit_app.py")
    app.run()
    assert app.title[0].value == "CLAFACT-AUTO"
    app.text_area[0].input("2024년 전국 고용률은 70%였다.")
    app.text_input[0].input("invalid-date")
    app.button[0].click()
    app.run()
    assert any("보류: 기사 기준일은 YYYY-MM-DD 형식이어야 합니다." in element.value for element in app.error)

def test_streamlit_mvp_displays_openai_and_fallback_connection_status(monkeypatch) -> None:
    _set_provider_environment(
        monkeypatch,
        claim_provider="openai",
        kosis_api_key="kosis-secret",
        hcx_api_key="hcx-secret",
        openai_api_key="openai-secret",
    )
    app = AppTest.from_file("app/streamlit_app.py", default_timeout=15)
    app.run()

    assert app.subheader[0].value == "운영 연결 상태"
    assert _metric_values(app) == {
        "KOSIS API": "연결됨",
        "OpenAI 함수 호출": "연결됨",
        "HCX 예비 처리": "연결됨",
    }
    rendered_text = " ".join(
        [*(metric.label + metric.value for metric in app.metric), *(item.value for item in app.caption)]
    )
    assert "kosis-secret" not in rendered_text
    assert "hcx-secret" not in rendered_text
    assert "openai-secret" not in rendered_text
    assert "OpenAI API 키 지문: 설정됨 (SHA-256: 9cbbbfb350d0)" in rendered_text


def test_streamlit_mvp_preserves_hcx_primary_status(monkeypatch) -> None:
    _set_provider_environment(
        monkeypatch,
        claim_provider="hcx",
        hcx_api_key="hcx-secret",
        openai_api_key="",
        hcx_extraction_mode="function_calling",
    )
    app = AppTest.from_file("app/streamlit_app.py", default_timeout=15)
    app.run()

    assert _metric_values(app) == {
        "KOSIS API": "미설정",
        "HCX 함수 호출": "연결됨",
    }


def test_streamlit_mvp_marks_unsupported_claim_provider_as_configuration_error(monkeypatch) -> None:
    _set_provider_environment(
        monkeypatch,
        claim_provider="local",
        hcx_api_key="hcx-secret",
        openai_api_key="openai-secret",
    )
    app = AppTest.from_file("app/streamlit_app.py", default_timeout=15)
    app.run()

    assert _metric_values(app) == {
        "KOSIS API": "미설정",
        "지원하지 않는 Provider": "설정 오류",
    }


def test_factory_value_error_is_not_reported_as_invalid_article_date(monkeypatch) -> None:
    _set_provider_environment(
        monkeypatch,
        claim_provider="hcx",
        hcx_api_key="hcx-secret",
    )

    with patch(
        "core.claim_extractor_factory.create_claim_extractor",
        side_effect=ValueError("CLAIM_PROVIDER_UNSUPPORTED"),
    ):
        app = AppTest.from_file("app/streamlit_app.py", default_timeout=15)
        app.run()
        app.text_area[0].input("2024년 전국 고용률은 70%였다.")
        app.text_input[0].input("2025-06-26")
        app.button[0].click()
        app.run()

    errors = [element.value for element in app.error]
    assert "보류: ValueError" in errors
    assert "보류: 기사 기준일은 YYYY-MM-DD 형식이어야 합니다." not in errors


def test_single_claim_reuses_extractor_and_shows_actual_fallback_provider(monkeypatch) -> None:
    _set_provider_environment(
        monkeypatch,
        claim_provider="openai",
        hcx_api_key="hcx-secret",
        openai_api_key="openai-secret",
    )

    class FakeFallbackExtractor:
        last_provider = "hcx"

        def extract(self, source_sentence: str) -> ClaimSchema:
            return ClaimSchema(
                claim_id="temporary",
                source_sentence=source_sentence,
                indicator="고용률",
                value=70,
                unit="%",
                time="2024",
                parse_status="AUTO_OK",
            )

    extractor = FakeFallbackExtractor()
    factory_calls = 0

    def create_fake_extractor(settings):
        nonlocal factory_calls
        factory_calls += 1
        return extractor

    with patch(
        "core.claim_extractor_factory.create_claim_extractor",
        side_effect=create_fake_extractor,
    ):
        app = AppTest.from_file("app/streamlit_app.py", default_timeout=15)
        app.run()
        app.text_area[0].input("2024년 전국 고용률은 70%였다.")
        app.text_input[0].input("2025-06-26")
        app.button[0].click()
        app.run()

    assert factory_calls == 1
    assert _metric_values(app)["실제 주장 추출기"] == "HCX"


@pytest.mark.parametrize(
    ("claim_provider", "last_provider", "expected_label"),
    [
        ("openai", None, "OpenAI"),
        ("hcx", "unexpected-provider", "HCX"),
    ],
)
def test_single_claim_normalizes_selected_provider_when_actual_provider_is_unavailable(
    monkeypatch,
    claim_provider: str,
    last_provider: str | None,
    expected_label: str,
) -> None:
    _set_provider_environment(
        monkeypatch,
        claim_provider=claim_provider,
        hcx_api_key="hcx-secret",
        openai_api_key="openai-secret",
        hcx_extraction_mode="function_calling",
    )

    class FakeDirectExtractor:
        def extract(self, source_sentence: str) -> ClaimSchema:
            return ClaimSchema(
                claim_id="temporary",
                source_sentence=source_sentence,
                indicator="고용률",
                value=70,
                unit="%",
                time="2024",
                parse_status="AUTO_OK",
            )

    extractor = FakeDirectExtractor()
    if last_provider is not None:
        extractor.last_provider = last_provider

    with patch(
        "core.claim_extractor_factory.create_claim_extractor",
        return_value=extractor,
    ):
        app = AppTest.from_file("app/streamlit_app.py", default_timeout=15)
        app.run()
        app.text_area[0].input("2024년 전국 고용률은 70%였다.")
        app.text_input[0].input("2025-06-26")
        app.button[0].click()
        app.run()

    assert _metric_values(app)["실제 주장 추출기"] == expected_label


def test_streamlit_mvp_renders_batch_upload_control() -> None:
    app = AppTest.from_file("app/streamlit_app.py")
    app.run()

    assert app.file_uploader[0].label == "크롤링 뉴스 파일 업로드"


def test_streamlit_mvp_renders_batch_default_article_date_input() -> None:
    app = AppTest.from_file("app/streamlit_app.py")
    app.run()

    assert any(widget.label == "배치 기본 기사 기준일 (선택)" for widget in app.text_input)
