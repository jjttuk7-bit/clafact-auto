"""Provider-neutral structured claim extraction adapter."""
from collections.abc import Callable
from datetime import date
from typing import Any
from schemas.claim import ClaimSchema

class StructuredOutputAdapter:
    def __init__(self, invoke: Callable[[str], dict[str, Any]]) -> None:
        self.invoke = invoke
    def extract(
        self, source_sentence: str, *, article_published_at: date | None = None
    ) -> ClaimSchema:
        del article_published_at
        return ClaimSchema.model_validate(self.invoke(source_sentence))
