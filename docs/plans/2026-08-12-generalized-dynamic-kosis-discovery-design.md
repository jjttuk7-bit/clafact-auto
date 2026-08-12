# Generalized Dynamic KOSIS Discovery Design

## Problem

CLAFACT-AUTO must not require sentence-specific profiles or code branches. A new Claim must be parsed into the shared 12-slot schema and either reach evidence-backed AUTO or stop at a precise HOLD stage. The sentence `올해 1분기 중고차 수출액은 지난해보다 31% 증가했다.` exposed four class-level gaps: unresolved relative quarters, local-catalog short-circuiting, unbounded sequential metadata hydration, and masked runtime exceptions.

## Design principles

- Never add a condition for one sentence, Claim ID, or one product name.
- Treat indicator, dimensions, time, comparison, and calculation as independent reusable constraints.
- Use local catalog candidates as a cache, not as permission to suppress official live search.
- Run Hard Guard before semantic scoring and never force an ambiguous Top-1.
- Convert operational failures into stage-specific HOLD results while logging a secret-free diagnostic reference.

## Data flow

1. Resolve relative target periods from `article_published_at`, including year, half-year, quarter, and month expressions.
2. Parse and normalize the Concept and all dimension member values.
3. Search the local catalog.
4. Determine whether local candidates contain enough metadata and Claim context to enter Hard Guard.
5. If they do not, search the official KOSIS catalog with contextual queries such as `중고차 수출액`, merge identities, deduplicate, and rank.
6. Hydrate only the highest-ranked candidates within an explicit request budget.
7. Continue through Hard Guard, semantic matching, evidence coordinates, official values, deterministic calculation, and verdict.
8. On an adapter failure, preserve the failed stage and a diagnostic ID; never expose credentials or raw provider responses in the UI.

## Search expansion rule

Live search is required when there is no local candidate, when local candidates have unresolved metadata, or when no local candidate represents the Claim's non-total dimension members in its table scope or official members. Local and live candidates are merged; live results do not automatically outrank structurally compatible local metadata.

## Latency boundary

Metadata hydration receives a small ranked-candidate budget. The default UI path must not sequentially hydrate eight unrelated candidates with two 20-second retries each. Unhydrated candidates remain identities only and cannot pass Hard Guard.

## Error handling

Expected uncertainty becomes a reason-coded HOLD. Unexpected exceptions are recorded with a stage and diagnostic ID in server logs, while the UI displays a safe message containing those two fields. API keys and response bodies are excluded.

## Test strategy

- Unit tests for relative quarter and half-year resolution.
- Unit tests proving contextual live search runs despite unrelated local candidates.
- Unit tests proving structurally sufficient local candidates do not trigger live search.
- Unit tests for merge/deduplication and metadata candidate budget.
- Streamlit test proving an exception is reported with stage and diagnostic ID rather than only `TypeError`.
- Regression execution for the used-car export Claim plus the existing unit, integration, and goldset suites.

## Completion criterion

The used-car sentence is not required to become AUTO unless KOSIS returns a unique official coordinate and both comparison values. It is required to resolve its target period, attempt the correct contextual official search, complete within the request budget, and return either evidence-backed AUTO or a precise stage-specific HOLD without an uncaught TypeError.
