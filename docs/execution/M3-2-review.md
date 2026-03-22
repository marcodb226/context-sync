# Review: [M3-2](../implementation-plan.md#m3-2---add-and-remove-root-whole-snapshot-flows)

> **Status**: Phase B complete (2 review passes)
> **Plan ticket**:
> [M3-2](../implementation-plan.md#m3-2---add-and-remove-root-whole-snapshot-flows)
> **Execution record**:
> [docs/execution/M3-2.md](M3-2.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/coding-guidelines-python.md](../policies/common/coding-guidelines-python.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/adr.md](../adr.md#21-context-manifest-and-non-ticket-files),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#21-context-directory-contents),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#63-add-flow),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#65-remove-root-flow)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M3-2-R1 | Medium | Todo | Alias Resolution | `_resolve_ref_to_uuid()` gives `manifest.aliases` precedence over currently tracked `current_key` values. That means the new `add`/`remove_root` flows can resolve a human-facing key to a historical alias target before checking whether another tracked ticket currently owns that key. The rest of the repository does not use that precedence: the Tier 3 URL resolver seeds current keys first and only falls back to aliases when no current key matches. | [src/context_sync/_sync.py:119](../../src/context_sync/_sync.py#L119), [src/context_sync/_sync.py:131](../../src/context_sync/_sync.py#L131), [src/context_sync/_pipeline.py:393](../../src/context_sync/_pipeline.py#L393), [docs/design/0-top-level-design.md:157](../design/0-top-level-design.md#L157), [docs/design/0-top-level-design.md:160](../design/0-top-level-design.md#L160), [docs/design/0-top-level-design.md:166](../design/0-top-level-design.md#L166), [docs/adr.md:186](../adr.md#L186), [docs/adr.md:205](../adr.md#L205) | In the key-reassignment scenario the ADR explicitly models, `add("OLD-1")` or `remove_root("OLD-1")` can silently mutate the wrong UUID. A historical alias can win over a currently tracked ticket with the same visible key, so the root set changes for the wrong ticket and the subsequent whole-snapshot refresh can add or prune the wrong subtree. | Resolve tracked `current_key` values before historical aliases, or detect alias/current-key collisions and raise an explicit ambiguity error instead of guessing. Add regression coverage for both the normal historical-alias case and the collision case so the root-mutation resolver stays aligned with the manifest contract. |
| M3-2-R2 | High | Todo | Failure Safety | `add()` and `remove_root()` persist the root-set mutation to `.context-sync.yml` before entering `_refresh_under_lock()`, but `_refresh_under_lock()` only writes snapshot metadata when the whole refresh finishes successfully. If the shared refresh pipeline then raises, the authoritative manifest keeps the new/removed root while `snapshot` still points to the previous completed pass and ticket files can still reflect the old root state. | [src/context_sync/_sync.py:797](../../src/context_sync/_sync.py#L797), [src/context_sync/_sync.py:1157](../../src/context_sync/_sync.py#L1157), [src/context_sync/_sync.py:1321](../../src/context_sync/_sync.py#L1321), [src/context_sync/_sync.py:1325](../../src/context_sync/_sync.py#L1325), [src/context_sync/_sync.py:1455](../../src/context_sync/_sync.py#L1455), [src/context_sync/_sync.py:1459](../../src/context_sync/_sync.py#L1459), [docs/design/0-top-level-design.md:155](../design/0-top-level-design.md#L155), [docs/design/0-top-level-design.md:158](../design/0-top-level-design.md#L158), [docs/design/0-top-level-design.md:164](../design/0-top-level-design.md#L164), [docs/adr.md:194](../adr.md#L194), [docs/adr.md:201](../adr.md#L201), [docs/adr.md:205](../adr.md#L205) | A failed root-mutation call can still partially commit on ordinary exceptions such as `WriteError` or a systemic gateway failure. In review-time reproduction, forcing `_refresh_under_lock()` to raise after the pre-save left failed `add("ROOT-2")` with both roots persisted in the manifest but `snapshot.mode == "sync"`, and failed `remove_root("ROOT-2")` with `ROOT-2.md` still on disk while the manifest no longer listed it as a root. Because the manifest is authoritative for roots, a later refresh will treat those root-set changes as real even though the original operation failed. | Do not save the mutated manifest before the shared refresh succeeds. Thread the in-memory manifest into `_refresh_under_lock()` (or add a mutation callback) so the root change and snapshot finalization are committed together. If early persistence is unavoidable, write an explicit in-progress/failed snapshot record before risky work and roll back the root mutation on exception. Add regression tests that force `_refresh_under_lock()` to raise after the root-set mutation and assert the manifest is either rolled back or explicitly marked failed. |

## Reviewer Notes

- Review scope was the `M3-2` implementation commit `9242e1b` plus the
  repository artifacts it touched. The later commit on `main` modifies only
  [docs/future-work.md](../future-work.md) and does not affect this ticket's
  code paths.
- Review-time reproduction for [M3-2-R1](M3-2-review.md#findings):
  with a synthetic manifest containing `aliases={"OLD-1": "uuid-old"}` and a
  separate tracked ticket whose `current_key` is also `OLD-1`,
  `_resolve_ref_to_uuid("OLD-1", manifest)` returned `uuid-old` instead of the
  currently tracked ticket UUID.
- Review-time reproduction for [M3-2-R2](M3-2-review.md#findings):
  monkeypatching `_refresh_under_lock()` to raise immediately after the new
  pre-refresh `save_manifest()` call left failed `add("ROOT-2")` with
  `roots=['uuid-root1', 'uuid-root2']` and `snapshot.mode == "sync"`, and left
  failed `remove_root("ROOT-2")` with `ROOT-2.md` still present while the
  manifest root set had already dropped `uuid-root2`.
- I did not find a Linear-boundary violation in this ticket.
  [src/context_sync/_sync.py](../../src/context_sync/_sync.py)
  continues to route remote reads through the gateway abstraction.
- I did not rerun the repository lint/format/test commands during this review.
  The current worktree diff is docs-only, and this repository's validation
  gate says not to run the repo validation commands for docs-only work unless
  the user explicitly asks.

## Residual Risks and Testing Gaps

- [tests/test_add_remove_root.py](../../tests/test_add_remove_root.py)
  covers current issue keys, Linear URLs, and overlap cases, but it does not
  exercise historical-alias inputs after a rename or the alias/current-key
  collision case behind [M3-2-R1](M3-2-review.md#findings).
- No test forces the shared refresh phase to fail after the new pre-refresh
  `save_manifest()` call in `add()` or `remove_root()`, so the partial-commit
  behavior behind [M3-2-R2](M3-2-review.md#findings) is currently unguarded.

---

## Review Pass 2

> **Reviewer**: Independent second-pass review
> **Scope**: Implementation commit `9242e1b`, the same artifacts as review
> pass 1. This pass confirms the pass-1 findings and adds four new findings.

### Review Pass 2 — Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M3-2-R3 | Medium | Todo | API / Resolution | `remove_root` documents `ticket_ref` as accepting "Issue key, Linear issue URL, or ticket UUID" ([src/context_sync/_sync.py:1354](../../src/context_sync/_sync.py#L1354)). However, `_resolve_ref_to_uuid` step 3 only checks `manifest.roots` for direct UUID matches — it never checks `manifest.tickets`. When a caller passes the raw UUID of a derived (non-root) ticket, all three resolution steps miss and the function returns `None`. This triggers the generic "Cannot resolve" error instead of the more specific "tracked but is not in the root set" error that the two-stage check was designed to produce. | [src/context_sync/_sync.py:119–141](../../src/context_sync/_sync.py#L119) (resolution function), [src/context_sync/_sync.py:138–140](../../src/context_sync/_sync.py#L138) (step 3 only checks `manifest.roots`), [src/context_sync/_sync.py:1354](../../src/context_sync/_sync.py#L1354) (docstring claims UUID input), [src/context_sync/_sync.py:1443–1446](../../src/context_sync/_sync.py#L1443) (generic error path hit instead of specific path at [line 1449](../../src/context_sync/_sync.py#L1449)) | `remove_root(uuid_of_derived_ticket)` reports "Cannot resolve … to a ticket in the manifest" even though the ticket IS in the manifest. The user gets a confusing diagnostic instead of the intended "tracked but is not in the root set" message. The documented API contract (UUID as accepted input) is not met for derived-ticket UUIDs. | Add a step between steps 2 and 3 (or replace step 3) that checks `manifest.tickets` for a direct UUID match, so derived-ticket UUIDs resolve correctly and reach the root-membership check with the more specific error. Add a test that calls `remove_root` with a raw derived-ticket UUID and asserts `RootNotInManifestError` with the "not in the root set" message. |
| M3-2-R4 | Low | Todo | Operational | The zero-roots early-return path in `_refresh_under_lock` (lines 809–832) prunes all remaining tracked tickets, but the path returns before reaching the INFO-level summary log at [line 1168](../../src/context_sync/_sync.py#L1168). Individual prunes are logged at DEBUG only. There is no INFO-level summary for the zero-roots case. | [src/context_sync/_sync.py:809–832](../../src/context_sync/_sync.py#L809) (zero-roots path with only DEBUG logs), [src/context_sync/_sync.py:1168](../../src/context_sync/_sync.py#L1168) (INFO summary only reached by the normal completion path), [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md) ("Emit meaningful operational events at INFO level") | An operator monitoring INFO logs would see no record of a `remove_root` that pruned all tickets via the zero-roots path. This makes post-incident diagnosis harder for the most destructive variant of `remove_root` (removing the last root). | Add an INFO-level log line before the early return in the zero-roots branch, summarizing the prune count and snapshot mode, consistent with the normal completion path's format. |
| M3-2-R5 | Low | Todo | Maintainability | [src/context_sync/_sync.py](../../src/context_sync/_sync.py) is now 888 code lines (per `cloc`). The coding guidelines require proactive extraction when a file grows past ~750 lines ([docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md)). M3-2 added ~255 code lines. The three new module-level helpers (`_parse_linear_url`, `_normalize_ticket_ref`, `_resolve_ref_to_uuid`) are stateless, have no dependency on `ContextSync` instance state, and form a cohesive "ticket-ref resolution" group that could live in a sibling module. The execution record does not note consideration of file-size extraction. | [src/context_sync/_sync.py](../../src/context_sync/_sync.py) (888 code lines via `cloc`), [src/context_sync/_sync.py:86–141](../../src/context_sync/_sync.py#L86) (three stateless helpers), [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md) (750-line proactive extraction threshold, 1000-line hard limit) | The file is 112 code lines from the hard limit. One more ticket of similar scope (M3-3 `diff`) will likely breach 1000 lines. Extracting now is cheaper than extracting under the hard-limit deadline. | Extract `_parse_linear_url`, `_normalize_ticket_ref`, `_resolve_ref_to_uuid`, and `_LINEAR_URL_RE` into a dedicated `_ticket_ref.py` module. This reduces `_sync.py` by ~60 code lines and creates a natural test seam for the resolution logic. |
| M3-2-R6 | Low | Todo | Testing | No test exercises `add` on an already-quarantined root. The implementation unconditionally sets `state="active"` at [line 1322](../../src/context_sync/_sync.py#L1322), silently overriding a quarantine without logging the state transition. The test suite covers idempotent re-add of an active root (`test_add_already_active_root_is_idempotent`) but not the quarantined→active transition. | [src/context_sync/_sync.py:1322](../../src/context_sync/_sync.py#L1322) (`manifest.roots[root_uuid] = ManifestRootEntry(state="active")` — no quarantine check), [tests/test_add_remove_root.py](../../tests/test_add_remove_root.py) (no quarantined-root test case) | The quarantine→active override via `add` is an implicit recovery path that bypasses the explicit quarantine/recovery logic in `refresh` (M3-1). If this behavior is intentional it should be documented and tested; if not, it is a silent correctness gap. | Add a test that syncs a root, quarantines it (by simulating an unavailable root through a subsequent refresh), then calls `add` with the same key and verifies: (a) the root returns to `active` state, (b) the ticket file is refreshed, and (c) the behavior is logged at INFO. If quarantine override is unintentional, add a guard that raises or warns instead. |

### Review Pass 2 — Reviewer Notes

- I independently confirm the findings from review pass 1.
  [M3-2-R1](M3-2-review.md#findings) (alias precedence inversion) and
  [M3-2-R2](M3-2-review.md#findings) (pre-refresh partial commit) are both
  real, reproducible, and correctly characterized. I traced the same code paths
  and agree with the severity assessments.
- For [M3-2-R3](M3-2-review.md#review-pass-2--findings): the resolution
  function's step 3 only checks `manifest.roots` for UUID matches
  ([src/context_sync/_sync.py:138–140](../../src/context_sync/_sync.py#L138)).
  A `manifest.tickets` UUID lookup is absent. Tracing
  `remove_root("uuid-child")` where `uuid-child` is tracked as a derived
  ticket: steps 1–2 miss (aliases and `current_key` don't match UUIDs), step 3
  misses (`uuid-child ∉ manifest.roots`), so `None` is returned and the
  generic "Cannot resolve" error fires rather than the targeted "not in the
  root set" error at [line 1449](../../src/context_sync/_sync.py#L1449).
- For [M3-2-R4](M3-2-review.md#review-pass-2--findings): the zero-roots
  early return at [line 832](../../src/context_sync/_sync.py#L832) bypasses
  the INFO log at [line 1168](../../src/context_sync/_sync.py#L1168). The
  `test_remove_sole_root_prunes_everything` test confirms the prune behavior
  works, but log output is not verified.
- For [M3-2-R5](M3-2-review.md#review-pass-2--findings): `cloc` reports 888
  code lines. The three new helpers at
  [lines 86–141](../../src/context_sync/_sync.py#L86) are pure functions with
  no `self` or class-level dependency — they are the strongest extraction
  candidate.
- I did not find a Linear-domain-boundary violation. All remote reads continue
  to route through the gateway abstraction.
- I did not rerun lint/format/test commands. The current worktree diff is
  docs-only per the validation scope gate.

### Review Pass 2 — Residual Risks and Testing Gaps

- All residual risks from pass 1 remain open.
- [tests/test_add_remove_root.py](../../tests/test_add_remove_root.py) does
  not test `remove_root` with a raw UUID input (neither root UUID nor derived
  UUID). The documented API contract for UUID inputs is untested
  ([M3-2-R3](M3-2-review.md#review-pass-2--findings)).
- No test verifies that `add` on a quarantined root transitions the root to
  `active` state ([M3-2-R6](M3-2-review.md#review-pass-2--findings)).
- The zero-roots prune path is the most destructive single code path in
  `remove_root` (deletes all ticket files), yet it has no INFO-level
  operational log ([M3-2-R4](M3-2-review.md#review-pass-2--findings)).
