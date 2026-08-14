"""FastAPI Gateway that runs the existing official KOSIS Core Engine."""

from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path
from secrets import compare_digest
from time import perf_counter

from fastapi import FastAPI, Header, HTTPException

from config.settings import Settings
from core.kosis_openapi_transport import get_meta
from core.official_evidence_service import OfficialEvidenceService
from core.official_engine_factory import OfficialEnginePaths, build_official_evidence_service
from schemas.official_gateway import GatewayVerifyRequest, GatewayVerifyResponse

OfficialEvidenceServiceFactory = Callable[[], OfficialEvidenceService]
KosisMetadataProbe = Callable[[], int]
_LOGGER = logging.getLogger(__name__)


def create_gateway_app(
    service_factory: OfficialEvidenceServiceFactory,
    *,
    gateway_token: str | None,
    kosis_metadata_probe: KosisMetadataProbe | None = None,
) -> FastAPI:
    """Create a token-protected HTTP boundary around the official evidence engine."""
    app = FastAPI(title="CLAFACT-AUTO Official KOSIS Gateway", version="1.0")

    @app.middleware("http")
    async def log_safe_request_lifecycle(request, call_next):
        """Log only transport timing; never log credentials or Claim payloads."""
        started = perf_counter()
        _LOGGER.info("gateway_request_started method=%s path=%s", request.method, request.url.path)
        try:
            response = await call_next(request)
        except Exception as error:
            _LOGGER.warning(
                "gateway_request_failed path=%s exception_type=%s elapsed_ms=%d",
                request.url.path,
                type(error).__name__,
                (perf_counter() - started) * 1000,
            )
            raise
        _LOGGER.info(
            "gateway_request_finished path=%s status=%d elapsed_ms=%d",
            request.url.path,
            response.status_code,
            (perf_counter() - started) * 1000,
        )
        return response

    @app.get("/diagnostics/kosis")
    def diagnose_kosis(
        token: str | None = Header(default=None, alias="X-CLAFACT-GATEWAY-TOKEN"),
    ) -> dict[str, int | str]:
        if not gateway_token:
            raise HTTPException(status_code=503, detail="GATEWAY_AUTH_NOT_CONFIGURED")
        if token is None or not compare_digest(token, gateway_token):
            raise HTTPException(status_code=401, detail="GATEWAY_AUTH_REQUIRED")
        if kosis_metadata_probe is None:
            raise HTTPException(status_code=503, detail="KOSIS_DIAGNOSTIC_UNAVAILABLE")
        try:
            row_count = kosis_metadata_probe()
        except (RuntimeError, TypeError, ValueError) as error:
            _LOGGER.warning("kosis_probe_failed exception_type=%s", type(error).__name__)
            raise HTTPException(status_code=503, detail="KOSIS_DIAGNOSTIC_UNAVAILABLE") from None
        return {"status": "OK", "metadata_row_count": row_count}

    @app.post("/verify", response_model=GatewayVerifyResponse)
    def verify(
        request: GatewayVerifyRequest,
        token: str | None = Header(default=None, alias="X-CLAFACT-GATEWAY-TOKEN"),
    ) -> GatewayVerifyResponse:
        if not gateway_token:
            raise HTTPException(status_code=503, detail="GATEWAY_AUTH_NOT_CONFIGURED")
        if token is None or not compare_digest(token, gateway_token):
            raise HTTPException(status_code=401, detail="GATEWAY_AUTH_REQUIRED")
        resolution = service_factory().resolve(
            request.claim,
            article_date=request.article_date,
        )
        return GatewayVerifyResponse(
            concept=resolution.concept,
            candidates=resolution.candidates,
            verdict=resolution.verdict,
            catalog_diagnostics=resolution.catalog_diagnostics,
        )

    return app


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DATA_ROOT = _PROJECT_ROOT / "data"


def build_gateway_evidence_service() -> OfficialEvidenceService:
    """Build the direct KOSIS engine owned by the Gateway runtime."""
    settings = Settings()
    return build_official_evidence_service(
        OfficialEnginePaths(
            standard_path=_DATA_ROOT / "semantic_standard" / "concept_seed_v1.json",
            catalog_path=_DATA_ROOT / "kosis_catalog" / "catalog_350.json",
            as_of_metadata_paths=[
                _DATA_ROOT / "kosis_snapshots" / "goldset_pilot.json",
                _DATA_ROOT / "kosis_snapshots" / "official_cpi_202510.json",
                _DATA_ROOT / "kosis_snapshots" / "official_cpi_detail_current_axes_v1.json",
            ],
            metadata_manifest_paths=[
                _DATA_ROOT / "kosis_snapshots" / "cpi_detail_metadata_v1_manifest.json",
            ],
        ),
        kosis_api_key=settings.kosis_api_key,
    )


def probe_kosis_metadata() -> int:
    """Verify one official metadata call without returning its contents."""
    api_key = Settings().kosis_api_key
    if not api_key:
        raise RuntimeError("KOSIS_API_KEY_NOT_CONFIGURED")
    rows = get_meta(api_key, "101", "DT_1DA7001S", meta_type="ITM")
    if not isinstance(rows, list):
        raise RuntimeError("KOSIS_METADATA_INVALID_RESPONSE")
    return len(rows)


app = create_gateway_app(
    build_gateway_evidence_service,
    gateway_token=Settings().gateway_token,
    kosis_metadata_probe=probe_kosis_metadata,
)