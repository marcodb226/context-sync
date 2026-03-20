# Review: [M2-1](../implementation-plan.md#m2-1---reachable-graph-builder-and-tiered-per-root-traversal)

> **Status**: Phase B complete
> **Plan ticket**:
> [M2-1](../implementation-plan.md#m2-1---reachable-graph-builder-and-tiered-per-root-traversal)
> **Execution record**:
> [docs/execution/M2-1.md](M2-1.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/coding-guidelines-python.md](../policies/common/coding-guidelines-python.md),
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
