"""Streamlit MVP for the safe, review-first CLAFACT-AUTO flow."""

from datetime import date
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from core.calculator import calculate
from core.catalog_search import search_semantic_catalog
from core.data_loader import load_kosis_catalog, load_standard_concepts
from core.evidence_resolver import resolve_evidence_cell
from core.hcx_claim_extractor import HcxClaimExtractor
from core.kosis_fetcher import OfficialValueFetcher
from core.kosis_api_adapter import build_kosis_api_lookup
from config.settings import Settings
from core.review_handoff import build_review_payload
from core.semantic_matcher import semantic_match
from core.semantic_normalizer import normalize_concept
from core.verdict_engine import make_verdict
from schemas.evidence import CalculationPlan

DATA_ROOT = Path("data")
STANDARD_PATH = DATA_ROOT / "semantic_standard" / "seed_concepts.json"
CATALOG_PATH = DATA_ROOT / "kosis_catalog" / "catalog_350.json"
SNAPSHOT_PATHS = [
    DATA_ROOT / "kosis_snapshots" / "goldset_pilot.json",
    DATA_ROOT / "kosis_snapshots" / "official_goldset_asof_v3.json",
]

st.set_page_config(page_title="CLAFACT-AUTO", layout="wide")
st.title("CLAFACT-AUTO")
st.caption("KOSIS 공식값만 사용하며, 좌표·기사시점·후보가 불확실하면 자동 판정하지 않습니다.")

settings = Settings()
st.subheader("운영 연결 상태")
connection_columns = st.columns(2)
connection_columns[0].metric("KOSIS API", "연결됨" if settings.kosis_api_key else "미설정")
connection_columns[1].metric("HCX Structured Output", "연결됨" if settings.hcx_api_key else "미설정")
st.caption("키 값은 표시하거나 로그에 기록하지 않습니다.")

sentence = st.text_area("검증할 뉴스 문장", placeholder="예: 2024년 전국 고용률은 70%였다.")
article_date_text = st.text_input("기사 기준일 (YYYY-MM-DD)", placeholder="예: 2025-06-26")

if st.button("자동 검증 실행", type="primary") and sentence.strip():
    try:
        article_date = date.fromisoformat(article_date_text) if article_date_text else None
        claim = HcxClaimExtractor().extract(sentence)
        concept = normalize_concept(claim, load_standard_concepts(STANDARD_PATH))
        candidates = search_semantic_catalog(claim, concept, load_kosis_catalog(CATALOG_PATH))
        matches = semantic_match(claim, candidates)

        st.subheader("기사 주장")
        claim_columns = st.columns(4)
        claim_columns[0].metric("지표", claim.indicator or "미확정")
        claim_columns[1].metric("기사값", f"{claim.value or ''} {claim.unit or ''}".strip() or "미확정")
        claim_columns[2].metric("기준시점", claim.time or "미확정")
        claim_columns[3].metric("파싱 상태", claim.parse_status)
        with st.expander("구조화 Claim 상세"):
            st.json({"claim": claim.model_dump(), "concept": concept.model_dump()})
        st.subheader("KOSIS 후보")
        st.dataframe(
            [{"표 ID": item.tbl_id, "통계표": item.tbl_name, "단위": " | ".join(item.unit_names), "주기": item.frequency} for item in candidates],
            use_container_width=True,
        )

        official_value = None
        evidence_cells = []
        if not article_date:
            verdict = make_verdict(claim.claim_id, claim.value, [], None)
            st.warning("HOLD: 기사 기준일이 없어 사후 개정값을 차단할 수 없습니다.")
        elif not matches:
            verdict = make_verdict(claim.claim_id, claim.value, [], None)
            st.warning("HOLD: Hard Guard를 통과한 KOSIS 후보가 없습니다.")
        else:
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
                api_lookup = build_kosis_api_lookup(settings.kosis_api_key) if settings.kosis_api_key else None
                official_value = OfficialValueFetcher(SNAPSHOT_PATHS, api_lookup=api_lookup).fetch(cell, article_date=article_date)
                if official_value.status != "SUCCESS":
                    verdict = make_verdict(claim.claim_id, claim.value, [], None)
                    st.warning(f"HOLD: {official_value.status}")
                else:
                    calculated = calculate(CalculationPlan(calculation_type="DIRECT_VALUE", required_cells=[cell]), [official_value.value])
                    verdict = make_verdict(claim.claim_id, claim.value, [official_value.value], calculated, tolerance=0.01)
                    st.success(f"{verdict.verdict}: KOSIS Snapshot 공식값 {official_value.value}")

        st.subheader("최종 판정")
        verdict_columns = st.columns(4)
        verdict_columns[0].metric("판정", verdict.verdict)
        verdict_columns[1].metric("경로", verdict.route_status)
        verdict_columns[2].metric("기사값", verdict.claim_value if verdict.claim_value is not None else "-")
        verdict_columns[3].metric("KOSIS 공식값", verdict.calculated_value if verdict.calculated_value is not None else "-")
        if verdict.route_status != "AUTO":
            st.warning(f"HOLD 사유: {verdict.reason_code} — {verdict.explanation}")
        with st.expander("Verdict 상세 JSON"):
            st.json(verdict.model_dump())
        payload = build_review_payload(verdict)
        st.subheader("검토 콘솔 전달 payload")
        st.json({"claim_id": payload.claim_id, "route_status": payload.route_status, "reason_code": payload.reason_code, "evidence_count": payload.evidence_count})
    except ValueError:
        st.error("HOLD: 기사 기준일은 YYYY-MM-DD 형식이어야 합니다.")
    except Exception as error:
        st.error(f"HOLD: {type(error).__name__}")