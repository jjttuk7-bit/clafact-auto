# Profile Legacy Removal Design

## Goal
Remove Profile-based execution contracts from the standard CLAFACT-AUTO service. The only supported verification route is the 12-slot dynamic KOSIS pipeline.

## Scope
- Replace Profile-named operator UI queue with a generic review queue.
- Delete profile-only pilot commands and tests after confirming they are not imported by the standard batch command.
- Retain no Profile fallback in `tools/run_e2e_batch.py` or `core/dynamic_e2e_batch_runner.py`.
- Keep Gold Registry, KOSIS snapshots, and review queue artifacts unchanged.

## Safety
Deletion is limited to modules with no standard-engine imports. Every deletion is preceded by `rg` reference checks and followed by full import/test verification.
