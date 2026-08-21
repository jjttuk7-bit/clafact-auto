# CLAFACT-AUTO Canonical Pipeline Design

## Objective

Make `core.unified_claim_pipeline` the only orchestration path for article, batch, and Registry verification, and construct its official evidence dependency exclusively with `build_official_evidence_service_v3`.

## Selected approach

Use a thin-adapter architecture:

- `core.unified_claim_pipeline` owns article parsing, child Claim recovery, re-Admission, official verification, terminal routing, and serialization boundaries.
- A canonical runtime factory owns paths, Structured Output extractor creation, and the v3 official engine.
- Streamlit converts `ArticlePipelineResult` entries into presentation rows only.
- Batch verification invokes the same article method once per article and flattens its entries without enforcing one Claim per sentence.
- Registry verification invokes the same record-level function used internally by article verification.
- The full Registry runner writes checkpointed JSONL rows and a deterministic stage report so interrupted official runs can resume.

This keeps UI and CLI concerns out of the Core Engine while preserving the existing schemas and official adapters.

## Data flow

```text
Article adapter / Batch adapter
  -> CanonicalPipeline.verify_article
  -> parse_article_claims
  -> verify_registry_record
  -> recover_registry_record_v3
  -> OfficialEvidenceService v3
  -> live KOSIS Catalog + metadata
  -> Hard Guard + semantic match + evidence coordinate
  -> live KOSIS value + publication lookup
  -> deterministic Python calculation
  -> PipelineEntry(AUTO | HOLD, reason, trace, provenance)

Registry CLI
  -> load ClaimRegistryRecord
  -> verify_registry_record (same function)
  -> checkpoint/result JSONL
  -> stage/failure summary JSON
```

## Error handling

- External failures never abort the entire Registry.
- Each failure is preserved with its operational stage, stable reason code, and diagnostic identifier/hash.
- Structural HOLD and operational failure remain separate.
- Resume skips only records that already have a complete checkpoint result.
- No cached value may replace a required live lookup in this acceptance run.

## Acceptance criteria

1. Streamlit single verification calls the canonical runtime.
2. Streamlit batch accepts multiple derived Claims and calls the same runtime.
3. CLI Registry processing calls the same record-level function as article processing.
4. Runtime construction uses the v3 semantic/catalog/coordinate/publication overlays.
5. Existing tests and new integration-contract tests pass.
6. The 1542-record Registry is attempted against live official APIs with checkpointing.
7. The final report includes parent/child counts, terminal routes, reason codes, official resolution count, and stage-level pass/hold/failure counts.
8. Results distinguish successful official verification, justified HOLD, and operational failure.

