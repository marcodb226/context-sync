# Review: [M2-3](../implementation-plan.md#m2-3---full-snapshot-sync-flow)

> **Status**: Phase B complete
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
| M2-3-R1 | High | Todo | Error Handling | `sync()` cannot honor the documented "partial success with `SyncResult.errors`" contract for linked-ticket fetch failures. The post-traversal fetch step delegates to `fetch_tickets()`, and that helper propagates any single `fetch_issue()` exception as an `ExceptionGroup`, so the run aborts before the later `errors.append(...)` path can execute. The design and ADR both say an isolated linked-ticket failure should be recorded in the result while successful tickets still write. | [src/context_sync/_pipeline.py:154](../../src/context_sync/_pipeline.py#L154), [src/context_sync/_pipeline.py:190](../../src/context_sync/_pipeline.py#L190), [src/context_sync/_sync.py:355](../../src/context_sync/_sync.py#L355), [src/context_sync/_sync.py:371](../../src/context_sync/_sync.py#L371), [docs/design/0-top-level-design.md:263](../design/0-top-level-design.md#L263), [docs/adr.md:500](../adr.md#L500), [docs/execution/M2-3.md:41](M2-3.md#L41), [tests/test_pipeline.py:188](../../tests/test_pipeline.py#L188) | A single unreachable non-root ticket can abort the entire sync pass and prevent otherwise healthy tickets from being refreshed or written. That turns a ticket-scoped failure into a full-run failure and breaks the caller-facing `SyncResult` contract the ticket says it implemented. | Split reachable-ticket fetch outcomes into ticket-scoped failures versus systemic failures. Keep aborting on systemic gateway errors, but collect not-found/not-visible linked-ticket failures into `SyncError` rows and continue writing the successfully fetched tickets. Add an integration test where traversal discovers a related ticket whose later `fetch_issue()` fails and assert the run completes with one `errors` entry. |
| M2-3-R2 | High | Todo | Public API | The public library surface is still broken for real callers. The package docs and top-level design both say `ContextSync` accepts an authenticated `linear-client` `Linear` instance, but the constructor still stores that object without creating a gateway and leaves `self._gateway = None`. `sync()` then passes that `None` straight into `_sync_under_lock()`, which immediately calls `gateway.fetch_issue(...)`. In practice, the new sync flow only works through the private `_gateway_override` testing hook. | [src/context_sync/_sync.py:119](../../src/context_sync/_sync.py#L119), [src/context_sync/_sync.py:223](../../src/context_sync/_sync.py#L223), [src/context_sync/_sync.py:231](../../src/context_sync/_sync.py#L231), [src/context_sync/_sync.py:268](../../src/context_sync/_sync.py#L268), [src/context_sync/__init__.py:6](../../src/context_sync/__init__.py#L6), [docs/design/0-top-level-design.md:11](../design/0-top-level-design.md#L11), [tests/test_sync.py:119](../../tests/test_sync.py#L119) | Any real consumer that follows the documented constructor pattern gets an immediate `AttributeError` on the first `sync()` call instead of a usable snapshot flow. That means M2-3 is effectively test-hook-only despite being recorded as the implementation of the public full-snapshot sync behavior. | Implement and wire the real `Linear`-backed gateway for the public constructor path, or explicitly fail fast with a deliberate repository exception until that wrapper exists. Add a test that exercises `ContextSync(linear=...)` through the public constructor rather than only through `_gateway_override`. |

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
