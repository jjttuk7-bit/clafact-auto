# Live KOSIS Coordinate Resolution Design

## Goal

Extend uploaded-news verification from table discovery to safe evidence-coordinate resolution and deterministic year-on-year calculation. The implementation must never manufacture KOSIS values or force an ambiguous table, item, or dimension selection.

## Confirmed constraints

- KOSIS integrated search returns table identities, not a complete item/dimension coordinate.
- The parameter-value API requires an explicit item and ordered dimension codes.
- The current Streamlit path performs only `DIRECT_VALUE` calculations.
- Existing official Goldset metadata proves exact CPI detail coordinates for `DT_1J22112`; the October 2025 batch sentence contains several values in one sentence.

## Selected design

1. Keep existing registered official coordinate profiles as the only source for automatic coordinate confirmation.
2. Add a resolver for a single, unambiguous registered CPI detail claim. It creates two evidence cells for the article period and same month one year earlier.
3. Execute `GROWTH_RATE` with the existing Python calculator after fetching both official values through the KOSIS API (with official snapshots only as a dated fallback).
4. Preserve the batch row count: a sentence containing multiple independent numeric claims remains a review item until the batch data contract supports a parent claim with child claims.
5. For live table-search-only results, retain `LIVE_CATALOG_METADATA_UNRESOLVED`; this proves search was attempted but prevents scoring and fetching without an official coordinate.

## Error handling

- Missing article date, no registered coordinate, ambiguous item/member mapping, unavailable historical value, or an as-of conflict route to HOLD.
- Hard Guard executes before semantic scoring and rejects incomplete live metadata.
- API credentials are read only from environment/secrets and are not included in logs or reports.

## Tests

- Test the resolver produces exact current/prior-year cells only for a unique registered profile.
- Test the calculator uses the two fetched values for `GROWTH_RATE`.
- Test an ambiguous multi-value sentence does not become AUTO.
- Run the full pytest suite and compile check before push.
