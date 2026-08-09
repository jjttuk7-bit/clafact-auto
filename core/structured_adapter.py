"""Provider-neutral structured claim extraction adapter."""
from collections.abc import Callable
from typing import Any
from schemas.claim import ClaimSchema

class StructuredOutputAdapter:
    def __init__(self, invoke: Callable[[str], dict[str, Any]]) -> None:
        self.invoke = invoke
    def extract(self, source_sentence: str) -> ClaimSchema:
        return ClaimSchema.model_validate(self.invoke(source_sentence))
