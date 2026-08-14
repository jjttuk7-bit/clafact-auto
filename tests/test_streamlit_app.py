from __future__ import annotations

import subprocess
import sys
import runpy
from contextlib import ExitStack
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import config.settings as settings_module
from schemas.claim import ClaimSchema
from schemas.candidate import KosisCandidateSchema
from schemas.concept import StandardConceptSchema
from core.kosis_publication import PublicationEvidence


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
    monkeypatch.setattr(settings_module, "_ENV_PATH", Path("missing-test.env"))
    monkeypatch.setenv("CLAFACT_CLAIM_PROVIDER", claim_provider)
    monkeypatch.setenv("KOSIS_API_KEY", kosis_api_key)
    monkeypatch.setenv("HCX_API_KEY", hcx_api_key)
    monkeypatch.setenv("OPENAI_API_KEY", openai_api_key)
    monkeypatch.setenv("CLAFACT_HCX_EXTRACTION_MODE", hcx_extraction_mode)
    monkeypatch.setenv("CLAFACT_LLM_VERDICT_EXPLANATION_ENABLED", "false")


def _metric_values(app: AppTest) -> dict[str, str]:
    return {metric.label: metric.value for metric in app.metric}


def test_single_claim_catalog_hydration_uses_interactive_candidate_budget() -> None:
    candidate = KosisCandidateSchema(
        org_id="145",
        tbl_id="DT_EXPORT",
        tbl_name="중고차 수출액",
        metadata_status="LIVE_SEARCH_UNRESOLVED",
    )
    claim = ClaimSchema(
        claim_id="EXPORT-Q1",
        source_sentence="2024년 1분기 중고차 수출액은 증가했다.",
        indicator="수출액",
        value=31,
        unit="%",
        time="2024년 1분기",
        frequency="분기",
        dimension={"상품": "중고차"},
        parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="C000003",
        canonical_name="수출액",
        standard_key="export_value",
        status="MATCHED",
    )
    settings = MagicMock(kosis_api_key="secret")

    with ExitStack() as stack:
        stack.enter_context(
            patch("core.catalog_search.search_semantic_catalog", return_value=[candidate])
        )
        stack.enter_context(
            patch("core.catalog_discovery.discover_catalog_candidates", return_value=[candidate])
        )
        refresh = stack.enter_context(
            patch("core.catalog_metadata_refresh.refresh_item_metadata", return_value=[candidate])
        )
        namespace = runpy.run_path(str(APP_PATH), run_name="__catalog_budget_test__")
        namespace["_find_catalog_candidates"](claim, concept, settings)

    refresh.assert_called_once_with(
        [candidate],
        "secret",
        metadata_fetcher=namespace["_official_metadata_repository"](),
        max_candidates=None,
        time_budget_seconds=45.0,
        retries=2,
        timeout_seconds=10,
    )


def test_catalog_transport_failure_is_not_misreported_as_no_evidence() -> None:
    claim = ClaimSchema(
        claim_id="CPI-CABBAGE",
        source_sentence="2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다.",
        indicator="물가",
        value=-34.5,
        unit="%",
        time="2025년 10월",
        frequency="MONTHLY",
        dimension={"item": "배추"},
        comparison={"type": "YEAR_OVER_YEAR"},
        calculation="GROWTH_RATE",
        condition={"direction": "DECREASE"},
        parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="UNRESOLVED",
        canonical_name="UNRESOLVED",
        standard_key="unresolved",
        status="UNRESOLVED",
    )
    settings = MagicMock(kosis_api_key="secret")
    failed_search = MagicMock(attempted_queries=2, failed_queries=2)

    with ExitStack() as stack:
        stack.enter_context(
            patch("core.catalog_search.search_semantic_catalog", return_value=[])
        )
        stack.enter_context(
            patch("core.kosis_live_catalog.KosisLiveCatalogSearch", return_value=failed_search)
        )
        stack.enter_context(
            patch("core.catalog_discovery.discover_catalog_candidates", return_value=[])
        )
        namespace = runpy.run_path(str(APP_PATH), run_name="__catalog_failure_test__")
        with pytest.raises(RuntimeError, match="KOSIS_CATALOG_UNAVAILABLE"):
            namespace["_find_catalog_candidates"](claim, concept, settings)



def test_official_runtime_dependencies_do_not_use_static_snapshots() -> None:
    api_lookup = MagicMock()
    with patch("core.kosis_api_adapter.build_kosis_api_lookup", return_value=api_lookup):
        namespace = runpy.run_path(str(APP_PATH), run_name="__live_runtime_test__")
        namespace["_official_metadata_repository"].clear()
        repository = namespace["_official_metadata_repository"]()
        settings = MagicMock(kosis_api_key="secret")
        value_fetcher = namespace["_official_fetcher"](settings)

    assert tuple(repository._snapshot_paths) == ()
    assert value_fetcher._snapshot_paths == []
    assert value_fetcher._prefer_api is True
    assert value_fetcher._require_verified_release_metadata is True
    assert value_fetcher._publication_lookup is not None


def test_catalog_metadata_failure_returns_holdable_candidates() -> None:
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_CPI",
        tbl_name="품목별 소비자물가지수",
        metadata_status="OFFICIAL_ITEM_METADATA_UNAVAILABLE",
    )
    claim = ClaimSchema(
        claim_id="CPI-CABBAGE",
        source_sentence="2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다.",
        indicator="물가",
        value=-34.5,
        unit="%",
        time="2025년 10월",
        frequency="MONTHLY",
        dimension={"item": "배추"},
        comparison={"type": "YEAR_OVER_YEAR"},
        calculation="GROWTH_RATE",
        condition={"direction": "DECREASE"},
        parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="UNRESOLVED",
        canonical_name="UNRESOLVED",
        standard_key="unresolved",
        status="UNRESOLVED",
    )
    settings = MagicMock(kosis_api_key="secret")

    with ExitStack() as stack:
        stack.enter_context(
            patch("core.catalog_search.search_semantic_catalog", return_value=[])
        )
        stack.enter_context(
            patch("core.catalog_discovery.discover_catalog_candidates", return_value=[candidate])
        )
        stack.enter_context(
            patch("core.catalog_metadata_refresh.refresh_item_metadata", return_value=[candidate])
        )
        namespace = runpy.run_path(str(APP_PATH), run_name="__metadata_failure_test__")
        with pytest.raises(RuntimeError, match="KOSIS_METADATA_UNAVAILABLE"):
            namespace["_find_catalog_candidates"](claim, concept, settings)

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

        def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
            return ClaimSchema(
                claim_id="review-claim", source_sentence=source_sentence,
                indicator="고용률", value=70, unit="%", time="2024", frequency="YEAR",
                region="전국", population="15세 이상 인구", dimension={"sex": "전체"},
                comparison={"basis": "전년"}, calculation="DIRECT_VALUE",
                condition={"seasonal_adjustment": "원계열"}, source_hint="KOSIS",
                parse_status=parse_status, parse_reason=parse_reason,
            )

    downstream_targets = (        "core.semantic_normalizer.normalize_concept",
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
    assert metrics["경로"] == "보류"
    assert any(element.label == "구조화된 주장 상세" for element in app.expander)
    assert any(element.label == "판정 상세 JSON" for element in app.expander)
    assert any(element.value == "검토 콘솔 전달 데이터" for element in app.subheader)
    rendered_json = " ".join(str(element.value) for element in app.json)
    assert parse_status in rendered_json
    assert parse_reason in rendered_json



def test_unresolved_concept_holds_at_semantic_mapping_without_catalog(
    monkeypatch,
) -> None:
    _set_provider_environment(
        monkeypatch,
        claim_provider="openai",
        openai_api_key="openai-secret",
    )

    class FakeExtractor:
        last_provider = "openai"

        def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
            return ClaimSchema(
                claim_id="unresolved-claim",
                source_sentence=source_sentence,
                indicator="완전히 미등록된 지표",
                value=12.3,
                unit="%",
                time="2025년 10월",
                frequency="MONTHLY",
                dimension={"product": "가상 품목"},
                calculation="DIRECT_VALUE",
                parse_status="AUTO_OK",
            )

    with (
        patch(
            "core.claim_extractor_factory.create_claim_extractor",
            return_value=FakeExtractor(),
        ),
        patch(
            "core.catalog_search.search_semantic_catalog",
            side_effect=AssertionError("Catalog must not run for an unresolved Concept"),
        ),
    ):
        app = AppTest.from_file("app/streamlit_app.py", default_timeout=30)
        app.run()
        app.text_area[0].input("2025년 10월 완전히 미등록된 지표는 12.3%였다.")
        app.text_input[0].input("2025-11-04")
        app.button[0].click()
        app.run()

    assert not app.exception
    metrics = _metric_values(app)
    assert metrics["판정"] == "판정 보류"
    assert metrics["경로"] == "보류"
    rendered_json = " ".join(str(element.value) for element in app.json)
    assert "CONCEPT_NOT_FOUND" in rendered_json
    assert "SEMANTIC_MAPPING" in rendered_json
    assert "CATALOG_SEARCH" not in rendered_json

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
    metrics = _metric_values(app)
    assert {
        key: metrics[key]
        for key in ("KOSIS API", "OpenAI 함수 호출", "HCX 예비 처리")
    } == {
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

    metrics = _metric_values(app)
    assert {key: metrics[key] for key in ("KOSIS API", "HCX 함수 호출")} == {
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

    metrics = _metric_values(app)
    assert {
        key: metrics[key]
        for key in ("KOSIS API", "지원하지 않는 Provider")
    } == {
        "KOSIS API": "미설정",
        "지원하지 않는 Provider": "설정 오류",
    }


def test_factory_value_error_is_not_reported_as_invalid_article_date(monkeypatch) -> None:
    _set_provider_environment(
        monkeypatch,
        claim_provider="hcx",
        hcx_api_key="hcx-secret",
    )

    with (
        patch(
            "core.claim_extractor_factory.create_claim_extractor",
            side_effect=ValueError("CLAIM_PROVIDER_UNSUPPORTED"),
        ),
        patch("core.operational_error._diagnostic_id", return_value="diag12345678"),
    ):
        app = AppTest.from_file("app/streamlit_app.py", default_timeout=15)
        app.run()
        app.text_area[0].input("2024년 전국 고용률은 70%였다.")
        app.text_input[0].input("2025-06-26")
        app.button[0].click()
        app.run()

    errors = [element.value for element in app.error]
    assert "보류: CLAIM_PARSE 단계 처리 오류 · 진단 ID diag12345678" in errors
    assert "보류: 기사 기준일은 YYYY-MM-DD 형식이어야 합니다." not in errors


def test_single_claim_reports_parse_exception_with_safe_stage_reference(monkeypatch) -> None:
    _set_provider_environment(
        monkeypatch,
        claim_provider="openai",
        openai_api_key="openai-secret",
    )

    with (
        patch(
            "core.claim_extractor_factory.create_claim_extractor",
            side_effect=TypeError("openai-secret must not be rendered"),
        ),
        patch("core.operational_error._diagnostic_id", return_value="diag12345678"),
    ):
        app = AppTest.from_file("app/streamlit_app.py", default_timeout=15)
        app.run()
        app.text_area[0].input("올해 1분기 중고차 수출액은 지난해보다 31% 증가했다.")
        app.text_input[0].input("2024-04-30")
        app.button[0].click()
        app.run()

    errors = [element.value for element in app.error]
    assert errors == ["보류: CLAIM_PARSE 단계 처리 오류 · 진단 ID diag12345678"]
    assert "openai-secret must not be rendered" not in " ".join(errors)


@pytest.mark.parametrize(
    ("failure_target", "expected_stage"),
    [
        ("core.official_engine_factory.discover_catalog_candidates", "KOSIS_CATALOG"),
        ("core.dynamic_kosis_verifier.verify_claim_against_kosis", "VERIFICATION"),
        ("core.verdict_explainer.explain_verdict", "VERDICT_EXPLANATION"),
    ],
)
def test_single_claim_reports_downstream_exception_stage(
    monkeypatch, failure_target: str, expected_stage: str,
) -> None:
    _set_provider_environment(
        monkeypatch,
        claim_provider="openai",
        openai_api_key="openai-secret",
    )

    class FakeExtractor:
        last_provider = "openai"

        def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
            return ClaimSchema(
                claim_id="temporary",
                source_sentence=source_sentence,
                indicator="수출액",
                value=31,
                unit="%",
                time="2024년 1분기",
                frequency="분기",
                calculation="GROWTH_RATE",
                comparison={"type": "YEAR_OVER_YEAR"},
                condition={"direction": "INCREASE"},
                parse_status="AUTO_OK",
            )

    with (
        patch(
            "core.claim_extractor_factory.create_claim_extractor",
            return_value=FakeExtractor(),
        ),
        patch(failure_target, side_effect=TypeError("must not be rendered")),
        patch("core.operational_error._diagnostic_id", return_value="diag12345678"),
    ):
        app = AppTest.from_file("app/streamlit_app.py", default_timeout=15)
        app.run()
        app.text_area[0].input("2024년 1분기 수출액은 지난해보다 31% 증가했다.")
        app.text_input[0].input("2024-04-30")
        app.button[0].click()
        app.run()

    errors = [element.value for element in app.error]
    assert errors == [
        f"보류: {expected_stage} 단계 처리 오류 · 진단 ID diag12345678"
    ]


def test_single_claim_reuses_extractor_and_shows_actual_fallback_provider(monkeypatch) -> None:
    _set_provider_environment(
        monkeypatch,
        claim_provider="openai",
        hcx_api_key="hcx-secret",
        openai_api_key="openai-secret",
    )

    class FakeFallbackExtractor:
        last_provider = "hcx"

        def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
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
        def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
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


def test_streamlit_operator_panel_uses_configured_run_directory(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "internal-run"
    run_dir.mkdir()
    (run_dir / "coverage_and_e2e_report.json").write_text(
        '{"route_counts":{"AUTO":5,"HOLD":1}}', encoding="utf-8"
    )
    (run_dir / "claim_verification_results.jsonl").write_text(
        '{"claim_id":"C1","route_status":"AUTO"}\n', encoding="utf-8"
    )
    review_dir = run_dir / "review_queues"
    review_dir.mkdir()
    (review_dir / "parse.jsonl").write_text(
        '{"claim_id":"C2","reason_code":"CLAIM_PARSE_UNCERTAIN"}\n', encoding="utf-8"
    )
    (run_dir / "claim_verification_results.csv").write_text("claim_id\nC1\n", encoding="utf-8")
    (run_dir / "claim_verification_results.xlsx").write_bytes(b"xlsx")
    monkeypatch.setenv("CLAFACT_INTERNAL_RUN_DIR", str(run_dir))

    app = AppTest.from_file("app/streamlit_app.py", default_timeout=20)
    app.run()

    assert not app.exception
    assert any(item.value == "내부 검증 MVP 실행 결과" for item in app.subheader)
    labels = {item.label for item in app.download_button}
    assert {"보류 검토 큐 JSON 다운로드", "전체 결과 CSV 다운로드", "전체 결과 XLSX 다운로드"} <= labels



def test_cabbage_cpi_single_and_batch_paths_share_auto_result(monkeypatch) -> None:
    _set_provider_environment(
        monkeypatch,
        claim_provider="openai",
        kosis_api_key="kosis-test-key",
        openai_api_key="openai-secret",
    )

    class FakeCpiExtractor:
        last_provider = "openai"

        def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
            return ClaimSchema(
                claim_id="claim_eeb4134b7158445d",
                source_sentence=source_sentence,
                indicator="물가",
                value=-34.5,
                unit="%",
                time="2025년 10월",
                frequency="MONTHLY",
                dimension={"product": "배추"},
                comparison={
                    "type": "YEAR_OVER_YEAR",
                    "reference_period": "전년 동월",
                },
                calculation="GROWTH_RATE",
                condition={"direction": "DECREASE"},
                parse_status="AUTO_OK",
            )

    table_identity = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_1J22112",
        tbl_name="품목별 소비자물가지수",
        metadata_status="LIVE_SEARCH_UNRESOLVED",
    )
    hydrated = table_identity.model_copy(update={
        "core_item_ids": ["T"],
        "core_item_names": ["소비자물가지수"],
        "dimension_ids": ["C", "I"],
        "dimension_names": ["지역", "품목"],
        "dimension_members": {"C": ["전국"], "I": ["배추"]},
        "dimension_member_codes": {
            "C": {"전국": "T10"},
            "I": {"배추": "A02A01701"},
        },
        "unit_names": ["2020=100"],
        "item_units": {"T": "2020=100"},
        "frequency": "월|분기|년",
        "metadata_status": "OFFICIAL_METADATA_READY",
    })

    class FakePublicationLookup:
        def __init__(self, _api_key):
            pass

        def fetch(self, _org_id, _table_id, *, period):
            return PublicationEvidence(
                status="VERIFIED", published_at=date(2025, 11, 4),
                source_url="https://kosis.kr/openapi/statisticsExplData.do",
                retrieved_at="2025-11-04T00:00:00Z", content_hash=period.ljust(64, "0"),
            )

    class FakeLiveLookup:
        def __call__(self, cell):
            return self.fetch_many([cell])

        def fetch_many(self, _cells):
            return [
                {
                    "TBL_ID": "DT_1J22112", "ITM_ID": "T",
                    "PRD_DE": "202410", "DT": "208.57",
                    "LST_CHN_DE": "2025-10-30",
                },
                {
                    "TBL_ID": "DT_1J22112", "ITM_ID": "T",
                    "PRD_DE": "202510", "DT": "136.62",
                    "LST_CHN_DE": "2025-10-30",
                },
            ]

    with (
        patch(
            "core.claim_extractor_factory.create_claim_extractor",
            return_value=FakeCpiExtractor(),
        ),
        patch(
            "core.official_engine_factory.discover_catalog_candidates",
            return_value=[table_identity],
        ),
        patch(
            "core.official_engine_factory.refresh_item_metadata_for_claim",
            return_value=[hydrated],
        ),
        patch("core.official_engine_factory.build_kosis_api_lookup", return_value=FakeLiveLookup()),
        patch("core.official_engine_factory.KosisPublicationLookup", FakePublicationLookup),
    ):
        st.cache_data.clear()
        st.cache_resource.clear()
        app = AppTest.from_file("app/streamlit_app.py", default_timeout=40)
        app.run()
        app.text_area[0].input(
            "2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다."
        )
        app.text_input[0].input("2025-11-04")
        app.button[0].click()
        app.run()

        namespace = runpy.run_path(str(APP_PATH), run_name="__cpi_batch_e2e_test__")
        batch_verdict = namespace["_verify_batch_claim"](
            "2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다.",
            date(2025, 11, 4),
            MagicMock(kosis_api_key="kosis-test-key"),
        )

    assert not app.exception
    metrics = _metric_values(app)
    assert metrics["판정"] == "일치"
    assert metrics["경로"] == "자동"
    assert any(element.label == "KOSIS Catalog 진단 (안전 정보)" for element in app.expander)
    rendered_json = " ".join(str(element.value) for element in app.json)
    assert "CPI_DETAIL:A02A01701" in rendered_json
    assert "A02A01701" in rendered_json
    assert "official_value_provenance" in rendered_json

    assert batch_verdict.route_status == "AUTO"
    assert batch_verdict.verdict == "MATCH"
    assert batch_verdict.evidence_values == [136.62, 208.57]
    assert all(
        cell.dimension_codes == {"C": "T10", "I": "A02A01701"}
        for cell in batch_verdict.evidence_cells
    )
    assert [item.source for item in batch_verdict.official_value_provenance] == [
        "API",
        "API",
    ]

def test_streamlit_official_service_uses_shared_engine_factory() -> None:
    sentinel = object()
    settings = MagicMock(kosis_api_key="kosis-test-key")

    with patch(
        "core.official_engine_factory.build_official_evidence_service",
        return_value=sentinel,
    ) as build_service:
        namespace = runpy.run_path(str(APP_PATH), run_name="__shared_engine_factory_test__")
        result = namespace["_official_evidence_service"](settings)

    assert result is sentinel
    paths = build_service.call_args.args[0]
    assert paths.standard_path == namespace["STANDARD_PATH"]
    assert paths.catalog_path == namespace["CATALOG_PATH"]
    assert paths.as_of_metadata_paths == namespace["AS_OF_METADATA_PATHS"]
