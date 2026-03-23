# Review: [M2-1](../implementation-plan.md#m2-1---reachable-graph-builder-and-tiered-per-root-traversal)

> **Status**: Phase C complete
> **Plan ticket**:
> [M2-1](../implementation-plan.md#m2-1---reachable-graph-builder-and-tiered-per-root-traversal)
> **Execution record**:
> [docs/execution/M2-1.md](M2-1.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/python/coding-guidelines.md](../policies/common/python/coding-guidelines.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/adr.md](../adr.md#13-traversal-order-and-ticket-cap),
> [docs/adr.md](../adr.md#14-root-vs-derived-tickets),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#61-sync-flow),
> [docs/design/linear-domain-coverage-audit.md](../design/linear-domain-coverage-audit.md)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M2-1-R1 | Medium | Todo | Determinism | Same-tier candidate ordering is not normalized before cap decisions. The traversal iterates `relation_map` and `ticket_ref_fn` outputs in whatever order the adapter/provider returns them, but the ADR explicitly requires same-tier breadth-first processing with deterministic relation ordering. Under a tight per-root cap, reversing two same-tier edges changes which ticket survives. | [src/context_sync/_traversal.py:228](../../src/context_sync/_traversal.py#L228), [src/context_sync/_traversal.py:256](../../src/context_sync/_traversal.py#L256), [docs/adr.md:85](../adr.md#L85), [docs/design/0-top-level-design.md:333](../design/0-top-level-design.md#L333), [tests/test_traversal.py:192](../../tests/test_traversal.py#L192) | Cap-bound snapshots can vary with upstream list order instead of repository-defined ordering. That makes the reachable set nondeterministic near the safety bound and can arbitrarily prefer one same-tier dependency over another. | Sort same-tier relation edges and `ticket_ref` targets deterministically per frontier ticket before applying cap logic, and add tests that reverse same-tier input order while asserting identical reachable sets. |
| M2-1-R2 | Medium | Todo | Cap Enforcement | The traversal does not stop when a root's budget becomes exactly full; it stops only when a later candidate cannot be added. `cap_remaining` can reach `0` after a successful add, but `at_cap` remains `False`, so the next frontier is still expanded and can trigger more `get_ticket_relations()` or `ticket_ref_fn` calls even though no further tickets can ever be admitted. The ADR says a root stops expanding when its cap is reached. | [src/context_sync/_traversal.py:194](../../src/context_sync/_traversal.py#L194), [src/context_sync/_traversal.py:197](../../src/context_sync/_traversal.py#L197), [src/context_sync/_traversal.py:233](../../src/context_sync/_traversal.py#L233), [src/context_sync/_traversal.py:262](../../src/context_sync/_traversal.py#L262), [docs/adr.md:87](../adr.md#L87), [docs/design/0-top-level-design.md:339](../design/0-top-level-design.md#L339), [tests/test_traversal.py:118](../../tests/test_traversal.py#L118) | The reachable-ticket set may still be correct, but the engine performs unnecessary remote work after the per-root budget is already exhausted. That wastes rate-limited adapter calls and can force expensive Tier 3 scanning on tickets that cannot possibly be added. | Stop traversal for that root as soon as `cap_remaining` reaches `0` after an accepted add, and add a logging-fake test that proves no next-depth relation read or `ticket_ref_fn` call occurs once the budget is full. |
| M2-1-R3 | Low | Todo | API Contract | `build_reachable_graph()` is exported from the package root as a public helper, but it does not validate its own config boundary. The wider library API rejects non-positive `max_tickets_per_root`, and the common coding policy requires validation at system boundaries, yet this exported function accepts raw `dimensions` and `max_tickets_per_root` and feeds them directly into internal logic. A zero cap, for example, still returns the root ticket and reports no cap hit. | [src/context_sync/__init__.py:86](../../src/context_sync/__init__.py#L86), [src/context_sync/_traversal.py:296](../../src/context_sync/_traversal.py#L296), [src/context_sync/_traversal.py:194](../../src/context_sync/_traversal.py#L194), [src/context_sync/_sync.py:94](../../src/context_sync/_sync.py#L94), [docs/policies/common/coding-guidelines.md:54](../policies/common/coding-guidelines.md#L54), [tests/test_package.py:170](../../tests/test_package.py#L170) | Direct callers of the exported traversal helper can get silent nonsense instead of fail-loud validation errors. That weakens the public API contract and makes the helper behave less safely than the main `ContextSync` surface. | Validate `max_tickets_per_root >= 1` and normalize or validate `dimensions` inside `build_reachable_graph()`, or stop exporting the helper if it is intentionally internal-only. Add invalid-input tests either way. |

## Reviewer Notes

- Validation is reproducible from the repo-local virtualenv:
  `.venv/bin/ruff check src tests` passed,
  `.venv/bin/ruff format --check src tests` passed,
  and `.venv/bin/pytest -v` passed all 268 tests during review.
- Review-time probes confirmed both runtime findings above:
  reversing two same-tier `blocks` relations changes which derived ticket
  survives under `max_tickets_per_root=2`, and a root that exactly fills its
  cap still triggers a second `get_ticket_relations()` call on the next
  frontier before the traversal stops.
- I did not find evidence of a Linear-boundary violation in this ticket.
  [src/context_sync/_traversal.py](../../src/context_sync/_traversal.py)
  stays within the approved adapter surface by using only
  `gateway.get_ticket_relations()` plus the caller-provided `ticket_ref_fn`.

## Residual Risks and Testing Gaps

- The current tests are strong on cross-tier priority but weak on same-tier
  determinism. There is no test that reverses relation order within one tier
  and asserts a stable reachable set under a tight cap.
- There is also no test that asserts post-cap non-expansion. The existing
  cap tests check the final reachable set and `roots_at_cap`, but they do not
  verify that no extra adapter calls are made after the budget is exhausted.
- This review used repository artifacts, local code inspection, validation
  commands, and small review-time probes against the in-repo fake gateway. No
  live Linear calls were needed or attempted.

---

## Second Review Pass

> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/data-modeling.md](../policies/common/data-modeling.md),
> [docs/adr.md](../adr.md#13-traversal-order-and-ticket-cap)

### Additional Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M2-1-R4 | Low | Todo | API Contract | `TraversalResult` is a frozen dataclass, but its `per_root_tickets` and `tickets` fields are plain mutable dicts. Python's `frozen=True` prevents rebinding the attribute (`result.per_root_tickets = x` raises `FrozenInstanceError`) but does not prevent in-place mutation of the dict value (`result.per_root_tickets["injected"] = frozenset()` silently succeeds). The execution record claims "Frozen dataclasses for both result types per the data-modeling policy" as evidence of immutability, and `TraversalResult` is a public export, so external callers may reasonably assume the object is fully immutable. | [src/context_sync/_traversal.py:85-107](../../src/context_sync/_traversal.py#L85), [src/context_sync/_traversal.py:105-106](../../src/context_sync/_traversal.py#L105), [src/context_sync/__init__.py:87-91](../../src/context_sync/__init__.py#L87), [docs/execution/M2-1.md:113-114](M2-1.md#L113) | Callers treating the result as fully immutable (e.g. as a cache key basis or shared across coroutines) could observe unexpected mutation. The false immutability guarantee also makes the public contract harder to rely on correctly as downstream tickets build on this type. | Replace the mutable dict fields with `types.MappingProxyType` wrappers, or document explicitly in the class docstring that the outer dict values should not be mutated by callers, and add a test that confirms in-place mutation of `per_root_tickets` raises an error (or at minimum documents the current behavior). |
| M2-1-R5 | Low | Todo | Code Quality | `tier12_active` is computed (lines 204–210) by inlining the depth-check predicate `dimensions.get(d, 0) > current_depth` rather than calling the already-extracted `_active_dims_for_tier` helper. The execution record lists DRY compliance as a checked item. The inside-loop uses of `_active_dims_for_tier` are consistent, but the gate computation at the top of the depth loop is not. | [src/context_sync/_traversal.py:204-210](../../src/context_sync/_traversal.py#L204), [src/context_sync/_traversal.py:115-140](../../src/context_sync/_traversal.py#L115), [docs/execution/M2-1.md:121-122](M2-1.md#L121) | Minor inconsistency: the depth-check logic lives in two places. A future change to the depth-boundary rule (e.g. `>=` instead of `>`) would need to be made in both locations or the gate and the per-tier filter would diverge silently. | Replace the inline comprehension with calls to `_active_dims_for_tier` over the non-Tier-3 tiers, e.g. `frozenset().union(_active_dims_for_tier(t, dimensions, current_depth) for t in TRAVERSAL_TIERS if Dimension.TICKET_REF not in t)`. |
| M2-1-R6 | Low | Todo | Testing | `test_ticket_ref_depth_boundary` includes a `for call in call_log` loop whose assertion `assert "d1" not in call or "e1" not in result.tickets` is vacuously true whenever the implementation is correct (the second disjunct always holds because `"e1"` is never admitted). The assertion does not verify that `ticket_ref_fn` is only called at depth 0 and is skipped at depth 1; the meaningful check is the standalone `assert "e1" not in result.tickets` on the next line. A regression that calls `ticket_ref_fn` at depth 1 but somehow still excludes `"e1"` from results would not be caught by the loop. | [tests/test_traversal.py:644-648](../../tests/test_traversal.py#L644) | The test gives false confidence that call-depth isolation is verified. The real depth-boundary enforcement for Tier 3 is tested only indirectly through the end-state assertion, leaving open the possibility that a future bug calls `ticket_ref_fn` unnecessarily without failing any assertion. | Replace the loop assertion with explicit call-count and call-argument checks: `assert len(call_log) == 1` and `assert call_log[0] == ["r1"]`, which directly verify that `ticket_ref_fn` was called exactly once (at depth 0 with only the root) and was not called again at depth 1. |

### Reviewer Notes

- Validation was performed from the repo-local virtualenv:
  `.venv/bin/ruff check src tests` passed,
  `.venv/bin/ruff format --check src tests` passed,
  and `.venv/bin/pytest -v` confirmed all 268 tests pass.
- All seven "Reviewer Handoff" items from the Phase A execution record were
  verified by code inspection and confirmed correct: per-root set independence,
  tier ordering, minimum-depth resolution, cycle safety, `roots_at_cap`
  semantics, `ticket_ref_fn=None` skipping, and the adapter boundary.
- [M2-1-R1](M2-1-review.md#additional-findings) and
  [M2-1-R2](M2-1-review.md#additional-findings) from the first pass were
  independently confirmed: relation ordering is not sorted within a tier
  before the cap decision, and the `cap_remaining == 0` early-exit gap is
  present. No new medium or high severity findings beyond those already
  recorded.
- [M2-1-R4](M2-1-review.md#additional-findings) is a contract-clarity issue
  rather than a runtime bug: no existing code mutates the returned dicts, but
  the public type does not enforce what the frozen-dataclass framing implies.

### Residual Risks and Testing Gaps (Second Pass)

- The `test_ticket_ref_depth_boundary` call-log assertion (covered by
  [M2-1-R6](M2-1-review.md#additional-findings)) leaves the depth-isolation
  property for Tier 3 verified only indirectly. If the depth-boundary check
  for `ticket_ref_fn` were removed or broken, no test would catch the
  unnecessary extra call.
- The DRY gap identified in
  [M2-1-R5](M2-1-review.md#additional-findings) is isolated to the
  `tier12_active` gate and does not affect correctness today, but is a
  maintenance risk if the depth-boundary predicate changes.
- No Linear-boundary violations were found. The module correctly limits all
  Linear-side reads to `gateway.get_ticket_relations()` and leaves Tier 3
  discovery entirely to the caller-supplied `ticket_ref_fn`.

---

## Ticket Owner Response

> **Status**: Phase C complete

| ID | Verdict | Disposition | Notes |
| --- | --- | --- | --- |
| M2-1-R1 | Fix now | Accepted | Sort same-tier relation edges by `target_issue_id` and Tier 3 targets by `(target_id, target_key)` before cap decisions. Add same-tier ordering stability test that reverses relation order and asserts identical reachable sets. |
| M2-1-R2 | Fix now | Accepted | Break the outer BFS loop when `cap_remaining == 0` after the tier pass — no further gateway calls are possible. Add a call-tracking test that confirms no `get_ticket_relations` call occurs after the budget is exactly exhausted. |
| M2-1-R3 | Fix now | Accepted | Add `ValueError` guard at the start of `build_reachable_graph` for `max_tickets_per_root < 1`. Add invalid-input test. |
| M2-1-R4 | Fix now (docstring) | Accepted with narrowed scope | The existing `SyncResult` pattern uses plain lists similarly without MappingProxyType; wrapping would diverge from that convention. Instead, add a `Notes` section to the `TraversalResult` docstring explicitly warning callers that the dict fields must not be mutated in place. |
| M2-1-R5 | Fix now | Accepted | Replace the inline `tier12_active` comprehension with a call to `_active_dims_for_tier` so the depth-boundary predicate lives in one place. |
| M2-1-R6 | Fix now | Accepted | Replace the vacuous loop assertion with `assert len(call_log) == 1` and `assert call_log[0] == ["r1"]`, which directly verify call isolation. |
