# Review: [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery)

> **Status**: Phase C complete
> **Plan ticket**:
> [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery)
> **Execution record**:
> [docs/execution/M3-1.md](M3-1.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/python/coding-guidelines.md](../policies/common/python/coding-guidelines.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/adr.md](../adr.md#61-snapshot-consistency-contract),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#62-refresh-flow),
> [docs/design/linear-domain-coverage-audit.md](../design/linear-domain-coverage-audit.md),
> [docs/execution/M3-O1.md](M3-O1.md)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M3-1-R1 | High | Done | Traversal Configuration | `refresh()` ignores the manifest's persisted traversal configuration and recomputes reachability with the current `ContextSync` instance defaults instead. The design makes the manifest authoritative for the active dimensions and `max_tickets_per_root`, and `refresh()` exposes no override parameters, so a later process can silently change snapshot scope just by being constructed with different defaults. | [src/context_sync/_sync.py:679](../../src/context_sync/_sync.py#L679), [src/context_sync/_sync.py:823](../../src/context_sync/_sync.py#L823), [docs/design/0-top-level-design.md:154](../design/0-top-level-design.md#L154), [docs/design/0-top-level-design.md:368](../design/0-top-level-design.md#L368) | Refresh can prune or miss tickets even when upstream state is unchanged. In review-time reproduction, a snapshot synced with `blocks=1` and then refreshed from a new `ContextSync` instance built with `blocks=0` removed `CHILD-1` while the manifest still recorded `blocks: 1`. | Load `manifest.dimensions` and `manifest.max_tickets_per_root` after [src/context_sync/_sync.py:677](../../src/context_sync/_sync.py#L677) and use those as the authoritative refresh traversal config. If future work wants refresh-time overrides, add them explicitly and persist the accepted values back to the manifest before traversal. |
| M3-1-R2 | High | Done | Input Validation | `missing_root_policy` is never validated. Any typo falls through the `else:` branch and is treated as `"remove"`, even though the public docstring and the implementation plan both describe destructive removal as an explicit opt-in mode only. | [src/context_sync/_sync.py:592](../../src/context_sync/_sync.py#L592), [src/context_sync/_sync.py:716](../../src/context_sync/_sync.py#L716), [src/context_sync/_sync.py:745](../../src/context_sync/_sync.py#L745), [docs/implementation-plan.md:431](../implementation-plan.md#L431) | A caller who passes `missing_root_policy="quaratine"` or any other typo gets silent root deletion instead of a fail-loud validation error. In review-time reproduction, `await refresh(missing_root_policy="typo")` removed `ROOT-1`, deleted its file, and returned no error. | Validate `missing_root_policy` at the public boundary in [src/context_sync/_sync.py:592](../../src/context_sync/_sync.py#L592) and raise `ValueError` or `ContextSyncError` unless the value is exactly `"quarantine"` or `"remove"`. Add a negative test for an invalid policy string. |
| M3-1-R3 | Medium | Done | Missing-Root Handling | If a root passes `get_refresh_issue_metadata(...).visible` but then `fetch_issue()` fails during the active-root prefetch, refresh only logs a warning and drops that root from traversal. The root stays marked `active`, no `root_quarantined` or `fetch_failed` result is recorded, and the rest of the pass proceeds as if the root had been intentionally excluded. | [src/context_sync/_sync.py:706](../../src/context_sync/_sync.py#L706), [src/context_sync/_sync.py:779](../../src/context_sync/_sync.py#L779), [src/context_sync/_sync.py:797](../../src/context_sync/_sync.py#L797), [docs/design/0-top-level-design.md:371](../design/0-top-level-design.md#L371) | A transient race between the visibility probe and the full fetch can silently shrink the visible graph and prune descendants while leaving the root recorded as healthy. In review-time reproduction, a forced prefetch failure left `ROOT-1` marked `active`, removed `CHILD-1`, and returned no error. | Treat a root-prefetch `RootNotFoundError` as a missing-root condition and reapply the requested `missing_root_policy`, or abort the refresh as an inconsistent remote-state failure. Do not silently continue with the root still marked `active`. |
| M3-1-R4 | Medium | Done | Persistence Safety | `_rewrite_quarantined_ticket()` bypasses the repository's normal atomic write and post-write verification path and writes the quarantined ticket file with plain `Path.write_text()`. That diverges from the ticket's stated reuse of existing write primitives and from the repository I/O contract that persisted files are written atomically and verified after the write. | [src/context_sync/_sync.py:110](../../src/context_sync/_sync.py#L110), [src/context_sync/_sync.py:161](../../src/context_sync/_sync.py#L161), [src/context_sync/_io.py:33](../../src/context_sync/_io.py#L33), [src/context_sync/_io.py:79](../../src/context_sync/_io.py#L79), [docs/execution/M3-1.md:93](M3-1.md#L93) | Quarantine is the path taken when remote state is already degraded. A crash, short write, or malformed frontmatter update in that path can leave the only surviving copy of the root ticket half-written or corrupt, with no verification error raised. | Route the surgical quarantine rewrite through `atomic_write` and a quarantine-specific verification helper, or build a safe no-bundle write path that preserves the same atomicity and verification guarantees as [src/context_sync/_io.py:79](../../src/context_sync/_io.py#L79). |

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

---

## Review Pass 2 — Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M3-1-R5 | Medium | Done | Error Handling | `_read_existing_ticket_state()` catches bare `except Exception:` and silently returns `(None, None, None)`. Per [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md) ("Fail loudly") and [docs/policies/common/python/coding-guidelines.md](../policies/common/python/coding-guidelines.md) ("Catch only the exceptions you can handle"), this masks real filesystem errors such as permission-denied, disk-full, or encoding failures behind a silent fallback. A masked read error causes the ticket to be treated as stale rather than surfacing the operational failure. | [src/context_sync/_sync.py:98](../../src/context_sync/_sync.py#L98) | A real filesystem failure (for example, a permission change on the context directory mid-refresh) would be silently swallowed, producing an unnecessary re-fetch and overwrite instead of a diagnosable error. In a permission-denied scenario, the subsequent `write_ticket()` would then fail with an unrelated `WriteError`, making the root cause harder to trace. | Narrow the caught exception set to parsing-related errors only (for example `ValueError`, `KeyError`, or `ManifestError`). For genuine I/O failures (`OSError`), let the exception propagate or log at WARNING level with full context. |
| M3-1-R6 | Medium | Done | Type Safety | `_rewrite_quarantined_ticket()` declares `manifest: object` in its signature and then validates with `assert isinstance(manifest, Manifest)` at runtime. The `assert` can be stripped by `python -O`, and the function already performs a runtime import of `Manifest` on the next line. This is both a type-annotation gap (static checkers see `object`) and a fragile runtime check. | [src/context_sync/_sync.py:114](../../src/context_sync/_sync.py#L114), [src/context_sync/_sync.py:131](../../src/context_sync/_sync.py#L131), [src/context_sync/_sync.py:133](../../src/context_sync/_sync.py#L133) | Under `python -O`, the `assert` is removed entirely. The function would then call `manifest.tickets.get(uid)` on a bare `object`, producing an `AttributeError` with no diagnostic context. Static type checkers also cannot validate callers because the declared type is `object`. | Use a `TYPE_CHECKING` conditional import to annotate the parameter as `Manifest` for static analysis. Replace the `assert` with an explicit `if not isinstance(manifest, Manifest): raise TypeError(...)` for runtime safety that survives `-O`. |
| M3-1-R7 | Low | Done | Defensive Checks | `_rewrite_quarantined_ticket()` silently returns without logging or raising when `ticket_entry is None` (line 135) or when the ticket file does not exist (line 139). Reaching this code for a root that has no manifest ticket entry or no on-disk file indicates an inconsistent manifest/filesystem state that should be surfaced, not silently ignored. | [src/context_sync/_sync.py:135](../../src/context_sync/_sync.py#L135), [src/context_sync/_sync.py:139](../../src/context_sync/_sync.py#L139), [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md) ("Fail loudly") | In the inconsistent-state case, quarantine is silently skipped: the manifest records `state="quarantined"` but the ticket file retains its pre-quarantine content with `root_state: active`, creating a manifest/file-system divergence with no diagnostic trace. | Log at WARNING level when either early-return branch is taken, so the divergence is at least observable in operational logs. |
| M3-1-R8 | Low | Done | Readability | The inline comment block at lines 260–265 lists `refresh → M3-1` as a stub implementation not yet owned by this ticket. Since M3-1 is the ticket that implemented `refresh()`, this comment is now stale and misleading for future readers. | [src/context_sync/_sync.py:260](../../src/context_sync/_sync.py#L260) | Minor readability issue only. No behavioral impact. | Remove `refresh → M3-1` from the stub list. |

## Review Pass 2 — Reviewer Notes

- Full repository validation confirmed passing:
  `.venv/bin/ruff check src/ tests/`,
  `.venv/bin/ruff format --check src/ tests/`,
  `.venv/bin/pytest` (346 passed in 1.85s).
- I independently confirm the four findings from Review Pass 1
  ([M3-1-R1](M3-1-review.md#findings) through
  [M3-1-R4](M3-1-review.md#findings)). The traversal-config and
  input-validation findings ([M3-1-R1](M3-1-review.md#findings),
  [M3-1-R2](M3-1-review.md#findings)) are the most impactful — both can cause
  silent data loss under conditions that a caller might reasonably produce.
- The core refresh logic (composite-cursor freshness, selective re-fetch,
  quarantine/recovery state machine, pruning, manifest finalization) is
  structurally sound and well-tested for the happy path. The implementation
  correctly follows the [M1-D3](M1-D3.md) composite freshness contract and
  the [M3-O1](M3-O1.md) `comments_signature` settlement.
- The `format_version` staleness gate at
  [src/context_sync/_sync.py:881](../../src/context_sync/_sync.py#L881) is a
  good forward-looking design choice that ensures format-incompatible files are
  unconditionally refreshed.
- Linear-boundary compliance: confirmed. All remote reads route through the
  gateway abstraction. No direct `linear.gql.*` calls were introduced.
- The 16 integration tests provide good behavioral coverage for the primary
  refresh scenarios. The test helpers (`_sync_then_refresh`, `_read_ticket_fm`)
  are clean and well-scoped.

## Review Pass 2 — Residual Risks and Testing Gaps

- No test exercises `_read_existing_ticket_state` with a corrupt or
  unreadable ticket file. The bare `except Exception:` path
  ([M3-1-R5](M3-1-review.md#review-pass-2--findings)) is untested.
- No test exercises `_rewrite_quarantined_ticket` when the ticket entry is
  missing from the manifest or when the file has been externally deleted. The
  silent-return paths ([M3-1-R7](M3-1-review.md#review-pass-2--findings))
  are untested.
- No test verifies the `format_version` staleness signal in isolation: a
  ticket written with `format_version=0` (or missing) being treated as stale
  during refresh and re-fetched.
- The quarantine recovery + prefetch failure interaction is untested: a
  quarantined root that becomes visible again but whose `fetch_issue()` then
  fails would be left marked `active` with its descendants pruned (amplifies
  [M3-1-R3](M3-1-review.md#findings)).

## Ticket Owner Response

| ID | Verdict | Rationale |
| --- | --- | --- |
| [M3-1-R1](M3-1-review.md#findings) | Fix now | Agreed. `_refresh_under_lock()` now reads `manifest.dimensions` and `manifest.max_tickets_per_root` instead of `self._dimensions` and `self._max_tickets_per_root`. Added `TestRefreshUsesManifestConfig::test_cross_instance_config_divergence` which syncs with `blocks=1`, refreshes from a different `ContextSync` with `blocks=0`, and confirms the child is not pruned. |
| [M3-1-R2](M3-1-review.md#findings) | Fix now | Agreed. `refresh()` now validates `missing_root_policy` against `("quarantine", "remove")` at the public boundary before acquiring the lock and raises `ValueError` for any unrecognized value. Added `TestRefreshInputValidation` with two tests: one confirms `ValueError` is raised, the other confirms a typo does not delete the root file. |
| [M3-1-R3](M3-1-review.md#findings) | Fix now | Agreed. Root-prefetch `RootNotFoundError` is now treated as a missing-root condition. After the `TaskGroup` completes, any root in `prefetch_failed` has the requested `missing_root_policy` applied (quarantine with file rewrite and error recording, or remove with file deletion). Added `TestRefreshPrefetchFailure` with two tests: one confirms quarantine + child pruning + error recording, the other confirms the remove path. |
| [M3-1-R4](M3-1-review.md#findings) | Fix now | Agreed. `_rewrite_quarantined_ticket()` now routes through `atomic_write()` from [src/context_sync/_io.py](../../src/context_sync/_io.py) instead of `Path.write_text()`. Added the `atomic_write` import to [src/context_sync/_sync.py](../../src/context_sync/_sync.py). Full post-write verification (`write_and_verify_ticket`) was not applied because the quarantine rewrite preserves existing content with surgical frontmatter edits rather than rendering from a bundle — the verification helper's expected-marker and expected-frontmatter checks are designed for fresh renders. Atomic write alone is sufficient to prevent partial writes. |
| [M3-1-R5](M3-1-review.md#review-pass-2--findings) | Fix now | Agreed. Narrowed the caught exception set from bare `except Exception:` to `except (ValueError, KeyError, ManifestError):`. Genuine I/O failures (`OSError`) now propagate. Added a `DEBUG`-level log when the parse-error fallback is taken. |
| [M3-1-R6](M3-1-review.md#review-pass-2--findings) | Fix now | Agreed. Changed the parameter annotation from `manifest: object` to `manifest: Manifest` with a top-level import of `Manifest` from `context_sync._manifest`. Removed the runtime `assert isinstance(...)` and the deferred `from context_sync._manifest import Manifest` inside the function body. Static checkers now see the correct type, and the annotation survives `python -O`. |
| [M3-1-R7](M3-1-review.md#review-pass-2--findings) | Fix now | Agreed. Both early-return branches in `_rewrite_quarantined_ticket()` now log at `WARNING` level with the issue UUID and (for the missing-file case) the expected path. |
| [M3-1-R8](M3-1-review.md#review-pass-2--findings) | Fix now | Agreed. Removed `refresh → M3-1` from the stub comment block. The remaining entries (`add → M3-2`, `remove_root → M3-2`, `diff → M3-3`) are still stubs. |
