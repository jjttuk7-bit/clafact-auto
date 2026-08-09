# HCX Claim Contract and emit_claim Design

## Goal

Make the HCX claim-extraction boundary faithfully emit all 12 semantic slots, represent every optional value with an explicit nullable JSON Schema type, and provide one constrained `emit_claim` Function Calling alternative without giving the model authority over KOSIS retrieval, calculation, or verdicts.

## Confirmed provider constraint

HCX-007 supports both Structured Outputs and Function Calling, but NAVER Cloud documents that Structured Outputs, Function Calling, and Thinking cannot be requested simultaneously. The implementation therefore exposes two mutually exclusive extraction modes that share one schema:

1. `responseFormat` Structured Output (default and existing production path)
2. one forced `emit_claim` Function Call (optional alternative)

Official references:

- https://api.ncloud-docs.com/docs/clovastudio-chatcompletionsv3-so
- https://api.ncloud-docs.com/docs/clovastudio-chatcompletionsv3-fc
- https://guide.ncloud-docs.com/docs/clovastudio-model

## Shared contract

The 12 semantic slots are:

`indicator`, `value`, `unit`, `time`, `frequency`, `region`, `population`, `dimension`, `comparison`, `calculation`, `condition`, and `source_hint`.

The response also contains the metadata fields `claim_id`, `source_sentence`, `parse_status`, and `parse_reason`.

All 16 keys are listed in JSON Schema `required`. Optional semantics are expressed by explicit nullable types, not by omitted keys:

- strings: `type: ["string", "null"]`
- numeric value: `type: ["number", "null"]`
- mapping slots: `type: ["object", "null"]` with string-valued `additionalProperties`
- `parse_status`: non-null enum `AUTO_OK`, `HOLD`, `HUMAN_REVIEW`

The root schema forbids extra properties. Pydantic `ClaimSchema` remains the final runtime validator.

## Components

### Schema factory

A provider-neutral module owns the canonical JSON Schema and `emit_claim` tool definition. Both HCX request modes import it, preventing the Structured Output and Function Calling contracts from drifting apart.

### Structured Output extractor

The existing `HcxClaimExtractor` sends `responseFormat` only. It does not send `tools` or `toolChoice`. The returned JSON content is validated by `ClaimSchema` and normalized as today.

### Function Calling extractor

`HcxFunctionClaimExtractor` sends exactly one function tool named `emit_claim`, with the shared Claim JSON Schema as `function.parameters`, and forces that function through `toolChoice`. It does not send `responseFormat` or `thinking`.

It accepts exactly one tool call, requires type `function` and name `emit_claim`, validates `function.arguments` through `ClaimSchema`, and returns the Claim object. It never dispatches a model-selected Python function.

## Security and authority boundary

The only LLM-produced object is a structured Claim interpretation. The function interface is a typed return envelope, not an execution router.

The following remain direct Python calls controlled by the application:

- semantic normalization
- catalog search
- Hard Guard
- semantic matching and Top1/Top2 margin
- Evidence Cell resolution
- KOSIS API or official Snapshot lookup
- deterministic calculation
- verdict and review routing

No KOSIS tool, calculation tool, or verdict tool is exposed to HCX.

## Error handling

Reject, rather than repair, these Function Calling responses:

- missing `toolCalls`
- zero or multiple tool calls
- wrong tool type or function name
- non-object arguments
- missing required Claim keys
- extra keys
- incorrect nullable or mapping value types

Provider/network errors continue to propagate to the existing HOLD/error boundary; secrets are never included in errors or logs.

## Tests

Contract tests must prove:

1. all 12 semantic slots exist in `properties` and `required`
2. every nullable field declares its null type explicitly
3. `dimension`, `comparison`, and `condition` are nullable string maps
4. Structured Output and `emit_claim` reuse the same schema
5. a complete all-null optional payload validates
6. valid tool-call arguments produce `ClaimSchema`
7. wrong name, multiple calls, missing fields, extra fields, and bad types are rejected
8. HCX Structured Output requests contain no tools
9. HCX Function Calling requests contain no `responseFormat` or `thinking`
10. repository search confirms no KOSIS/calculation/verdict function is exposed as an HCX tool

