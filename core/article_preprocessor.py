"""Deterministic crawler-text cleanup and numerical claim candidate selection."""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.pipeline_trace import PipelineTrace
from schemas.pipeline_trace import PipelineTraceSchema

_NUMERIC = re.compile(r"\d")
_SENTENCES = re.compile(r"(?<=[.!?])\s+|\n+")
_TRAILING_CRAWL_NOISE = re.compile(r"(?:관련 기사|AI 추천|By Taboola|댓글(?:작성)?|많이 본 뉴스)")
_METADATA_PREFIX = re.compile(
    r"^.*?(?:입력|등록)\s*\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}\.?(?:\s*\d{1,2}:\d{2})?"
    r"(?:\s*(?:업데이트|수정)\s*\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}\.?(?:\s*\d{1,2}:\d{2})?)?\s*\d*\s*",
    re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class ArticlePreprocessResult:
    clean_text: str
    sentences: list[str]
    claim_candidates: list[str]
    trace: PipelineTraceSchema


def preprocess_article(body: str, *, preprocess_version: str = "1.0") -> ArticlePreprocessResult:
    """Return cleaned article text, sentence units, numerical candidates, and trace."""
    clean_text = _METADATA_PREFIX.sub("", _TRAILING_CRAWL_NOISE.split(body, maxsplit=1)[0], count=1).strip()
    trace = PipelineTrace.for_claim(
        "article-preprocess",
        preprocess_version=preprocess_version,
        claim_schema_version="1.0",
    )
    trace = trace.pass_stage("PREPROCESS", output_ref="clean_text")
    sentences = [sentence.strip() for sentence in _SENTENCES.split(clean_text) if sentence.strip()]
    trace = trace.pass_stage("SENTENCE_SPLIT", output_ref=str(len(sentences)))
    claim_candidates = [sentence for sentence in sentences if _NUMERIC.search(sentence)]
    trace = trace.pass_stage("CLAIM_CANDIDATE_SELECTION", output_ref=str(len(claim_candidates)))
    return ArticlePreprocessResult(clean_text, sentences, claim_candidates, trace)