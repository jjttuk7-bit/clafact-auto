@echo off
cd /d "D:\projects\services\archived\clafact-auto\.worktrees\gold-standard-registry-v1"
set PYTHONPATH=D:\projects\services\archived\clafact-auto\.worktrees\gold-standard-registry-v1
"C:\Users\USER\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe" -m tools.run_e2e_batch "data\claim_registry\gold_standard_v1\claim_registry.jsonl" "data\semantic_standard\concept_seed_v1.json" "artifacts\gold_standard_v1_snapshot_collection_20260812" --catalog "data\kosis_catalog\catalog_350.json" --live-kosis --preparsed-registry --discovery-snapshot "data\kosis_snapshots\gold_standard_v1_execution_snapshot.json" --refresh-discovery-snapshot > "artifacts\gold_standard_v1_snapshot_collection_20260812.log" 2>&1
