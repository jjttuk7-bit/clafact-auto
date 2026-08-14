# Multi-Claim Input UI Design

## Goal

Make the Streamlit input explicitly accept a news sentence or article body, then make every
independent Claim visible and independently inspectable after Claim Split.

## Chosen approach

Use a two-level result view:

1. Display a Claim results table immediately after parsing and verification.  Each row contains
   the source Claim text, indicator, article value, time, parse state, and verdict route.
2. Keep one selectbox below the table for the detailed view.  The selected row alone renders
   its 12-slot JSON, KOSIS candidates, evidence cells, verdict, and downloads.

The UI must persist the completed run in Streamlit session state.  Selecting a different Claim
reruns Streamlit; without session state the original button is no longer true and all result
widgets disappear.  Persisting the parsed Claim list and resolutions fixes that interaction
without rerunning OpenAI or KOSIS for a mere selection change.

## Alternatives considered

- Render all detailed results at once: simple but makes a multi-Claim article long and slow.
- Require the user to paste one Claim only: contradicts Article → Claim Split pipeline.
- Table plus persistent selected detail: chosen because it proves every extracted Claim exists
  while retaining a readable evidence detail view.

## Error handling

Each Claim retains its own parse status and verdict.  A single HOLD does not block other
AUTO_OK Claims from being resolved.  If no numerical Claim is found, preserve the existing
NO_NUMERICAL_CLAIM_CANDIDATE error.

## Test contract

- A two-Claim article produces two rows in the result summary.
- The summary names the input as a sentence or article body.
- Selecting another Claim reads the persisted result instead of requiring a second execution.
