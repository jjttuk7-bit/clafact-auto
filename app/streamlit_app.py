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

sentence = st.text_area("검증할 뉴스 문장", placeholder="예: 2024년 전국 고용률은 70%였다.")
article_date_text = st.text_input("기사 기준일 (YYYY-MM-DD)", placeholder="예: 2025-06-26")

if st.button("자동 검증 실행", type="primary") and sentence.strip():
    try:
        article_date = date.fromisoformat(article_date_text) if article_date_text else None
        claim = HcxClaimExtractor().extract(sentence)
        concept = normalize_concept(claim, load_standard_concepts(STANDARD_PATH))
        candidates = search_semantic_catalog(claim, concept, load_kosis_catalog(CATALOG_PATH))
        matches = semantic_match(claim, candidates)

        st.subheader(f"파싱 상태: {claim.parse_status}")
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
                settings = Settings()
                api_lookup = build_kosis_api_lookup(settings.kosis_api_key) if settings.kosis_api_key else None
                official_value = OfficialValueFetcher(SNAPSHOT_PATHS, api_lookup=api_lookup).fetch(cell, article_date=article_date)
                if official_value.status != "SUCCESS":
                    verdict = make_verdict(claim.claim_id, claim.value, [], None)
                    st.warning(f"HOLD: {official_value.status}")
                else:
                    calculated = calculate(CalculationPlan(calculation_type="DIRECT_VALUE", required_cells=[cell]), [official_value.value])
                    verdict = make_verdict(claim.claim_id, claim.value, [official_value.value], calculated, tolerance=0.01)
                    st.success(f"{verdict.verdict}: KOSIS Snapshot 공식값 {official_value.value}")

        st.subheader("Verdict")
        st.json(verdict.model_dump())
        payload = build_review_payload(verdict)
        st.subheader("검토 콘솔 전달 payload")
        st.json({"claim_id": payload.claim_id, "route_status": payload.route_status, "reason_code": payload.reason_code, "evidence_count": payload.evidence_count})
    except ValueError:
        st.error("HOLD: 기사 기준일은 YYYY-MM-DD 형식이어야 합니다.")
    except Exception as error:
        st.error(f"HOLD: {type(error).__name__}")