"""Streamlit MVP for the safe, review-first CLAFACT-AUTO flow."""

from dataclasses import asdict
from datetime import date
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from core.batch_verifier import export_batch_xlsx, load_articles, verify_articles
from core.claim_parser import parse_claim
from core.claim_extractor_factory import create_claim_extractor
from core.claim_time_resolver import resolve_relative_time
from core.calculator import calculate
from core.catalog_binding import apply_catalog_binding
from core.catalog_discovery import discover_catalog_candidates, has_unresolved_live_metadata
from core.catalog_search import search_semantic_catalog
from core.data_loader import load_kosis_catalog, load_standard_concepts
from core.evidence_resolver import resolve_evidence_cell
from core.evidence_presentation import build_evidence_rows, build_kosis_table_url
from core.kosis_fetcher import OfficialValueFetcher
from core.cpi_growth_resolver import resolve_cpi_growth_plan
from core.growth_verdict import make_cpi_growth_verdict
from core.kosis_live_catalog import KosisLiveCatalogSearch
from core.catalog_metadata_refresh import refresh_item_metadata
from core.kosis_api_adapter import build_kosis_api_lookup
from config.settings import Settings
from core.review_handoff import build_review_payload
from core.trace_presentation import build_trace_summary
from core.semantic_matcher import semantic_match
from core.semantic_normalizer import normalize_concept
from core.unit_normalizer import convert_value
from core.verdict_engine import make_verdict
from core.claim_verification_service import VerificationTraceRecorder
from core.verification_trace import attach_trace
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema
from schemas.evidence import CalculationPlan
from schemas.verdict import VerdictSchema

DATA_ROOT = Path("data")
STANDARD_PATH = DATA_ROOT / "semantic_standard" / "seed_concepts.json"
CATALOG_PATH = DATA_ROOT / "kosis_catalog" / "catalog_350.json"
SNAPSHOT_PATHS = [
    DATA_ROOT / "kosis_snapshots" / "goldset_pilot.json",
    DATA_ROOT / "kosis_snapshots" / "official_goldset_asof_v3.json",
    DATA_ROOT / "kosis_snapshots" / "official_cpi_202510.json",
    DATA_ROOT / "kosis_snapshots" / "official_goldset_v3_news_b023.json",
]

def _find_catalog_candidates(
    claim: ClaimSchema,
    concept: StandardConceptSchema,
    settings: Settings,
) -> list[KosisCandidateSchema]:
    """Prefer registered structural metadata; search KOSIS only for missing tables."""
    local = apply_catalog_binding(
        claim,
        concept,
        search_semantic_catalog(claim, concept, load_kosis_catalog(CATALOG_PATH)),
    )
    live_search = KosisLiveCatalogSearch(settings.kosis_api_key) if settings.kosis_api_key else None
    discovered = discover_catalog_candidates(claim, concept, local, live_search)
    return discovered


def _official_fetcher(settings: Settings) -> OfficialValueFetcher:
    """Build the read-only official-value fetcher without exposing credentials."""
    api_lookup = build_kosis_api_lookup(settings.kosis_api_key) if settings.kosis_api_key else None
    return OfficialValueFetcher(SNAPSHOT_PATHS, api_lookup=api_lookup, prefer_api=api_lookup is not None)


def _cpi_growth_fetcher(settings: Settings) -> OfficialValueFetcher:
    """Use the dated official CPI detail Snapshot before an API fallback."""
    api_lookup = build_kosis_api_lookup(settings.kosis_api_key) if settings.kosis_api_key else None
    return OfficialValueFetcher(
        [DATA_ROOT / "kosis_snapshots" / "official_goldset_v3_news_b023.json"],
        api_lookup=api_lookup,
        prefer_api=False,
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
    """Run the same safe claim pipeline for one batch sentence."""
    claim = parse_claim(sentence, create_claim_extractor(settings))
    claim = resolve_relative_time(claim, article_date)
    recorder = VerificationTraceRecorder(claim.claim_id).claim_parsed()
    if claim.parse_status != "AUTO_OK":
        return attach_trace(make_verdict(claim.claim_id, claim.value, [], None), recorder.build()).model_copy(
            update={
                "route_status": claim.parse_status,
                "reason_code": claim.parse_reason or "CLAIM_PARSE_UNCERTAIN",
                "explanation": "Claim parsing requires human review.",
            }
        )
    growth_verdict = make_cpi_growth_verdict(claim, article_date, _cpi_growth_fetcher(settings))
    if growth_verdict is not None:
        recorder.registered_growth_profile_matched().verification_succeeded()
        return attach_trace(growth_verdict, recorder.build())
    recorder.concept_mapped()
    concept = normalize_concept(claim, load_standard_concepts(STANDARD_PATH))
    candidates = _find_catalog_candidates(claim, concept, settings)
    recorder.catalog_searched()
    matches = semantic_match(claim, candidates)
    if not matches:
        recorder.hard_guard_held("NO_HARD_GUARD_CANDIDATE")
        reason = "LIVE_CATALOG_METADATA_UNRESOLVED" if has_unresolved_live_metadata(candidates) else "NO_HARD_GUARD_CANDIDATE"
        explanation = "KOSIS table was found, but official item and dimension codes are not yet resolved." if reason == "LIVE_CATALOG_METADATA_UNRESOLVED" else "No KOSIS candidate passed Hard Guard."
        return attach_trace(make_verdict(claim.claim_id, claim.value, [], None), recorder.build()).model_copy(
            update={"reason_code": reason, "explanation": explanation}
        )
    recorder.hard_guard_passed().semantic_matched(matches[0].route_status, matches[0].reason_code or "MATCH_ACCEPTED", matches[0].top1_top2_margin)
    best = matches[0]
    selected = next(item for item in candidates if item.tbl_id == best.candidate_tbl_id)
    cell = resolve_evidence_cell(claim, selected)
    if best.route_status != "AUTO" or cell.status != "CONFIRMED":
        return attach_trace(make_verdict(claim.claim_id, claim.value, [], None), recorder.build()).model_copy(
            update={"reason_code": best.reason_code or cell.status, "explanation": "KOSIS coordinate is not confirmed.", "evidence_cells": [cell]}
        )
    official_value = _official_fetcher(settings).fetch(cell, article_date=article_date)
    if official_value.status != "SUCCESS":
        return attach_trace(make_verdict(claim.claim_id, claim.value, [], None), recorder.build()).model_copy(
            update={"reason_code": official_value.status, "explanation": "Official value is unavailable.", "evidence_cells": [cell]}
        )
    calculated = calculate(CalculationPlan(calculation_type="DIRECT_VALUE", required_cells=[cell]), [official_value.value])
    claim_unit_value = convert_value(calculated, cell.unit or "", claim.unit or "")
    return attach_trace(make_verdict(claim.claim_id, claim.value, [official_value.value], claim_unit_value, tolerance=0.01), recorder.build()).model_copy(update={"evidence_cells": [cell]})

st.set_page_config(page_title="CLAFACT-AUTO", layout="wide")
st.title("CLAFACT-AUTO")
st.caption("KOSIS 공식값만 사용하며, 좌표·기사시점·후보가 불확실하면 자동 판정하지 않습니다.")

settings = Settings()
st.subheader("운영 연결 상태")
hcx_mode_label = "Function Calling" if settings.hcx_extraction_mode == "function_calling" else "Structured Output"
if settings.claim_provider == "openai":
    is_openai_primary = True
    primary_provider_label = "OpenAI Function Calling"
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
    connection_columns[2].metric("HCX fallback", "연결됨" if settings.hcx_api_key else "미설정")
st.caption("키 값은 표시하거나 로그에 기록하지 않습니다.")

sentence = st.text_area("검증할 뉴스 문장", placeholder="예: 2024년 전국 고용률은 70%였다.")
article_date_text = st.text_input("기사 기준일 (YYYY-MM-DD)", placeholder="예: 2025-06-26")

if st.button("자동 검증 실행", type="primary") and sentence.strip():
    try:
        article_date = _parse_article_date(article_date_text)
        extractor = create_claim_extractor(settings)
        claim = parse_claim(sentence, extractor)
        actual_provider = getattr(extractor, "last_provider", None)
        actual_provider_label = {
            "openai": "OpenAI",
            "hcx": "HCX",
        }.get(actual_provider, selected_provider_display_label)
        st.metric("실제 Claim Provider", actual_provider_label)
        claim = resolve_relative_time(claim, article_date)
        ui_trace = VerificationTraceRecorder(claim.claim_id).claim_parsed()
        growth_plan = resolve_cpi_growth_plan(claim)
        growth_verdict = make_cpi_growth_verdict(claim, article_date, _cpi_growth_fetcher(settings)) if article_date else None
        concept = growth_plan.concept if growth_plan is not None else normalize_concept(claim, load_standard_concepts(STANDARD_PATH))
        candidates = [growth_plan.candidate] if growth_plan is not None else _find_catalog_candidates(claim, concept, settings)
        if growth_plan is not None:
            ui_trace.registered_growth_profile_matched()
        else:
            ui_trace.concept_mapped().catalog_searched()
        matches = semantic_match(claim, candidates)

        st.subheader("기사 주장")
        claim_columns = st.columns(4)
        claim_columns[0].metric("지표", claim.indicator or "미확정")
        claim_columns[1].metric("기사값", f"{claim.value or ''} {claim.unit or ''}".strip() or "미확정")
        claim_columns[2].metric("기준시점", claim.time or "미확정")
        claim_columns[3].metric("파싱 상태", claim.parse_status)
        with st.expander("구조화 Claim 상세"):
            st.json({"claim": claim.model_dump(), "concept": concept.model_dump() if concept else None})
        st.subheader("KOSIS 후보")
        st.dataframe(
            [{"표 ID": item.tbl_id, "통계표": item.tbl_name, "단위": " | ".join(item.unit_names), "주기": item.frequency} for item in candidates],
            width="stretch",
        )

        official_value = None
        evidence_cells = []
        if growth_verdict is not None:
            ui_trace.verification_succeeded()
            verdict = growth_verdict
            evidence_cells = verdict.evidence_cells
            st.subheader("Evidence 좌표")
            st.json([cell.model_dump() for cell in evidence_cells])
        elif not article_date:
            verdict = make_verdict(claim.claim_id, claim.value, [], None)
            st.warning("HOLD: 기사 기준일이 없어 사후 개정값을 차단할 수 없습니다.")
        elif not matches:
            ui_trace.hard_guard_held("NO_HARD_GUARD_CANDIDATE")
            verdict = make_verdict(claim.claim_id, claim.value, [], None)
            if has_unresolved_live_metadata(candidates):
                st.warning("HOLD: KOSIS 표는 찾았지만 항목·분류 코드가 확정되지 않았습니다.")
            else:
                st.warning("HOLD: Hard Guard를 통과한 KOSIS 후보가 없습니다.")
        else:
            ui_trace.hard_guard_passed().semantic_matched(matches[0].route_status, matches[0].reason_code or "MATCH_ACCEPTED", matches[0].top1_top2_margin)
            best = matches[0]
            selected = next(item for item in candidates if item.tbl_id == best.candidate_tbl_id)
            cell = resolve_evidence_cell(claim, selected)
            evidence_cells = [cell]
            st.subheader("Evidence 좌표")
            st.json(cell.model_dump())
            if best.route_status != "AUTO" or cell.status != "CONFIRMED":
                verdict = make_verdict(claim.claim_id, claim.value, [], None)
                st.warning(f"HOLD: {best.reason_code or cell.status}")
            else:
                official_value = _official_fetcher(settings).fetch(cell, article_date=article_date)
                if official_value.status != "SUCCESS":
                    verdict = make_verdict(claim.claim_id, claim.value, [], None)
                    st.warning(f"HOLD: {official_value.status}")
                else:
                    calculated = calculate(CalculationPlan(calculation_type="DIRECT_VALUE", required_cells=[cell]), [official_value.value])
                    claim_unit_value = convert_value(calculated, cell.unit or "", claim.unit or "")
                    verdict = make_verdict(claim.claim_id, claim.value, [official_value.value], claim_unit_value, tolerance=0.01)
                    st.success(f"{verdict.verdict}: KOSIS Snapshot 공식값 {official_value.value}")

        verdict = attach_trace(verdict, ui_trace.build())
        st.subheader("최종 판정")
        verdict_columns = st.columns(4)
        verdict_columns[0].metric("판정", verdict.verdict)
        verdict_columns[1].metric("경로", verdict.route_status)
        verdict_columns[2].metric("기사값", verdict.claim_value if verdict.claim_value is not None else "-")
        verdict_columns[3].metric("KOSIS 공식값", verdict.calculated_value if verdict.calculated_value is not None else "-")
        if verdict.execution_trace:
            with st.expander("3갈래 실행 추적"):
                st.json(build_trace_summary(verdict.execution_trace))
        if verdict.route_status != "AUTO":
            st.warning(f"HOLD 사유: {verdict.reason_code} — {verdict.explanation}")
        if verdict.evidence_cells:
            st.subheader("KOSIS 공식 근거")
            st.dataframe(
                build_evidence_rows(verdict.evidence_cells, verdict.evidence_values),
                width="stretch",
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
        with st.expander("Verdict 상세 JSON"):
            st.json(verdict.model_dump())
        payload = build_review_payload(verdict)
        st.subheader("검토 콘솔 전달 payload")
        st.json({"claim_id": payload.claim_id, "route_status": payload.route_status, "reason_code": payload.reason_code, "evidence_count": payload.evidence_count})
    except _InvalidArticleDateError:
        st.error("HOLD: 기사 기준일은 YYYY-MM-DD 형식이어야 합니다.")
    except Exception as error:
        st.error(f"HOLD: {type(error).__name__}")
st.divider()
st.subheader("크롤링 뉴스 배치 검증")
st.caption("기사형: article_id, published_at, body · 문장형: article_id, sentence · 선택 열: title, source_url · 업로드 파일은 저장하지 않습니다.")
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
        st.dataframe(batch_rows, width="stretch")
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
