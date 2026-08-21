"""Batch entrypoint for target-aware multi-Claim recovery."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import core.admission_recovery_batch_v2 as batch_v2
from core.admission_recovery import OfficialEvidenceResolver
from core.admission_recovery_v3 import recover_registry_record_v3
from core.claim_parser import StructuredClaimExtractor
from schemas.claim_registry import ClaimRegistryRecord


def run_admission_recovery_batch_v3(
    records: Iterable[ClaimRegistryRecord],
    *,
    extractor: StructuredClaimExtractor,
    official_service: OfficialEvidenceResolver,
    article_context_by_id: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    batch_v2.recover_registry_record_v2 = recover_registry_record_v3
    return batch_v2.run_admission_recovery_batch_v2(
        records,
        extractor=extractor,
        official_service=official_service,
        article_context_by_id=article_context_by_id,
    )
