# Review: [M2-3](../implementation-plan.md#m2-3---full-snapshot-sync-flow)

> **Status**: Phase C complete
> **Plan ticket**:
> [M2-3](../implementation-plan.md#m2-3---full-snapshot-sync-flow)
> **Execution record**:
> [docs/execution/M2-3.md](M2-3.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/coding-guidelines-python.md](../policies/common/coding-guidelines-python.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/adr.md](../adr.md#51-sync-full-snapshot-rebuild),
> [docs/adr.md](../adr.md#7-failure-model),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#1-library-api),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#4-error-handling),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#61-sync-flow),
> [docs/design/linear-domain-coverage-audit.md](../design/linear-domain-coverage-audit.md)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M2-3-R1 | High | Done | Error Handling | `sync()` cannot honor the documented "partial success with `SyncResult.errors`" contract for linked-ticket fetch failures. The post-traversal fetch step delegates to `fetch_tickets()`, and that helper propagates any single `fetch_issue()` exception as an `ExceptionGroup`, so the run aborts before the later `errors.append(...)` path can execute. The design and ADR both say an isolated linked-ticket failure should be recorded in the result while successful tickets still write. | [src/context_sync/_pipeline.py:154](../../src/context_sync/_pipeline.py#L154), [src/context_sync/_pipeline.py:190](../../src/context_sync/_pipeline.py#L190), [src/context_sync/_sync.py:355](../../src/context_sync/_sync.py#L355), [src/context_sync/_sync.py:371](../../src/context_sync/_sync.py#L371), [docs/design/0-top-level-design.md:263](../design/0-top-level-design.md#L263), [docs/adr.md:500](../adr.md#L500), [docs/execution/M2-3.md:41](M2-3.md#L41), [tests/test_pipeline.py:188](../../tests/test_pipeline.py#L188) | A single unreachable non-root ticket can abort the entire sync pass and prevent otherwise healthy tickets from being refreshed or written. That turns a ticket-scoped failure into a full-run failure and breaks the caller-facing `SyncResult` contract the ticket says it implemented. | Split reachable-ticket fetch outcomes into ticket-scoped failures versus systemic failures. Keep aborting on systemic gateway errors, but collect not-found/not-visible linked-ticket failures into `SyncError` rows and continue writing the successfully fetched tickets. Add an integration test where traversal discovers a related ticket whose later `fetch_issue()` fails and assert the run completes with one `errors` entry. |
| M2-3-R2 | High | Done | Public API | The public library surface is still broken for real callers. The package docs and top-level design both say `ContextSync` accepts an authenticated `linear-client` `Linear` instance, but the constructor still stores that object without creating a gateway and leaves `self._gateway = None`. `sync()` then passes that `None` straight into `_sync_under_lock()`, which immediately calls `gateway.fetch_issue(...)`. In practice, the new sync flow only works through the private `_gateway_override` testing hook. | [src/context_sync/_sync.py:119](../../src/context_sync/_sync.py#L119), [src/context_sync/_sync.py:223](../../src/context_sync/_sync.py#L223), [src/context_sync/_sync.py:231](../../src/context_sync/_sync.py#L231), [src/context_sync/_sync.py:268](../../src/context_sync/_sync.py#L268), [src/context_sync/__init__.py:6](../../src/context_sync/__init__.py#L6), [docs/design/0-top-level-design.md:11](../design/0-top-level-design.md#L11), [tests/test_sync.py:119](../../tests/test_sync.py#L119) | Any real consumer that follows the documented constructor pattern gets an immediate `AttributeError` on the first `sync()` call instead of a usable snapshot flow. That means M2-3 is effectively test-hook-only despite being recorded as the implementation of the public full-snapshot sync behavior. | Implement and wire the real `Linear`-backed gateway for the public constructor path, or explicitly fail fast with a deliberate repository exception until that wrapper exists. Add a test that exercises `ContextSync(linear=...)` through the public constructor rather than only through `_gateway_override`. |

## Reviewer Notes

- Targeted validation from the repo-local virtualenv passed:
  `.venv/bin/python -m pytest -q tests/test_sync.py tests/test_pipeline.py`
  reported `72 passed in 0.64s`.
- Review-time reproduction for [M2-3-R1](M2-3-review.md#findings):
  a root ticket with one related-but-unloaded target caused
  `await syncer.sync("ROOT-1")` to raise
  `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
  instead of returning a `SyncResult` with an `errors` entry.
- Review-time reproduction for [M2-3-R2](M2-3-review.md#findings):
  constructing `ContextSync(linear=DummyLinear(), ...)` and calling
  `await syncer.sync("ANY-1")` raised
  `AttributeError: 'NoneType' object has no attribute 'fetch_issue'`.
- I did not find a Linear-boundary violation in this ticket.
  [src/context_sync/_sync.py](../../src/context_sync/_sync.py)
  continues to route remote access through the gateway abstraction rather than
  adding direct `linear.gql.*` usage.

## Residual Risks and Testing Gaps

- The current sync integration suite exercises the explicit-root failure case
  (`RootNotFoundError`) and the happy-path relation traversal, but it does not
  cover the contractually important case where a discovered linked ticket
  fails during the later fetch/write phase.
  Supporting context:
  [tests/test_sync.py:388](../../tests/test_sync.py#L388),
  [tests/test_sync.py:400](../../tests/test_sync.py#L400).
- There is still no automated coverage for the documented
  `ContextSync(linear=...)` constructor path. The existing constructor-adjacent
  tests validate the private `_gateway_override` hook instead of the public
  `linear-client` entry point.
  Supporting context:
  [tests/test_sync.py:119](../../tests/test_sync.py#L119),
  [src/context_sync/__init__.py:13](../../src/context_sync/__init__.py#L13).
- I reran targeted ticket-relevant tests only, not the repository's full lint,
  format, and test suite, because this review did not modify implementation
  code.

---

## Second Review Pass

### Scope

Independent strict review of the
[M2-3](../implementation-plan.md#m2-3---full-snapshot-sync-flow)
implementation, performed in a separate session from both Phase A and the
first Phase B pass. Reviewed against the governing design artifacts, ADR,
coding guidelines, and code-review checklist. The first-pass findings
([M2-3-R1](M2-3-review.md#findings), [M2-3-R2](M2-3-review.md#findings))
were read but treated as prior art; this pass focused on finding additional
issues.

### Additional Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M2-3-R3 | Medium | Done | Error Handling | The pre-fetch of existing active roots at [src/context_sync/_sync.py:314-320](../../src/context_sync/_sync.py#L314-L320) uses the same `fetch_tickets()` / `asyncio.TaskGroup` all-or-nothing failure mode identified by [M2-3-R1](M2-3-review.md#findings). If any existing active root is temporarily unavailable during a multi-root sync, the entire run aborts with `ExceptionGroup` even though the explicitly requested root was fetched successfully. The pre-fetch exists to populate Tier 3 URL-scanning content; its failure is not equivalent to a requested-root failure. The design error table ([docs/design/0-top-level-design.md:267](../design/0-top-level-design.md#L267)) makes only the *requested* root's failure terminal; existing-root unavailability during `sync` is not addressed and falls into an unspecified gap between the root-failure and linked-ticket-failure rows. | [src/context_sync/_sync.py:314-320](../../src/context_sync/_sync.py#L314-L320), [src/context_sync/_pipeline.py:190](../../src/context_sync/_pipeline.py#L190), [docs/design/0-top-level-design.md:267](../design/0-top-level-design.md#L267), [docs/adr.md:489](../adr.md#L489) | A user calling `sync("NEW-ROOT")` on a multi-root context directory fails outright because an unrelated, previously healthy root is transiently unreachable. The sync could proceed with reduced cross-root Tier 3 discovery instead of aborting. This is a distinct call site and a distinct impact from [M2-3-R1](M2-3-review.md#findings): the post-traversal fetch concerns non-root linked tickets, while the pre-fetch concerns pre-existing roots whose failure is not contractually terminal. | Guard the pre-fetch of existing roots with per-ticket error handling. If an existing root fails during pre-fetch, exclude it from Tier 3 scanning, drop it from `roots_for_traversal`, log a warning, and proceed. The traversal would still include the requested root and any other healthy roots. If the same fix as [M2-3-R1](M2-3-review.md#findings) is applied (replacing `fetch_tickets` with per-ticket error collection), this call site benefits automatically. Add an integration test where one of two active roots is hidden and assert the sync completes for the healthy root. |
| M2-3-R4 | Medium | Done | Contract Conformance | Sync unconditionally rewrites every reachable ticket file with a fresh `last_synced_at` timestamp even when upstream content is unchanged. The `_utc_now()` call at [src/context_sync/_sync.py:369](../../src/context_sync/_sync.py#L369) ensures the rendered frontmatter always differs from the previous sync pass, and `write_and_verify_ticket` at [src/context_sync/_io.py:113](../../src/context_sync/_io.py#L113) writes unconditionally without comparing content. This violates the ADR §8 operating guarantee: "Re-running sync or refresh without upstream changes should not rewrite files" ([docs/adr.md:522](../adr.md#L522)). The idempotency test at [tests/test_sync.py:313](../../tests/test_sync.py#L313) validates content *stability* (non-timestamp fields match) but does not check whether the file was actually *rewritten* or whether the on-disk content changed. | [src/context_sync/_sync.py:369](../../src/context_sync/_sync.py#L369), [src/context_sync/_io.py:113](../../src/context_sync/_io.py#L113), [docs/adr.md:522](../adr.md#L522), [docs/adr.md:319-325](../adr.md#L319-L325), [tests/test_sync.py:313-348](../../tests/test_sync.py#L313-L348) | For callers who track the context directory in version control, every `sync` invocation produces a git-visible diff for every tracked file (at minimum the `last_synced_at` change), even when nothing changed upstream. This creates unnecessary commit churn and makes it impossible to use VCS diffs to detect real upstream changes. The ADR §5.1 instruction to "rewrite regardless of freshness" refers to skipping freshness *checks*, but the §8 guarantee expects the result to be idempotent when upstream is unchanged. These two requirements are in tension; the implementation followed §5.1 without reconciling §8. | Either (a) compare rendered content to the existing file and skip the write when identical (requires `last_synced_at` to be excluded from the comparison or only updated when upstream content changed), or (b) update `last_synced_at` only when the non-timestamp portion of the file changed. Add an idempotency test that asserts file modification times do not advance when upstream state is unchanged. If the project treats the §8 guarantee as aspirational for sync mode (applying only to refresh/M3-1), document that exception in the ADR and adjust the existing test to verify it. |

### Second-Pass Reviewer Notes

- Targeted validation passed: `.venv/bin/python -m pytest -q tests/test_sync.py
  tests/test_pipeline.py` reported `72 passed in 0.88s`.
- Both first-pass findings ([M2-3-R1](M2-3-review.md#findings) and
  [M2-3-R2](M2-3-review.md#findings)) remain valid and unresolved after
  independent verification. The error-handling code at
  [src/context_sync/_sync.py:371-383](../../src/context_sync/_sync.py#L371-L383)
  is confirmed unreachable dead code: `fetched.get(uid)` can never return
  `None` for a ticket in `graph.tickets` because `fetch_tickets()` either
  succeeds for all tickets or raises `ExceptionGroup`, so the `SyncError`
  construction path never executes. The code creates a false signal to future
  readers that partial-success handling is in place when it is not.
- The sync flow correctly implements the design's full-snapshot rebuild
  sequence: lock acquisition, root fetch, manifest bootstrap, workspace
  validation before mutation, all-root traversal, full rewrite of reachable
  tickets, derived-ticket pruning, manifest finalization, and lock release in
  the `finally` block.
- Lock lifecycle is sound: `acquire_lock` precedes all mutation;
  `release_lock` runs in a `finally` block that covers both success and
  failure paths. Tests at
  [tests/test_sync.py:504-524](../../tests/test_sync.py#L504-L524) confirm
  the lock file is absent after both successful and failed syncs.
- Workspace validation fires before any manifest or filesystem mutation,
  matching the design contract. The test at
  [tests/test_sync.py:354-386](../../tests/test_sync.py#L354-L386) confirms
  the guard works across two separate workspaces.
- Pruning correctly protects root tickets (the `uid not in manifest.roots`
  guard at [src/context_sync/_sync.py:405](../../src/context_sync/_sync.py#L405)),
  removes only unreachable derived tickets, and cleans up both the file and the
  manifest entry. Test coverage at
  [tests/test_sync.py:400-458](../../tests/test_sync.py#L400-L458) covers
  relation removal and root protection.
- No Linear-boundary violation found. All remote access routes through the
  gateway abstraction: `gateway.fetch_issue`, `gateway.get_ticket_relations`
  (via `build_reachable_graph`), and `gateway.fetch_issue` again (via
  `make_ticket_ref_provider`). No direct `linear.gql.*` calls.
- No concurrency defects found in the async code. The shared `fetched` dict is
  mutated only by coroutines that execute sequentially within a single event
  loop turn or under `await` boundaries. The `asyncio.Semaphore` correctly
  limits concurrent gateway calls.
- Module decomposition is clean: `sync` orchestrates; `_pipeline` owns fetch,
  render, and write; `_traversal` owns graph construction; `_manifest` owns
  persistence. No responsibility leaks across module boundaries.
- Coding guidelines compliance: docstrings present on all public and private
  methods, type annotations complete, no magic numbers, no hardcoded secrets,
  logging at INFO and DEBUG levels matches the ADR §6 observability contract.

### Additional Testing Gaps

- No test covers multi-root sync failure when an existing root is hidden or
  unavailable during the pre-fetch step
  ([src/context_sync/_sync.py:314-320](../../src/context_sync/_sync.py#L314-L320)).
  The `FakeLinearGateway.hide_issue()` method exists but is not exercised in
  sync-flow tests.
- No test asserts that `SyncResult.unchanged` is empty for sync mode
  (minor — implied by the default factory, but an explicit assertion would
  document the sync-mode contract).
- The idempotency test
  ([tests/test_sync.py:313-348](../../tests/test_sync.py#L313-L348)) validates
  content stability but not write avoidance: it does not check whether the file
  was actually rewritten on disk (e.g., by comparing file modification times).

---

## Ticket Owner Response (Phase C)

### Verdict Table

| ID | Verdict | Rationale |
| --- | --- | --- |
| M2-3-R1 | Fix now | Replaced post-traversal `fetch_tickets()` with per-ticket concurrent fetches using `asyncio.TaskGroup`. Each task catches `RootNotFoundError` and records it as a `SyncError` entry. The previously dead error-handling code in the write loop is removed; the write loop now silently skips tickets not in `fetched` since errors are recorded during fetch. Non-`RootNotFoundError` exceptions still propagate for systemic failures. Added integration test `test_linked_ticket_unavailable_records_error` using `hide_issue()`. |
| M2-3-R2 | Fix now | Added a fail-fast check at the top of `sync()`: if `self._gateway is None`, raises `ContextSyncError` with a message directing callers to use `_gateway_override`. This surfaces the missing gateway wrapper immediately rather than at `fetch_issue()` time. Added test `test_linear_constructor_raises_on_sync` exercising `ContextSync(linear=object())`. |
| M2-3-R3 | Fix now | Replaced pre-fetch `fetch_tickets()` for existing roots with per-ticket concurrent fetches. Each task catches `RootNotFoundError`, adds the failed UUID to `prefetch_failed`, and logs a warning. Failed roots are excluded from `roots_for_traversal` so they do not participate in traversal or trigger spurious post-traversal fetch attempts. Added integration test `test_hidden_existing_root_excluded_from_traversal` using `hide_issue()`. |
| M2-3-R4 | Fix now | Added write-avoidance by comparing `compute_refresh_cursor(bundle)` and `root_state` against the existing file's frontmatter (via `_read_existing_ticket_state` helper). When both match and the issue key is unchanged, the ticket is classified as `unchanged` and the write is skipped. Updated three existing tests (`test_second_sync_reports_unchanged_when_no_upstream_change`, `test_root_tickets_never_pruned`, `test_add_second_root_expands_snapshot`) to assert `unchanged` instead of `updated`. Added `test_file_mtime_stable_when_unchanged` (mtime check) and `test_upstream_change_triggers_rewrite` (cursor change triggers write). Updated the module docstring to reflect the ADR §8 reconciliation. |

### Changes Made

- [src/context_sync/_sync.py](../../src/context_sync/_sync.py):
  - Added imports: `RootNotFoundError`, `ManifestTicketEntry`,
    `compute_refresh_cursor`, `parse_frontmatter`. Removed `fetch_tickets`.
  - Added `_read_existing_ticket_state()` helper for R4 cursor comparison.
  - Added gateway readiness check at top of `sync()` (R2).
  - Replaced pre-fetch `fetch_tickets()` with per-ticket error-handling
    `_fetch_existing_root()` coroutines under `asyncio.TaskGroup` (R3).
  - Added `prefetch_failed` set; excluded failed roots from
    `roots_for_traversal` (R3).
  - Replaced post-traversal `fetch_tickets()` with per-ticket error-handling
    `_fetch_linked()` coroutines under `asyncio.TaskGroup` (R1).
  - Added cursor/root_state comparison in write loop to skip unchanged
    tickets (R4). Added `unchanged` list to `SyncResult` construction.
  - Removed dead-code error handling from write loop (R1).
  - Updated module docstring to reflect ADR §8 idempotency guarantee.
- [tests/test_sync.py](../../tests/test_sync.py):
  - Updated `test_second_sync_reports_unchanged_when_no_upstream_change`
    (renamed; asserts `unchanged` instead of `updated`).
  - Updated `test_root_tickets_never_pruned` (asserts `unchanged`).
  - Updated `test_add_second_root_expands_snapshot` (R-1 now `unchanged`).
  - Added `TestSyncLinkedTicketFetchFailure` (R1 regression test).
  - Added `TestSyncGatewayReadiness` (R2 regression test).
  - Added `TestSyncExistingRootPrefetchFailure` (R3 regression test).
  - Added `TestSyncWriteAvoidance` with mtime and upstream-change tests (R4).

### Validation

- `ruff check` — clean
- `ruff format --check` — clean
- `pytest -q` — 331 tests pass (326 → 331; 5 new)
