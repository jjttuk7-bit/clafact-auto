"""Run Registry claims stage by stage with signature-bound checkpoints."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Callable

from core.stage_result_store import StageResultStore
from schemas.pipeline_trace import PipelineStageName
from schemas.stage_result import StageExecutionStatus, StageResultSchema


@dataclass(frozen=True, slots=True)
class StageOutcome:
    status: StageExecutionStatus
    output: object
    reason_code: str | None = None
    output_ref: str | None = None
    official_attempted: bool = False


StageHandler = Callable[[object], StageOutcome]


@dataclass(frozen=True, slots=True)
class StageDefinition:
    name: PipelineStageName
    handler: StageHandler
    code_version: str
    data_version: str
    official_lookup: bool = False


@dataclass(frozen=True, slots=True)
class StageRunResult:
    output: object
    terminal_status: StageExecutionStatus
    reason_code: str | None
    completed_stage_count: int
    executed_stage_count: int
    resumed_stage_count: int


class RegistryStageRunner:
    """Execute only invalid stages and stop at the first non-PASS outcome."""

    def __init__(self, checkpoint_root: Path, result_store: StageResultStore) -> None:
        self.checkpoint_root = checkpoint_root
        self.result_store = result_store

    def run(
        self,
        *,
        parent_claim_id: str,
        child_claim_id: str,
        initial_input: object,
        stages: list[StageDefinition],
    ) -> StageRunResult:
        payload = initial_input
        executed = resumed = completed = 0
        terminal_status: StageExecutionStatus = "PASS"
        terminal_reason: str | None = None

        for stage_index, definition in enumerate(stages, start=1):
            input_hash = _payload_hash(payload)
            fingerprint = _fingerprint(input_hash, definition)
            checkpoint_path = self._checkpoint_path(
                child_claim_id, stage_index, definition.name
            )
            checkpoint = _load_checkpoint(checkpoint_path, fingerprint)
            if checkpoint is not None:
                outcome = StageOutcome(
                    status=checkpoint["status"],
                    output=checkpoint["output"],
                    reason_code=checkpoint.get("reason_code"),
                    output_ref=checkpoint.get("output_ref"),
                    official_attempted=bool(checkpoint.get("official_attempted")),
                )
                resumed += 1
            else:
                started_at = _now()
                outcome = definition.handler(payload)
                _validate_outcome(definition, outcome)
                finished_at = _now()
                attempt = self._next_attempt(child_claim_id, definition.name)
                self.result_store.append(
                    StageResultSchema(
                        parent_claim_id=parent_claim_id,
                        child_claim_id=child_claim_id,
                        stage=definition.name,
                        status=outcome.status,
                        reason_code=outcome.reason_code,
                        input_hash=input_hash,
                        output_ref=outcome.output_ref,
                        started_at=started_at,
                        finished_at=finished_at,
                        code_version=definition.code_version,
                        data_version=definition.data_version,
                        attempt=attempt,
                    )
                )
                _write_checkpoint(
                    checkpoint_path,
                    fingerprint,
                    outcome,
                )
                executed += 1

            payload = outcome.output
            completed += 1
            terminal_status = outcome.status
            terminal_reason = outcome.reason_code
            if outcome.status != "PASS":
                break

        return StageRunResult(
            output=payload,
            terminal_status=terminal_status,
            reason_code=terminal_reason,
            completed_stage_count=completed,
            executed_stage_count=executed,
            resumed_stage_count=resumed,
        )

    def _checkpoint_path(
        self,
        child_claim_id: str,
        stage_index: int,
        stage_name: str,
    ) -> Path:
        safe_child = re.sub(r"[^0-9A-Za-z_.-]+", "_", child_claim_id).strip("_")
        if not safe_child:
            safe_child = sha256(child_claim_id.encode("utf-8")).hexdigest()[:16]
        return self.checkpoint_root / safe_child / f"{stage_index:02d}_{stage_name}.json"

    def _next_attempt(self, child_claim_id: str, stage: str) -> int:
        attempts = [
            event.attempt
            for event in self.result_store.load()
            if event.child_claim_id == child_claim_id and event.stage == stage
        ]
        return max(attempts, default=0) + 1


def _validate_outcome(definition: StageDefinition, outcome: StageOutcome) -> None:
    if outcome.status != "PASS" and not outcome.reason_code:
        raise ValueError("NON_PASS_REQUIRES_REASON_CODE")
    if outcome.status == "HOLD" and (
        not definition.official_lookup or not outcome.official_attempted
    ):
        raise ValueError("HOLD_REQUIRES_OFFICIAL_ATTEMPT")
    if definition.official_lookup and outcome.status == "PASS" and not outcome.official_attempted:
        raise ValueError("OFFICIAL_PASS_REQUIRES_OFFICIAL_ATTEMPT")


def _fingerprint(input_hash: str, definition: StageDefinition) -> str:
    canonical = json.dumps(
        {
            "input_hash": input_hash,
            "stage": definition.name,
            "code_version": definition.code_version,
            "data_version": definition.data_version,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _payload_hash(payload: object) -> str:
    canonical = json.dumps(
        _serialize(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _serialize(value: object) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    raise TypeError(f"STAGE_OUTPUT_NOT_JSON_SERIALIZABLE:{type(value).__name__}")


def _load_checkpoint(path: Path, fingerprint: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("fingerprint") != fingerprint:
        return None
    outcome = payload.get("outcome")
    return outcome if isinstance(outcome, dict) else None


def _write_checkpoint(
    path: Path,
    fingerprint: str,
    outcome: StageOutcome,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(
            {
                "fingerprint": fingerprint,
                "outcome": {
                    "status": outcome.status,
                    "output": _serialize(outcome.output),
                    "reason_code": outcome.reason_code,
                    "output_ref": outcome.output_ref,
                    "official_attempted": outcome.official_attempted,
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

