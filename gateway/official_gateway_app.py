"""FastAPI Gateway that runs the existing official KOSIS Core Engine."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from secrets import compare_digest

from fastapi import FastAPI, Header, HTTPException

from config.settings import Settings
from core.official_evidence_service import OfficialEvidenceService
from core.official_engine_factory import OfficialEnginePaths, build_official_evidence_service
from schemas.official_gateway import GatewayVerifyRequest, GatewayVerifyResponse

OfficialEvidenceServiceFactory = Callable[[], OfficialEvidenceService]


def create_gateway_app(
    service_factory: OfficialEvidenceServiceFactory,
    *,
    gateway_token: str | None,
) -> FastAPI:
    """Create a token-protected HTTP boundary around the official evidence engine."""
    app = FastAPI(title="CLAFACT-AUTO Official KOSIS Gateway", version="1.0")

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


app = create_gateway_app(
    build_gateway_evidence_service,
    gateway_token=Settings().gateway_token,
)