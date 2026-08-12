# Official KOSIS Metadata Cache Design

## Goal

Resolve official KOSIS item, dimension, and member coordinates for unseen Claims
without adding Claim-specific mappings and without downloading a large table's
metadata for every verification.

## Diagnosis

KOSIS `getMeta&type=ITM` returns both measurement items (`OBJ_ID=ITEM`) and
classification members (`OBJ_ID!=ITEM`). Large classification tables can contain
thousands of members, so the current five-second, per-request live hydration is
not a reliable online lookup strategy. The repository already contains versioned
official metadata snapshots, but the Streamlit single-Claim path does not use
them before calling KOSIS.

## Contract

1. Read versioned official Snapshots before the network and verify their SHA-256
   against a committed manifest.
2. Cache metadata by `(org_id, table_id, meta_type)` for the process lifetime.
3. Call the official KOSIS adapter only when no Snapshot contains the table.
4. Cache successful live responses, including empty official responses, so one
   request never causes repeated downloads.
   KOSIS error payloads and structurally invalid responses are never cached.
5. Never persist API keys or include them in cache keys, logs, or snapshots.
6. Feed the resulting official rows through the existing metadata normalizer;
   do not create a separate Profile or Claim-specific coordinate map.
7. Use the same repository contract in the single-Claim UI and the batch engine.
8. Use a per-coordinate single-flight lock so duplicate requests share one call
   while different tables remain concurrent.

## Verification

- Snapshot hit performs zero live calls.
- Repeated live lookup performs one call.
- ITM and PRD remain independently cached.
- Large official ITM metadata hydrates item and dimension member coordinates.
- UI and batch tests prove they use the same Snapshot-first contract.
