# Read Guard and PMF

## Read-before-write guard
- Guard is enabled by default for all write operations.
- Write requires a recent read mark for the same doc (`TTL` default: 3600s).
- Guard checks doc `updated` version for optimistic conflict detection.
- Emergency bypass: `SIYUAN_ALLOW_UNSAFE_WRITE=true`.

## PMF
Header fields:
- `doc_id`
- `partial`
- `cursor`
- `timestamp`
- `updated`

## apply-patch safety subset
- Reject `partial=true`.
- Only allow update of existing blocks.
- Reject add/delete/reorder semantics.
- Require PMF to contain all current blocks to prevent accidental data loss.
