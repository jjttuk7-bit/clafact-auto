"""Append-only JSONL persistence for pipeline stage results."""

from __future__ import annotations

from pathlib import Path

from schemas.stage_result import StageResultSchema


class StageResultStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[StageResultSchema]:
        if not self.path.exists():
            return []
        return [
            StageResultSchema.model_validate_json(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def append(self, result: StageResultSchema) -> None:
        key = (result.child_claim_id, result.stage, result.attempt)
        existing_keys = {
            (event.child_claim_id, event.stage, event.attempt)
            for event in self.load()
        }
        if key in existing_keys:
            raise ValueError(
                "DUPLICATE_STAGE_RESULT:"
                f"{result.child_claim_id}:{result.stage}:{result.attempt}"
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as output:
            output.write(result.model_dump_json())
            output.write("\n")

