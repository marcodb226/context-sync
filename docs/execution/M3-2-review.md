# Review: [M3-2](../implementation-plan.md#m3-2---add-and-remove-root-whole-snapshot-flows)

> **Status**: Phase B complete
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
