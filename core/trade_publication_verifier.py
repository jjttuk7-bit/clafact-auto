"""Article-time recovery from registered BOK/KCS period-specific trade releases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from html import unescape
from io import BytesIO
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from typing import Any, Callable
from urllib.request import Request, urlopen

from core.kosis_openapi_transport import create_kosis_tls_context
from core.trade_official_publication import extract_trade_official_value
from core.verdict_engine import make_verdict
from schemas.claim import ClaimSchema
from schemas.verdict import (
    OfficialPublicationProvenanceSchema,
    OfficialValueProvenanceSchema,
    VerdictSchema,
)


@dataclass(frozen=True)
class TradeRelease:
    period: str
    author: str
    published_at: date
    source_url: str
    document_format: str


_RELEASES = (
    TradeRelease("2024-12", "한국은행", date(2025, 2, 6), "https://www.bok.or.kr/fileSrc/portal/83074cef62e649de9e3c3d993a68349b/2/5d5c1a4a4b094a858aea49205410d614.pdf", "PDF"),
    TradeRelease("2024", "한국은행", date(2025, 2, 6), "https://www.bok.or.kr/fileSrc/portal/83074cef62e649de9e3c3d993a68349b/2/5d5c1a4a4b094a858aea49205410d614.pdf", "PDF"),
    TradeRelease("2025-01-01/2025-02-20", "관세청", date(2025, 2, 21), "https://www.customs.go.kr/kcs/na/ntt/selectNttInfo.do?nttSn=10131794&nttSnUrl=9b510df43d783fcfd23b3f95b583609f&bbsId=1362&mi=2891", "HTML"),
    TradeRelease("2025-04-01/2025-04-10", "관세청", date(2025, 4, 11), "https://www.customs.go.kr/common/nttFileDownload.do?fileKey=0a58f14b5bd4fb97fc1ef556f28c7f34", "HWP"),
)


def _default_fetch(url: str, timeout: float) -> bytes:
    request = Request(url, headers={"User-Agent": "CLAFACT-AUTO/0.1"})
    with urlopen(request, timeout=timeout, context=create_kosis_tls_context()) as response:
        return response.read()


class TradePublicationVerifier:
    def __init__(self, *, fetch: Callable[[str, float], bytes] = _default_fetch, timeout_seconds: int = 20) -> None:
        self._fetch = fetch
        self._timeout = max(1, timeout_seconds)

    def recover(self, claim: ClaimSchema, verdict: VerdictSchema, *, article_date: date) -> VerdictSchema:
        if verdict.route_status != "HOLD" or not _is_trade(claim):
            return verdict
        releases = [item for item in _RELEASES if item.period == str(claim.time or "")]
        if len(releases) != 1 or releases[0].published_at > article_date:
            return verdict
        release = releases[0]
        try:
            raw = self._fetch(release.source_url, float(self._timeout))
            text = _document_text(raw, release.document_format)
        except (OSError, RuntimeError, TypeError, ValueError, ImportError):
            return verdict
        official_value = extract_trade_official_value(claim, text)
        if official_value is None:
            return verdict
        digest = sha256(raw).hexdigest()
        retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        publication = OfficialPublicationProvenanceSchema(
            status="VERIFIED",
            published_at=release.published_at,
            source_url=release.source_url,
            retrieved_at=retrieved_at,
            reference_period=release.period,
            content_hash=digest,
        )
        provenance = OfficialValueProvenanceSchema(
            evidence_key=f"OFFICIAL_TRADE_RELEASE:{release.author}:{release.period}",
            source="OFFICIAL_DOCUMENT",
            source_url=release.source_url,
            retrieved_at=retrieved_at,
            content_hash=digest,
            publication=publication,
        )
        trace = verdict.execution_trace
        if trace is not None:
            trace = (
                trace.pass_stage("OFFICIAL_AUTHOR_SEARCH", output_ref=release.author)
                .pass_stage("OFFICIAL_AUTHOR_FETCH", output_ref=digest)
                .pass_stage("CALCULATION")
                .pass_stage("VERDICT")
                .model_copy(update={"route_status": "AUTO"})
            )
        recovered = make_verdict(
            claim.claim_id,
            claim.value,
            [official_value],
            official_value,
            tolerance=_claim_tolerance(claim),
            trace=trace,
        )
        return recovered.model_copy(update={
            "evidence_cells": verdict.evidence_cells,
            "official_value_provenance": [*verdict.official_value_provenance, provenance],
        })


def _document_text(raw: bytes, document_format: str) -> str:
    if document_format == "PDF":
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(raw)).pages)
    if document_format == "HWP":
        from hwp5.hwp5txt import TextTransform
        from hwp5.xmlmodel import Hwp5File
        path = ""
        try:
            with NamedTemporaryFile(suffix=".hwp", delete=False) as temp:
                temp.write(raw)
                path = temp.name
            output = BytesIO()
            hwp = Hwp5File(path)
            try:
                TextTransform().transform_hwp5_to_text(hwp, output)
            finally:
                hwp.close()
            return output.getvalue().decode("utf-8")
        finally:
            if path:
                Path(path).unlink(missing_ok=True)
    html = raw.decode("utf-8", errors="replace")
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


def _is_trade(claim: ClaimSchema) -> bool:
    text = f"{claim.indicator or ''} {claim.source_sentence}".replace(" ", "")
    return any(term in text for term in ("수출", "수입", "무역수지"))


def _claim_tolerance(claim: ClaimSchema) -> float:
    if (claim.unit or "") in {"%", "％", "퍼센트"}:
        match = re.search(rf"{float(claim.value or 0):g}\s*[%％]", claim.source_sentence)
        decimals = len(match.group(0).split(".", 1)[1].split("%", 1)[0]) if match and "." in match.group(0) else 0
        return 0.5 * 10 ** -decimals
    scales = {"조": 1e12, "억": 1e8, "만": 1e4, "천": 1e3}
    matches = re.findall(r"\d+(?:\.\d+)?\s*(조|억|만|천)달러", claim.source_sentence)
    return 0.5 * min((scales[item] for item in matches), default=1.0)
