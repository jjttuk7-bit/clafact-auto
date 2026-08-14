"""Streamlit MVP for the safe, review-first CLAFACT-AUTO flow."""

from dataclasses import asdict
from datetime import date
from pathlib import Path
import json
import os
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from core.batch_verifier import export_batch_xlsx, load_articles, verify_articles
from core.article_claim_pipeline import parse_article_claims
from core.claim_parser import parse_claim
from core.claim_result_export import export_verdict_json_bytes, export_verdict_xlsx_bytes
from core.claim_extractor_factory import create_claim_extractor
from core.secret_fingerprint import describe_secret_fingerprint
from core.calculator import calculate
from core.catalog_binding import apply_catalog_binding
from core.catalog_discovery import discover_catalog_candidates, has_unresolved_live_metadata
from core.catalog_search import search_semantic_catalog
from core.data_loader import load_kosis_catalog, load_standard_concepts
from core.dynamic_kosis_verifier import verify_claim_against_kosis
from core.evidence_resolver import resolve_evidence_cell
from core.evidence_presentation import build_evidence_rows, build_kosis_table_url
from core.kosis_fetcher import OfficialValueFetcher
from core.kosis_live_catalog import KosisLiveCatalogSearch
from core.kosis_publication import KosisPublicationLookup
from core.catalog_metadata_refresh import refresh_item_metadata
from core.kosis_metadata_repository import KosisMetadataRepository
from core.kosis_api_adapter import build_kosis_api_lookup
from config.settings import Settings
from core.review_handoff import build_review_payload
from core.trace_presentation import build_trace_summary
from core.semantic_matcher import semantic_match
from core.semantic_normalizer import normalize_concept
from core.unit_normalizer import convert_value
from core.verdict_engine import make_verdict
from core.ui_labels import translate_status
from core.verdict_explainer import explain_verdict
from core.operator_artifact_loader import load_operator_run
from core.operational_error import OperationalStageError, run_operational_stage
from core.official_evidence_service import OfficialEvidenceService
from core.official_engine_factory import OfficialEnginePaths, build_official_evidence_service
from core.claim_verification_service import VerificationTraceRecorder
from core.verification_trace import attach_trace
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema
from schemas.evidence import CalculationPlan
from schemas.verdict import VerdictSchema

DATA_ROOT = Path("data")
DEFAULT_INTERNAL_RUN_DIR = Path(os.environ.get("CLAFACT_INTERNAL_RUN_DIR", PROJECT_ROOT / "artifacts" / "internal_validation_mvp_e2e_structured_20260811"))
STANDARD_PATH = DATA_ROOT / "semantic_standard" / "concept_seed_v1.json"
CATALOG_PATH = DATA_ROOT / "kosis_catalog" / "catalog_350.json"
GOLD_STANDARD_REGISTRY_PATH = DATA_ROOT / "claim_registry" / "gold_standard_v1" / "claim_registry.jsonl"
GOLD_STANDARD_REPORT_PATH = DATA_ROOT / "claim_registry" / "gold_standard_v1" / "validation_report.json"
AS_OF_METADATA_PATHS = [
    DATA_ROOT / "kosis_snapshots" / "goldset_pilot.json",
    DATA_ROOT / "kosis_snapshots" / "official_goldset_asof_v3.json",
    DATA_ROOT / "kosis_snapshots" / "official_cpi_202510.json",
    DATA_ROOT / "kosis_snapshots" / "official_goldset_v3_news_b023.json",
    DATA_ROOT / "kosis_snapshots" / "official_cpi_detail_current_axes_v1.json",
]

METADATA_MANIFEST_PATHS = [
    DATA_ROOT / "kosis_snapshots" / "cpi_detail_metadata_v1_manifest.json",
]


@st.cache_resource
def _official_metadata_repository() -> KosisMetadataRepository:
    """Cache live official table structure across interactive Claims."""
    return KosisMetadataRepository([])

def _find_catalog_candidates(
    claim: ClaimSchema,
    concept: StandardConceptSchema,
    settings: Settings,
) -> list[KosisCandidateSchema]:
    """Prefer registered structural metadata; search KOSIS only for missing tables."""
    local = search_semantic_catalog(claim, concept, load_kosis_catalog(CATALOG_PATH))
    live_search = (
        KosisLiveCatalogSearch(
            settings.kosis_api_key,
            max_attempts=2,
            timeout_seconds=10,
        )
        if settings.kosis_api_key
        else None
    )
    discovered = discover_catalog_candidates(
        claim,
        concept,
        local,
        live_search,
        time_budget_seconds=45.0,
    )
    if (
        live_search is not None
        and live_search.attempted_queries > 0
        and live_search.failed_queries == live_search.attempted_queries
    ):
        raise RuntimeError("KOSIS_CATALOG_UNAVAILABLE")
    refreshed = refresh_item_metadata(
        discovered,
        settings.kosis_api_key,
        metadata_fetcher=_official_metadata_repository(),
        max_candidates=None,
        time_budget_seconds=45.0,
        retries=2,
        timeout_seconds=10,
    )
    unavailable_statuses = {
        "OFFICIAL_ITEM_METADATA_UNAVAILABLE",
        "OFFICIAL_PERIOD_METADATA_UNAVAILABLE",
    }
    ready = [
        candidate
        for candidate in refreshed
        if candidate.metadata_status == "OFFICIAL_METADATA_READY"
    ]
    unavailable = [
        candidate
        for candidate in refreshed
        if candidate.metadata_status in unavailable_statuses
    ]
    concept_member_code = (
        concept.concept_id.rsplit(":", 1)[-1]
        if ":" in concept.concept_id
        else None
    )
    ready_for_concept = bool(ready)
    if concept_member_code:
        ready_for_concept = any(
            concept_member_code in codes.values()
            for candidate in ready
            for codes in candidate.dimension_member_codes.values()
        )
    if unavailable and not ready_for_concept:
        raise RuntimeError("KOSIS_METADATA_UNAVAILABLE")
    return refreshed


def _official_fetcher(settings: Settings) -> OfficialValueFetcher:
    """Build the read-only official-value fetcher without exposing credentials."""
    api_lookup = build_kosis_api_lookup(settings.kosis_api_key) if settings.kosis_api_key else None
    return OfficialValueFetcher(
        [],
        api_lookup=api_lookup,
        prefer_api=api_lookup is not None,
        as_of_metadata_paths=AS_OF_METADATA_PATHS,
        publication_lookup=KosisPublicationLookup(settings.kosis_api_key),
        require_verified_release_metadata=True,
    )


def _official_evidence_service(settings: Settings) -> OfficialEvidenceService:
    """Build the shared Core Engine for interactive and batch verification."""
    return build_official_evidence_service(
        OfficialEnginePaths(
            standard_path=STANDARD_PATH,
            catalog_path=CATALOG_PATH,
            as_of_metadata_paths=AS_OF_METADATA_PATHS,
            metadata_manifest_paths=METADATA_MANIFEST_PATHS,
        ),
        kosis_api_key=settings.kosis_api_key,
    )

class _InvalidArticleDateError(ValueError):
    """Raised only when the article date input is not ISO formatted."""


def _parse_article_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise _InvalidArticleDateError from error


def _verify_batch_claim(sentence: str, article_date: date, settings: Settings) -> VerdictSchema:
    """Parse a batch sentence, then use the same dynamic KOSIS engine as the UI."""
    extractor = run_operational_stage(
        "CLAIM_PARSE",
        lambda: create_claim_extractor(settings),
    )
    claims = run_operational_stage(
        "CLAIM_PARSE",
        lambda: parse_article_claims(
            sentence,
            extractor,
            article_published_at=article_date,
        ),
    )
    if len(claims) != 1:
        raise ValueError("BATCH_CLAIM_SPLIT_CARDINALITY")
    claim = claims[0]
    if claim.parse_status != "AUTO_OK":
        recorder = VerificationTraceRecorder(claim.claim_id).claim_parsed()
        return attach_trace(make_verdict(claim.claim_id, claim.value, [], None), recorder.build()).model_copy(
            update={
                "route_status": "HOLD",
                "reason_code": claim.parse_reason or "CLAIM_PARSE_UNCERTAIN",
                "explanation": "Claim parsing requires human review.",
            }
        )
    return _official_evidence_service(settings).resolve(
        claim, article_date=article_date
    ).verdict
st.set_page_config(page_title="CLAFACT-AUTO", layout="wide")
st.title("CLAFACT-AUTO")
st.caption("KOSIS 공식값만 사용하며, 좌표·기사시점·후보가 불확실하면 자동 판정하지 않습니다.")

settings = Settings()
st.subheader("운영 연결 상태")
hcx_mode_label = "함수 호출" if settings.hcx_extraction_mode == "function_calling" else "구조화 출력"
if settings.claim_provider == "openai":
    is_openai_primary = True
    primary_provider_label = "OpenAI 함수 호출"
    selected_provider_display_label = "OpenAI"
    primary_provider_status = "연결됨" if settings.openai_api_key else "미설정"
elif settings.claim_provider == "hcx":
    is_openai_primary = False
    primary_provider_label = f"HCX {hcx_mode_label}"
    selected_provider_display_label = "HCX"
    primary_provider_status = "연결됨" if settings.hcx_api_key else "미설정"
else:
    is_openai_primary = False
    primary_provider_label = "지원하지 않는 Provider"
    selected_provider_display_label = "지원하지 않는 Provider"
    primary_provider_status = "설정 오류"
connection_columns = st.columns(3 if is_openai_primary else 2)
connection_columns[0].metric("KOSIS API", "연결됨" if settings.kosis_api_key else "미설정")
connection_columns[1].metric(primary_provider_label, primary_provider_status)
if is_openai_primary:
    connection_columns[2].metric("HCX 예비 처리", "연결됨" if settings.hcx_api_key else "미설정")
st.caption("키 값은 표시하거나 로그에 기록하지 않습니다.")
if is_openai_primary:
    st.caption(f"OpenAI API 키 지문: {describe_secret_fingerprint(settings.openai_api_key)}")

sentence = st.text_area("검증할 뉴스 문장", placeholder="예: 2024년 전국 고용률은 70%였다.")
article_date_text = st.text_input("기사 기준일 (YYYY-MM-DD)", placeholder="예: 2025-06-26")

if st.button("자동 검증 실행", type="primary") and sentence.strip():
    try:
        article_date = _parse_article_date(article_date_text)
        extractor = run_operational_stage(
            "CLAIM_PARSE",
            lambda: create_claim_extractor(settings),
        )
        claims = run_operational_stage(
            "CLAIM_PARSE",
            lambda: parse_article_claims(
                sentence,
                extractor,
                article_published_at=article_date,
            ),
        )
        if not claims:
            raise ValueError("NO_NUMERICAL_CLAIM_CANDIDATE")
        st.caption(f"Claim Split: {len(claims)}개 독립 Claim")
        selected_claim_index = (
            st.selectbox(
                "검토할 Claim 선택",
                range(len(claims)),
                format_func=lambda index: claims[index].source_sentence,
            )
            if len(claims) > 1 else 0
        )
        claim = claims[selected_claim_index]
        actual_provider = getattr(extractor, "last_provider", None)
        actual_provider_label = {
            "openai": "OpenAI",
            "hcx": "HCX",
        }.get(actual_provider, selected_provider_display_label)
        st.metric("실제 주장 추출기", actual_provider_label)
        resolutions_by_claim_id = {}
        if article_date and any(parsed_claim.parse_status == "AUTO_OK" for parsed_claim in claims):
            service = _official_evidence_service(settings)
            for parsed_claim in claims:
                if parsed_claim.parse_status == "AUTO_OK":
                    resolutions_by_claim_id[parsed_claim.claim_id] = service.resolve(
                        parsed_claim, article_date=article_date
                    )
        ui_trace = VerificationTraceRecorder(claim.claim_id).claim_parsed()
        requires_parse_review = claim.parse_status != "AUTO_OK"
        resolution_ready = False
        if requires_parse_review:
            concept = None
            candidates = []
            verdict = make_verdict(claim.claim_id, claim.value, [], None).model_copy(
                update={
                    "route_status": "HOLD",
                    "reason_code": claim.parse_reason or "CLAIM_PARSE_UNCERTAIN",
                    "explanation": "Claim parsing requires human review.",
                }
            )
        elif article_date:
            resolution = resolutions_by_claim_id[claim.claim_id]
            concept = resolution.concept
            candidates = resolution.candidates
            verdict = resolution.verdict
            resolution_ready = True
        else:
            concept = normalize_concept(claim, load_standard_concepts(STANDARD_PATH))
            candidates = []
            verdict = make_verdict(claim.claim_id, claim.value, [], None)
        requires_semantic_review = concept is not None and concept.status != "MATCHED"
        st.subheader("기사 주장")
        claim_columns = st.columns(4)
        claim_columns[0].metric("지표", claim.indicator or "미확정")
        claim_columns[1].metric("기사값", f"{claim.value or ''} {claim.unit or ''}".strip() or "미확정")
        claim_columns[2].metric("기준시점", claim.time or "미확정")
        claim_columns[3].metric("파싱 상태", translate_status(claim.parse_status))
        with st.expander("구조화된 주장 상세"):
            st.json({"claim": claim.model_dump(), "concept": concept.model_dump() if concept else None})
        if not requires_parse_review:
            st.subheader("KOSIS 후보")
            st.dataframe(
                [{"표 ID": item.tbl_id, "통계표": item.tbl_name, "단위": " | ".join(item.unit_names), "주기": item.frequency} for item in candidates]
            )

        official_value = None
        evidence_cells = []
        if not article_date and not requires_parse_review:
            st.warning("보류: 기사 기준일이 없어 사후 개정값을 차단할 수 없습니다.")
        elif resolution_ready:
            evidence_cells = verdict.evidence_cells
            if evidence_cells:
                st.subheader("근거 좌표")
                st.json([cell.model_dump() for cell in evidence_cells])
            if verdict.route_status != "AUTO":
                st.warning(f"보류: {verdict.reason_code}")
            else:
                st.success(f"{translate_status(verdict.verdict)}: KOSIS 공식값 {verdict.evidence_values[0]}")
        if verdict.execution_trace is None:
            verdict = attach_trace(verdict, ui_trace.build())
        st.subheader("최종 판정")
        verdict_columns = st.columns(4)
        verdict_columns[0].metric("판정", translate_status(verdict.verdict))
        verdict_columns[1].metric("경로", translate_status(verdict.route_status))
        verdict_columns[2].metric("기사값", verdict.claim_value if verdict.claim_value is not None else "-")
        verdict_columns[3].metric("KOSIS 공식값", verdict.calculated_value if verdict.calculated_value is not None else "-")
        verdict_explanation = run_operational_stage(
            "VERDICT_EXPLANATION",
            lambda: explain_verdict(
                verdict,
                api_key=(
                    settings.openai_api_key
                    if settings.llm_verdict_explanation_enabled
                    else None
                ),
                model=settings.openai_model,
            ),
        )
        st.subheader("판정 설명")
        explanation_source = "AI 자연어 설명" if verdict_explanation.source == "LLM" else "규칙 기반 설명"
        st.caption(f"설명 방식: {explanation_source}")
        st.write(verdict_explanation.summary)
        st.write(verdict_explanation.detail)
        if verdict_explanation.next_action:
            st.info(f"다음 확인: {verdict_explanation.next_action}")
        if verdict.execution_trace:
            with st.expander("3갈래 실행 추적"):
                st.json(build_trace_summary(verdict.execution_trace))
        if verdict.route_status != "AUTO":
            st.warning(f"보류 사유: {verdict.reason_code} — {verdict.explanation}")
        if verdict.evidence_cells:
            st.subheader("KOSIS 공식 근거")
            st.dataframe(
                build_evidence_rows(verdict.evidence_cells, verdict.evidence_values)
            )
            rendered_tables: set[tuple[str, str]] = set()
            for evidence_cell in verdict.evidence_cells:
                table_key = (evidence_cell.org_id, evidence_cell.tbl_id)
                if table_key in rendered_tables:
                    continue
                rendered_tables.add(table_key)
                st.link_button(
                    f"KOSIS 표 원문 열기: {evidence_cell.tbl_id}",
                    build_kosis_table_url(evidence_cell),
                )
        with st.expander("판정 상세 JSON"):
            st.json(verdict.model_dump())
        payload = build_review_payload(verdict)
        st.subheader("검토 콘솔 전달 데이터")
        st.json({"claim_id": payload.claim_id, "route_status": payload.route_status, "reason_code": payload.reason_code, "evidence_count": payload.evidence_count})
        download_columns = st.columns(2)
        download_columns[0].download_button(
            "판정 결과 JSON 다운로드",
            data=export_verdict_json_bytes(verdict),
            file_name=f"clafact_claim_{verdict.claim_id}.json",
            mime="application/json",
        )
        download_columns[1].download_button(
            "판정 결과 XLSX 다운로드",
            data=export_verdict_xlsx_bytes(verdict),
            file_name=f"clafact_claim_{verdict.claim_id}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except _InvalidArticleDateError:
        st.error("보류: 기사 기준일은 YYYY-MM-DD 형식이어야 합니다.")
    except OperationalStageError as error:
        st.error(f"보류: {error.safe_message}")
    except Exception as error:
        st.error(f"보류: {type(error).__name__}")
st.divider()
st.subheader("크롤링 뉴스 배치 검증")
st.caption("기사형: article_id, published_at, body · 문장형: article_id, sentence · 선택 열: title, source_url · 업로드 파일은 저장하지 않습니다.")
st.caption("신규 기사는 OpenAI 12슬롯 파싱 후 같은 동적 KOSIS 엔진으로 검증됩니다.")
if GOLD_STANDARD_REPORT_PATH.is_file():
    gold_report = json.loads(GOLD_STANDARD_REPORT_PATH.read_text(encoding="utf-8"))
    st.info(f"Canonical Registry: gold_standard_v1 · {gold_report.get('actual_count', 0):,}건 · 재파싱 없이 동적 KOSIS 배치 실행 가능")
batch_default_date_text = st.text_input("배치 기본 기사 기준일 (선택)", placeholder="문장형 파일에 기사일이 없을 때만 입력 · 예: 2025-04-09")
uploaded_file = st.file_uploader("크롤링 뉴스 파일 업로드", type=["csv", "xlsx", "json"])
if st.button("배치 검증 실행", type="primary", disabled=uploaded_file is None):
    try:
        default_published_at = date.fromisoformat(batch_default_date_text) if batch_default_date_text else None
        articles = load_articles(uploaded_file.name, uploaded_file.getvalue(), default_published_at=default_published_at)
        batch_result = verify_articles(articles, lambda item, published_at: _verify_batch_claim(item, published_at, settings))
        batch_rows = [asdict(row) for row in batch_result.claim_rows]
        total = len(batch_rows)
        match_count = sum(row["verdict"] == "MATCH" for row in batch_rows)
        mismatch_count = sum(row["verdict"] == "MISMATCH" for row in batch_rows)
        review_count = total - match_count - mismatch_count
        columns = st.columns(4)
        columns[0].metric("검증 Claim", total)
        columns[1].metric("일치", match_count)
        columns[2].metric("불일치", mismatch_count)
        columns[3].metric("검토 필요", review_count)
        st.dataframe(batch_rows)
        st.download_button(
            "결과 XLSX 다운로드",
            data=export_batch_xlsx(batch_result),
            file_name="clafact_auto_batch_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except ValueError as error:
        st.error(f"배치 입력 오류: {error}")
    except Exception as error:
        st.error(f"배치 처리 HOLD: {type(error).__name__}")

st.divider()
st.subheader("운영 배치 산출물 검토")
st.caption("E2E 결과 JSONL·커버리지 보고서·비교 검토 큐를 읽기 전용으로 확인합니다. 업로드 파일은 저장하지 않습니다.")
operations_results = st.file_uploader("E2E 결과 JSONL", type=["jsonl"], key="operations_results")
operations_coverage = st.file_uploader("커버리지 보고서 JSON", type=["json"], key="operations_coverage")
operations_queue = st.file_uploader("모호 비교 검토 큐 JSONL (선택)", type=["jsonl"], key="operations_queue")
if operations_results and operations_coverage:
    import json as _operations_json
    try:
        operations_rows = [_operations_json.loads(line) for line in operations_results.getvalue().decode("utf-8").splitlines() if line.strip()]
        operations_report = _operations_json.loads(operations_coverage.getvalue().decode("utf-8"))
        operations_review_rows = [_operations_json.loads(line) for line in operations_queue.getvalue().decode("utf-8").splitlines() if line.strip()] if operations_queue else []
        metrics = st.columns(3)
        metrics[0].metric("결과 Claim", len(operations_rows))
        metrics[1].metric("검토 큐", len(operations_review_rows))
        metrics[2].metric("자동 경로", operations_report.get("route_counts", {}).get("AUTO", 0))
        st.json(operations_report)
        st.dataframe(operations_rows)
        if operations_review_rows:
            st.dataframe(operations_review_rows)
    except (UnicodeDecodeError, ValueError, _operations_json.JSONDecodeError):
        st.error("운영 산출물 형식 오류: UTF-8 JSONL/JSON 파일을 확인하세요.")

st.divider()
st.subheader("내부 검증 MVP 실행 결과")
st.caption("버전형 실행 산출물을 읽기 전용으로 표시합니다.")
if DEFAULT_INTERNAL_RUN_DIR.is_dir():
    try:
        operator_run = load_operator_run(DEFAULT_INTERNAL_RUN_DIR)
        status_columns = st.columns(3)
        status_columns[0].metric("실행 Claim", len(operator_run.results))
        status_columns[1].metric("자동 판정", operator_run.report.get("route_counts", {}).get("AUTO", 0))
        status_columns[2].metric("보류 검토 묶음", len(operator_run.review_queue))
        st.json(operator_run.report)
        if operator_run.review_queues:
            st.subheader("유형별 검토 큐")
            st.json(operator_run.review_summary)
            for queue_type, queue_rows in operator_run.review_queues.items():
                st.download_button(
                    f"{queue_type} 검토 큐 JSON 다운로드",
                    data=json.dumps(queue_rows, ensure_ascii=False, indent=2),
                    file_name=f"{queue_type}_review_queue.json",
                    mime="application/json",
                )
        reasons = sorted({str(row.get("reason_code", "UNSPECIFIED")) for row in operator_run.review_queue})
        selected_reason = st.selectbox("보류 사유 필터", ["전체", *reasons])
        max_rank = max((int(row.get("priority_rank", 0)) for row in operator_run.review_queue), default=0)
        selected_max_rank = st.number_input("최대 우선순위", min_value=1, max_value=max(1, max_rank), value=max(1, max_rank), step=1)
        filtered_queue = [
            row for row in operator_run.review_queue
            if (selected_reason == "전체" or row.get("reason_code") == selected_reason)
            and int(row.get("priority_rank", 0)) <= selected_max_rank
        ]
        st.dataframe(filtered_queue)
        st.download_button("보류 검토 큐 JSON 다운로드", data=json.dumps(operator_run.review_queue, ensure_ascii=False, indent=2), file_name="review_queue.json", mime="application/json")
        export_columns = st.columns(2)
        csv_path = DEFAULT_INTERNAL_RUN_DIR / "claim_verification_results.csv"
        xlsx_path = DEFAULT_INTERNAL_RUN_DIR / "claim_verification_results.xlsx"
        if csv_path.is_file():
            export_columns[0].download_button("전체 결과 CSV 다운로드", data=csv_path.read_bytes(), file_name=csv_path.name, mime="text/csv")
        if xlsx_path.is_file():
            export_columns[1].download_button("전체 결과 XLSX 다운로드", data=xlsx_path.read_bytes(), file_name=xlsx_path.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except (OSError, ValueError, json.JSONDecodeError):
        st.error("내부 검증 실행 산출물을 읽을 수 없습니다.")
else:
    st.info("아직 내부 검증 실행 산출물이 없습니다.")



