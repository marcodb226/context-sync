# Review: [M4-2](../implementation-plan.md#m4-2---operational-logging-validation-hardening-and-user-docs)

> **Status**: Phase B complete
> **Plan ticket**:
> [M4-2](../implementation-plan.md#m4-2---operational-logging-validation-hardening-and-user-docs)
> **Execution record**:
> [docs/execution/M4-2.md](M4-2.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/python/coding-guidelines.md](../policies/common/python/coding-guidelines.md),
> [docs/policies/common/cli-conventions.md](../policies/common/cli-conventions.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/adr.md](../adr.md#61-snapshot-consistency-contract),
> [README.md](../../README.md)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M4-2-R1 | High | Todo | Operator Readiness | The new operator docs present both the CLI and the public `ContextSync(linear=...)` constructor path as usable, but the shipped runtime still cannot execute any real Linear-backed command. Every CLI handler constructs `ContextSync(linear=linear)`, while `ContextSync.__init__()` explicitly leaves `_gateway` unset on that path and every operation immediately raises `ContextSyncError` with "No gateway available". The repository even retains a regression test that asserts this failure mode. | [README.md:53](../../README.md#L53), [README.md:68](../../README.md#L68), [README.md:223](../../README.md#L223), [src/context_sync/_cli.py:212](../../src/context_sync/_cli.py#L212), [src/context_sync/_sync.py:246](../../src/context_sync/_sync.py#L246), [src/context_sync/_sync.py:335](../../src/context_sync/_sync.py#L335), [src/context_sync/_sync.py:664](../../src/context_sync/_sync.py#L664), [src/context_sync/_sync.py:1199](../../src/context_sync/_sync.py#L1199), [src/context_sync/_sync.py:1362](../../src/context_sync/_sync.py#L1362), [src/context_sync/_sync.py:1483](../../src/context_sync/_sync.py#L1483), [tests/test_sync.py:681](../../tests/test_sync.py#L681), [docs/execution/M4-2.md:105](M4-2.md#L105) | Human operators following the new quick-start and CLI sections cannot complete even a first `sync`, and programmatic callers following the new library example hit the same hard failure. The ticket therefore overstates runtime readiness and leaves the repo with user docs that advertise a public surface that is still intentionally inert. | Do not close [M4-2](../implementation-plan.md#m4-2---operational-logging-validation-hardening-and-user-docs) until the real Linear-backed gateway path is wired for the documented CLI and library entry points. If that work is intentionally out of scope, then remove or clearly qualify the operator-ready examples and alignment claims in [README.md](../../README.md) and [docs/execution/M4-2.md](M4-2.md) so the repository stops promising a working surface it does not yet ship. |
| M4-2-R2 | Medium | Todo | Validation Coverage | The new "`end-to-end`" suite does not exercise the public CLI surface it claims to validate. The tests import private `_run_*` helpers, fabricate an `argparse.Namespace`, and inject `_gateway_override`; but `_gateway_override` is documented in the library as a testing hook that production callers should never use. That means the new coverage never touches `main()`, parser construction, `--log-level` configuration, console-script dispatch, or the real `linear=` constructor path. | [docs/implementation-plan.md:479](../implementation-plan.md#L479), [tests/test_e2e.py:2](../../tests/test_e2e.py#L2), [tests/test_e2e.py:21](../../tests/test_e2e.py#L21), [tests/test_e2e.py:39](../../tests/test_e2e.py#L39), [tests/test_e2e.py:93](../../tests/test_e2e.py#L93), [src/context_sync/_sync.py:220](../../src/context_sync/_sync.py#L220), [src/context_sync/_cli.py:198](../../src/context_sync/_cli.py#L198), [src/context_sync/_cli.py:485](../../src/context_sync/_cli.py#L485) | The ticket's headline "validation hardening" is undermined because the new suite can pass while the installed CLI remains broken or behaviorally different. In practice, that is exactly what happened: the repo now reports full end-to-end coverage while the real CLI path still cannot run. | Add a supported integration path that exercises [src/context_sync/_cli.py](../../src/context_sync/_cli.py) through `main()` or the console script with a fakeable gateway boundary, and keep the private-handler coverage classified as component tests rather than end-to-end proof. |
| M4-2-R3 | Low | Todo | Validation Documentation | The ticket acceptance notes require "manual CLI smoke checks documented in repo docs", but neither the repository docs nor the execution record contains a smoke-test procedure or recorded results. The execution file lists lint, format, pytest, and `cloc`; the README documents install steps, usage examples, and generic developer commands, but not an install-to-run smoke checklist for the real CLI. | [docs/implementation-plan.md:479](../implementation-plan.md#L479), [docs/execution/M4-2.md:84](M4-2.md#L84), [README.md:53](../../README.md#L53), [README.md:250](../../README.md#L250), [README.md:329](../../README.md#L329) | Future reviewers and operators do not have a durable repository artifact that says how to verify the human-facing CLI after setup, or what success/failure signals to expect. Given the automated suite's reliance on test-only injection, that missing manual validation story leaves the public runtime especially under-verified. | Add a short manual smoke section to [README.md](../../README.md) and/or [docs/execution/M4-2.md](M4-2.md) that covers environment bootstrap, one successful command path, and one representative failure path, including the expected stdout/stderr behavior. |

## Reviewer Notes

- Review scope covered [docs/execution/M4-2.md](M4-2.md),
  [README.md](../../README.md),
  [tests/test_e2e.py](../../tests/test_e2e.py),
  [src/context_sync/_cli.py](../../src/context_sync/_cli.py),
  [src/context_sync/_sync.py](../../src/context_sync/_sync.py),
  [src/context_sync/_diff.py](../../src/context_sync/_diff.py), and
  [src/context_sync/_lock.py](../../src/context_sync/_lock.py), along with the
  governing plan and ADR sections.
- I did not find a Linear-boundary violation in this ticket. The changed code
  still routes runtime behavior through the gateway abstraction rather than
  adding direct `linear.gql.*` calls.
- Changelog review did not apply here. The execution record states the repo is
  still pre-stable at [docs/execution/M4-2.md:111](M4-2.md#L111).
- I did not rerun the repository lint, format, or test commands during this
  review. The current worktree diff before writing this review artifact was
  docs-only, and the repository policy says not to run the declared validation
  commands for docs-only review work unless explicitly requested.

## Residual Risks and Testing Gaps

- There is still no supported test path that executes the real installed CLI
  against a fake or adapter-backed gateway. The new
  [tests/test_e2e.py](../../tests/test_e2e.py) suite exercises private handler
  functions instead.
- The repository now has richer operator docs, but the docs do not currently
  warn readers that the real `linear=` constructor path remains intentionally
  unwired in [src/context_sync/_sync.py](../../src/context_sync/_sync.py).
- No repository artifact currently documents a manual smoke-test recipe for the
  public CLI surface, despite that acceptance criterion appearing in
  [docs/implementation-plan.md](../implementation-plan.md#L479).
