# Review: [M4-R2](../implementation-plan.md#m4-r2---api-interface-review)

> **Status**: Phase B complete
> **Plan ticket**:
> [M4-R2](../implementation-plan.md#m4-r2---api-interface-review)
> **Execution record**:
> [docs/execution/M4-R2.md](M4-R2.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/design-review.md](../policies/common/reviews/design-review.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#1-library-api),
> [docs/execution/M4-R1.md](M4-R1.md),
> [docs/execution/M4-R1-review.md](M4-R1-review.md),
> [docs/future-work.md](../future-work.md),
> [docs/policies/terminology.md](../policies/terminology.md),
> [src/context_sync/__init__.py](../../src/context_sync/__init__.py),
> [src/context_sync/_sync.py](../../src/context_sync/_sync.py),
> [src/context_sync/_models.py](../../src/context_sync/_models.py),
> [src/context_sync/_errors.py](../../src/context_sync/_errors.py)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M4-R2-R1 | Low | Todo | Terminology Completeness | The review's §6 identifies the banned term "syncer" in the `context_dir` property docstring at [src/context_sync/_sync.py:270](../../src/context_sync/_sync.py#L270) and recommends rewording it. However, the same term appears as a variable name in the [src/context_sync/__init__.py](../../src/context_sync/__init__.py) module-level docstring code example at lines 15 and 19: `syncer = ContextSync(...)` and `result = await syncer.sync(...)`. Per [docs/policies/terminology.md](../policies/terminology.md), "syncer" must not appear anywhere in the project, including code within docstrings. The module docstring is the first thing callers and the generated API reference show, making it the most prominent API documentation surface. | [src/context_sync/__init__.py:15](../../src/context_sync/__init__.py#L15), [src/context_sync/__init__.py:19](../../src/context_sync/__init__.py#L19), [docs/policies/terminology.md](../policies/terminology.md) | The documentation-only fix recommended in definitive proposal item 3.c covers the `context_dir` property but not the module docstring. A caller reading the API reference or the package docstring still sees the banned term. | Extend the definitive proposal item 3.c (or the [M4-3](../implementation-plan.md#m4-3---rename-root-ticket-id-to-key) implementation scope) to also update the [src/context_sync/__init__.py](../../src/context_sync/__init__.py) module-level docstring code example, replacing the `syncer` variable name with a term consistent with [docs/policies/terminology.md](../policies/terminology.md) (for example, `ctx` or `context_sync`). |
| M4-R2-R2 | Low | Todo | Factual Accuracy | The review's §9 states the `__all__` in [src/context_sync/__init__.py](../../src/context_sync/__init__.py) "exports ~55 symbols across 13 categories" and that the essential surface includes "The `ContextSyncError` hierarchy (12 exception types)." The actual `__all__` list contains 67 symbols across 13 categories, and the error hierarchy exports 11 classes (not 12). The 67-symbol count: Core (1), Result models (4), Errors (11), Gateway types (11), Manifest (8), Lock (6), Pipeline (5), Renderer (1), Signatures (2), I/O (2), Config (10), Traversal (4), Version (2). | [src/context_sync/__init__.py:105-186](../../src/context_sync/__init__.py#L105) | Neither inaccuracy changes the review's recommendation (no surface-width change for 0.x, consider narrowing for 1.0.0). However, the 22% undercount could mislead a future 1.0.0 surface audit that relies on this review as a baseline. | Correct the counts in §9 of [docs/execution/M4-R2.md](M4-R2.md): replace "~55 symbols" with "67 symbols" and "12 exception types" with "11 exception classes." |

## Reviewer Notes

- Review scope: I reviewed [docs/execution/M4-R2.md](M4-R2.md) as a
  review-ticket execution artifact, verifying it against the plan scope at
  [docs/implementation-plan.md:572-591](../implementation-plan.md#L572), the
  execution model's review-ticket requirements (§4.5), the design review
  checklist at
  [docs/policies/common/reviews/design-review.md](../policies/common/reviews/design-review.md),
  and the actual source code at
  [src/context_sync/_sync.py](../../src/context_sync/_sync.py),
  [src/context_sync/_models.py](../../src/context_sync/_models.py),
  [src/context_sync/_errors.py](../../src/context_sync/_errors.py), and
  [src/context_sync/__init__.py](../../src/context_sync/__init__.py).
- I used the [M4-R1](M4-R1.md) execution artifact and its
  [review](M4-R1-review.md) as additional context since M4-R2 explicitly
  builds on M4-R1's CLI-level conclusions for the library-side assessment.
- The substantive API analysis is strong. The identification of the `_id`
  naming problem extending beyond M4-3's original scope (§1), the
  cross-method parameter inconsistency (§2), the sound reasoning for making
  `add()` internal (§3), and the assessment of the exception hierarchy (§7)
  are all well-grounded in the source code and design documents.
- The M4-3 assessment is the review's most valuable deliverable. It
  correctly identifies that the original ticket is too narrow and provides a
  concrete five-site rename scope that the implementation plan has already
  adopted at
  [docs/implementation-plan.md:614-625](../implementation-plan.md#L614).
- Follow-on tracking is complete. The
  [M4-3](../implementation-plan.md#m4-3---rename-root-ticket-id-to-key)
  detailed notes have been updated to reflect the broadened scope, and
  [FW-10](../future-work.md#fw-10-cli-simplification-amendment) includes the
  library-side method boundary changes (items 6-8). This is a clear
  improvement over the M4-R1 Phase A artifact, which left follow-on tracking
  incomplete (finding [M4-R1-R2](M4-R1-review.md#m4-r1-r2)).
- I independently verified every source-code claim in the review: the
  `root_ticket_id` parameter at
  [src/context_sync/_sync.py:292](../../src/context_sync/_sync.py#L292), the
  `ticket_ref` parameters at
  [src/context_sync/_sync.py:1170](../../src/context_sync/_sync.py#L1170) and
  [src/context_sync/_sync.py:1333](../../src/context_sync/_sync.py#L1333),
  the `SyncError.ticket_id` field at
  [src/context_sync/_models.py:33](../../src/context_sync/_models.py#L33),
  the `DiffEntry.ticket_id` field at
  [src/context_sync/_models.py:78](../../src/context_sync/_models.py#L78),
  the `context_dir` docstring at
  [src/context_sync/_sync.py:270](../../src/context_sync/_sync.py#L270), and
  the `SyncResult` docstring at
  [src/context_sync/_models.py:42](../../src/context_sync/_models.py#L42).
  All line references and content claims are accurate.
- The banned-term "syncer" appears more widely than the review identifies.
  Beyond the `context_dir` property docstring (found by the review) and the
  `__init__.py` module docstring ([M4-R2-R1](#m4-r2-r1)), the term is also
  used as a local variable name throughout
  [src/context_sync/_cli.py](../../src/context_sync/_cli.py) (every command
  handler) and as a public function name `make_syncer` in
  [src/context_sync/_testing.py](../../src/context_sync/_testing.py). These
  internal-code usages are outside M4-R2's "public library API" scope, but
  a comprehensive terminology cleanup should address them. The M4-R2 review
  is not expected to catalog internal variable names; however, the
  `__init__.py` module docstring is squarely within the public API
  documentation surface.
- I did not rerun lint, format, or test commands. The M4-R2 change set is
  docs-only (execution artifact and plan/future-work updates), and the
  validation-scope gate says not to run repository-wide validation for
  docs-only changes unless explicitly requested.

## Residual Risks and Testing Gaps

- The two findings are both low-severity and do not affect the review's
  substantive conclusions or recommendations. The M4-3 broadening, the
  FW-10 library-side items, and the documentation-only fixes are all
  well-routed.
- The biggest residual risk is not from M4-R2 itself but from its
  dependency chain: M4-3 depends on M4-R2, and FW-10 depends on a future
  plan amendment. If those downstream items stall, the naming
  inconsistencies identified by this review will persist in the shipped API.
- The `StrEnum`/`Literal` typing improvement for `DiffEntry.status` and
  `SyncError.error_type` (§8) is classified as optional and may be deferred
  indefinitely. If deferred past 1.0.0, the bare `str` typing becomes part
  of the stable contract and harder to change.
