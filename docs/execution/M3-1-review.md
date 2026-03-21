# Review: [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery)

> **Status**: Phase B complete
> **Plan ticket**:
> [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery)
> **Execution record**:
> [docs/execution/M3-1.md](M3-1.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/coding-guidelines-python.md](../policies/common/coding-guidelines-python.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/adr.md](../adr.md#61-snapshot-consistency-contract),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#62-refresh-flow),
> [docs/design/linear-domain-coverage-audit.md](../design/linear-domain-coverage-audit.md),
> [docs/execution/M3-O1.md](M3-O1.md)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M3-1-R1 | High | Todo | Traversal Configuration | `refresh()` ignores the manifest's persisted traversal configuration and recomputes reachability with the current `ContextSync` instance defaults instead. The design makes the manifest authoritative for the active dimensions and `max_tickets_per_root`, and `refresh()` exposes no override parameters, so a later process can silently change snapshot scope just by being constructed with different defaults. | [src/context_sync/_sync.py:679](../../src/context_sync/_sync.py#L679), [src/context_sync/_sync.py:823](../../src/context_sync/_sync.py#L823), [docs/design/0-top-level-design.md:154](../design/0-top-level-design.md#L154), [docs/design/0-top-level-design.md:368](../design/0-top-level-design.md#L368) | Refresh can prune or miss tickets even when upstream state is unchanged. In review-time reproduction, a snapshot synced with `blocks=1` and then refreshed from a new `ContextSync` instance built with `blocks=0` removed `CHILD-1` while the manifest still recorded `blocks: 1`. | Load `manifest.dimensions` and `manifest.max_tickets_per_root` after [src/context_sync/_sync.py:677](../../src/context_sync/_sync.py#L677) and use those as the authoritative refresh traversal config. If future work wants refresh-time overrides, add them explicitly and persist the accepted values back to the manifest before traversal. |
| M3-1-R2 | High | Todo | Input Validation | `missing_root_policy` is never validated. Any typo falls through the `else:` branch and is treated as `"remove"`, even though the public docstring and the implementation plan both describe destructive removal as an explicit opt-in mode only. | [src/context_sync/_sync.py:592](../../src/context_sync/_sync.py#L592), [src/context_sync/_sync.py:716](../../src/context_sync/_sync.py#L716), [src/context_sync/_sync.py:745](../../src/context_sync/_sync.py#L745), [docs/implementation-plan.md:431](../implementation-plan.md#L431) | A caller who passes `missing_root_policy="quaratine"` or any other typo gets silent root deletion instead of a fail-loud validation error. In review-time reproduction, `await refresh(missing_root_policy="typo")` removed `ROOT-1`, deleted its file, and returned no error. | Validate `missing_root_policy` at the public boundary in [src/context_sync/_sync.py:592](../../src/context_sync/_sync.py#L592) and raise `ValueError` or `ContextSyncError` unless the value is exactly `"quarantine"` or `"remove"`. Add a negative test for an invalid policy string. |
| M3-1-R3 | Medium | Todo | Missing-Root Handling | If a root passes `get_refresh_issue_metadata(...).visible` but then `fetch_issue()` fails during the active-root prefetch, refresh only logs a warning and drops that root from traversal. The root stays marked `active`, no `root_quarantined` or `fetch_failed` result is recorded, and the rest of the pass proceeds as if the root had been intentionally excluded. | [src/context_sync/_sync.py:706](../../src/context_sync/_sync.py#L706), [src/context_sync/_sync.py:779](../../src/context_sync/_sync.py#L779), [src/context_sync/_sync.py:797](../../src/context_sync/_sync.py#L797), [docs/design/0-top-level-design.md:371](../design/0-top-level-design.md#L371) | A transient race between the visibility probe and the full fetch can silently shrink the visible graph and prune descendants while leaving the root recorded as healthy. In review-time reproduction, a forced prefetch failure left `ROOT-1` marked `active`, removed `CHILD-1`, and returned no error. | Treat a root-prefetch `RootNotFoundError` as a missing-root condition and reapply the requested `missing_root_policy`, or abort the refresh as an inconsistent remote-state failure. Do not silently continue with the root still marked `active`. |
| M3-1-R4 | Medium | Todo | Persistence Safety | `_rewrite_quarantined_ticket()` bypasses the repository's normal atomic write and post-write verification path and writes the quarantined ticket file with plain `Path.write_text()`. That diverges from the ticket's stated reuse of existing write primitives and from the repository I/O contract that persisted files are written atomically and verified after the write. | [src/context_sync/_sync.py:110](../../src/context_sync/_sync.py#L110), [src/context_sync/_sync.py:161](../../src/context_sync/_sync.py#L161), [src/context_sync/_io.py:33](../../src/context_sync/_io.py#L33), [src/context_sync/_io.py:79](../../src/context_sync/_io.py#L79), [docs/execution/M3-1.md:93](M3-1.md#L93) | Quarantine is the path taken when remote state is already degraded. A crash, short write, or malformed frontmatter update in that path can leave the only surviving copy of the root ticket half-written or corrupt, with no verification error raised. | Route the surgical quarantine rewrite through `atomic_write` and a quarantine-specific verification helper, or build a safe no-bundle write path that preserves the same atomicity and verification guarantees as [src/context_sync/_io.py:79](../../src/context_sync/_io.py#L79). |

## Reviewer Notes

- Full repository validation from the repo-local virtualenv passed:
  `.venv/bin/ruff check src/ tests/`,
  `.venv/bin/ruff format --check src/ tests/`,
  and `.venv/bin/pytest` (`346 passed in 2.81s`).
- Review-time reproduction for [M3-1-R1](M3-1-review.md#findings):
  syncing with `dimensions={"blocks": 1}` and then refreshing the same
  directory through a new `ContextSync` instance built with
  `dimensions={"blocks": 0}` pruned `CHILD-1` even though the manifest still
  recorded `blocks: 1`.
- Review-time reproduction for [M3-1-R2](M3-1-review.md#findings):
  `await syncer.refresh(missing_root_policy="typo")` removed the hidden root,
  deleted its file, and returned `removed=["ROOT-1"]` with no error.
- Review-time reproduction for [M3-1-R3](M3-1-review.md#findings):
  a gateway that returned `visible=True` from
  `get_refresh_issue_metadata()` but raised `RootNotFoundError` from the later
  root prefetch left the root `active`, pruned its only child, and returned no
  `errors` entry.
- I did not find a Linear-boundary violation in this ticket.
  [src/context_sync/_sync.py](../../src/context_sync/_sync.py)
  continues to route remote reads through the gateway abstraction rather than
  adding direct `linear.gql.*` calls.

## Residual Risks and Testing Gaps

- The refresh tests all use one `ContextSync` instance for both `sync()` and
  `refresh()`, so they never exercise the cross-session case where the
  constructor defaults diverge from the manifest's stored traversal config.
  Supporting context:
  [tests/test_refresh.py:38](../../tests/test_refresh.py#L38),
  [tests/test_refresh.py:68](../../tests/test_refresh.py#L68).
- There is no negative test for invalid `missing_root_policy`. Current
  coverage exercises only the default quarantine path and the exact-string
  `"remove"` path.
  Supporting context:
  [tests/test_refresh.py:220](../../tests/test_refresh.py#L220),
  [tests/test_refresh.py:338](../../tests/test_refresh.py#L338).
- No test simulates divergence between the visibility probe and the later
  active-root prefetch. The existing suite covers consistent hide/unhide
  behavior only.
  Supporting context:
  [tests/test_refresh.py:220](../../tests/test_refresh.py#L220),
  [tests/test_refresh.py:296](../../tests/test_refresh.py#L296).
