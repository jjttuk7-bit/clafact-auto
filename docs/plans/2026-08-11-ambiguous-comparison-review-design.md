# Ambiguous Comparison Review Queue Design

Build a deterministic JSONL review queue from registry records whose claim has
`parse_reason` or enrichment reason `AMBIGUOUS_COMPARISON`. Each queue row keeps
the source keys, sentence, current slots, missing decision fields, and all
version fields. No value is inferred.

A separate JSONL decision file accepts only a matching source key and explicit
`APPROVED` or `REJECTED` status. Approved decisions must include comparison and
calculation fields. Applying decisions produces a new result stream: approved
records receive only the declared slot updates; rejected or undecided records
remain HOLD. Duplicate, unknown, or incomplete decisions fail validation.
