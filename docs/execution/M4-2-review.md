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

---

## Second Review Pass

> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/python/coding-guidelines.md](../policies/common/python/coding-guidelines.md),
> [docs/policies/common/cli-conventions.md](../policies/common/cli-conventions.md),
> [docs/adr.md §6.1](../adr.md#61-snapshot-consistency-contract),
> [docs/implementation-plan.md](../implementation-plan.md)

### Agreement with First Pass

M4-2-R1, M4-2-R2, and M4-2-R3 are confirmed. The operator-readiness gap
(M4-2-R1) and the test-scope mislabeling (M4-2-R2) are the most consequential
issues for this ticket. The second pass does not duplicate those findings but
adds six new ones below.

### Additional Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M4-2-R4 | Medium | Todo | Documentation | The [tests/test_e2e.py](../../tests/test_e2e.py) module docstring (line 3) claims "These tests exercise the full CLI → library → fake gateway → output pipeline" but no test in the file touches `main()`, `build_parser()`, or the console-script entry point. The `TestFullCycleE2E` class calls private `_run_*` handlers directly; the `TestLoggingContract` class uses `make_syncer()` and never enters any CLI code at all. The header docstring is the primary artifact a future contributor reads to understand the file's scope, and coding guidelines require that it be accurate. | [tests/test_e2e.py:3](../../tests/test_e2e.py#L3), [tests/test_e2e.py:93](../../tests/test_e2e.py#L93), [tests/test_e2e.py:194](../../tests/test_e2e.py#L194), [src/context_sync/_cli.py:485](../../src/context_sync/_cli.py#L485) | The misleading docstring reinforces the M4-2-R2 coverage gap by framing component-level tests as full-pipeline proof. A future reviewer trusting the docstring would skip adding the real CLI integration coverage that the file promises but does not deliver. | Rewrite the docstring to say the file tests the library pipeline with a fake gateway via private CLI handlers, and explicitly note that `main()` and parser-level dispatch are out of scope. |
| M4-2-R5 | Medium | Todo | Validation Robustness | The `_make_args` helper in [tests/test_e2e.py](../../tests/test_e2e.py) hardcodes default values (`max_tickets_per_root=200`, `missing_root_policy="quarantine"`, `log_level="WARNING"`) that are semantically duplicates of constants defined in [src/context_sync/_cli.py](../../src/context_sync/_cli.py) and [src/context_sync/_config.py](../../src/context_sync/_config.py). The helper does not import or reference those constants. | [tests/test_e2e.py:47](../../tests/test_e2e.py#L47), [tests/test_e2e.py:48](../../tests/test_e2e.py#L48), [tests/test_e2e.py:50](../../tests/test_e2e.py#L50), [src/context_sync/_cli.py:419](../../src/context_sync/_cli.py#L419), [src/context_sync/_cli.py:57](../../src/context_sync/_cli.py#L57), [src/context_sync/_config.py](../../src/context_sync/_config.py) | If a parser default changes (for example `DEFAULT_MAX_TICKETS_PER_ROOT` is raised to 500), the e2e tests will silently test a different default than the shipped CLI. Tests would pass against stale values, masking regressions in the real operator experience. This is a DRY violation under the coding guidelines. | Import `DEFAULT_MAX_TICKETS_PER_ROOT` from [src/context_sync/_config.py](../../src/context_sync/_config.py) and `DEFAULT_LOG_LEVEL` from [src/context_sync/_cli.py](../../src/context_sync/_cli.py) so the test helper stays aligned with the shipped defaults. |
| M4-2-R6 | Medium | Todo | Operational | ADR §6.1 requires that INFO-level logs cover "any catastrophic abort reason." When a `SystemicRemoteError` or other `ContextSyncError` is raised mid-operation inside `_sync_under_lock` or `_refresh_under_lock`, the exception propagates to the caller without an INFO log recording the abort. The CLI entry point prints the error to stderr at [src/context_sync/_cli.py:529](../../src/context_sync/_cli.py#L529), but this is a raw `print()`, not a structured INFO log. Library callers who set up their own logging never see an abort event in the log stream. | [docs/adr.md:471](../adr.md#L471), [src/context_sync/_sync.py:356–368](../../src/context_sync/_sync.py#L356), [src/context_sync/_sync.py:679–689](../../src/context_sync/_sync.py#L679), [src/context_sync/_cli.py:521–530](../../src/context_sync/_cli.py#L521) | Operators monitoring INFO logs for lifecycle events will see a "started" log with no matching "completed" and no "aborted" explanation. Diagnosing the failure requires correlating the log gap with stderr output or an exception trace, which may not be captured in the same log sink. | Add an INFO-level log in the `except` or `finally` path of `sync()`, `refresh()`, `add()`, `remove_root()`, and `diff()` (or a shared wrapper) that records the abort reason and duration before the exception propagates. |
| M4-2-R7 | Low | Todo | Readability | The sync started log uses `root_count=` ([src/context_sync/_sync.py:474](../../src/context_sync/_sync.py#L474)) while the refresh/add/remove-root started log uses `active_roots=` ([src/context_sync/_sync.py:940](../../src/context_sync/_sync.py#L940)). Both fields report the same logical value: the number of roots being traversed. The ADR says "root count" without prescribing a field name, but the inconsistency between synonymous fields makes structured log parsing and alerting harder. | [src/context_sync/_sync.py:474](../../src/context_sync/_sync.py#L474), [src/context_sync/_sync.py:940](../../src/context_sync/_sync.py#L940) | Operators writing log-based alerts or dashboards must handle two different field names for the same semantic concept across modes. | Standardize on one field name (for example `active_roots=` across all modes, since refresh adds `quarantined=` as a separate count and that distinction is useful). |
| M4-2-R8 | Medium | Todo | Documentation | The README's INFO logging description says "root count, ticket cap, reachable count, created/updated/unchanged/removed/error counts … whether any roots hit their per-root cap" as a blanket characterization of INFO output. This matches `sync` and `refresh` but does not describe `diff`, which logs `tracked_tickets=`, `current=`, `stale=`, `missing_locally=`, `missing_remotely=` — a different vocabulary and different categories. A reader following the README's description while monitoring `diff` INFO output would not find the fields promised. | [README.md:166–168](../../README.md#L166), [src/context_sync/_diff.py:196](../../src/context_sync/_diff.py#L196), [src/context_sync/_diff.py:332–341](../../src/context_sync/_diff.py#L332) | The coding guidelines require "Supported documentation must stay aligned with behavior." The README's logging section is the primary operator reference for understanding log output, and it under-specifies the diff mode. Operators may misinterpret diff logs or assume the tool is broken when they see different fields than documented. | Expand the README's INFO description to distinguish mutating modes (sync/refresh/add/remove-root) from the read-only diff mode, documenting diff's actual field names. |
| M4-2-R9 | Low | Todo | Readability | The variable `errored_uids` in [src/context_sync/_diff.py:257](../../src/context_sync/_diff.py#L257) is populated from `SyncError.ticket_id`, which holds issue keys (e.g. `"PROJ-1"`), not UUIDs. The comparison at [src/context_sync/_diff.py:263](../../src/context_sync/_diff.py#L263) (`manifest_entry.current_key in errored_uids`) is correct only because both sides are keys. The name `errored_uids` suggests UUID semantics and could mislead a maintainer into adding UUID-based comparisons that silently fail. | [src/context_sync/_diff.py:257](../../src/context_sync/_diff.py#L257), [src/context_sync/_diff.py:222](../../src/context_sync/_diff.py#L222), [src/context_sync/_diff.py:263](../../src/context_sync/_diff.py#L263) | No runtime bug today, but the naming creates a latent correctness risk. A future change that iterates `errored_uids` and compares against manifest UUID keys would silently produce empty intersections. | Rename to `errored_keys` to match the actual content semantics. |

### Second-Pass Reviewer Notes

- Review scope: full read of all files listed in the
  [M4-2 execution record](M4-2.md), including
  [src/context_sync/_sync.py](../../src/context_sync/_sync.py),
  [src/context_sync/_diff.py](../../src/context_sync/_diff.py),
  [src/context_sync/_lock.py](../../src/context_sync/_lock.py),
  [src/context_sync/_cli.py](../../src/context_sync/_cli.py),
  [tests/test_e2e.py](../../tests/test_e2e.py),
  [README.md](../../README.md), and the governing
  [ADR §6.1](../adr.md#61-snapshot-consistency-contract) logging contract.
  The first-pass review was read and confirmed before starting.
- No Linear-boundary violations. All M4-2 changes remain within the gateway
  abstraction.
- Changelog review not applicable (pre-stable at `0.1.0.dev0`).
- No correctness bugs found in the core logging additions or the diff pipeline
  extraction. The sync/refresh/diff logging logic correctly emits the contract
  fields at the right levels.
- The `_lock.py` DEBUG log for clean acquisition
  ([src/context_sync/_lock.py:171–175](../../src/context_sync/_lock.py#L171))
  is correctly placed and satisfies the ADR's "lock-handling logs" requirement
  for the clean-acquisition case.
- The per-ticket DEBUG logs for stale/fresh decisions in
  [src/context_sync/_sync.py:1019–1029](../../src/context_sync/_sync.py#L1019)
  correctly cover all four staleness paths (format_version, missing cursor,
  cursor mismatch, fresh) with the ticket key in each message.
- I did not rerun lint, format, or test commands. The worktree diff is
  docs-only (review artifact edits), which falls under the validation scope
  gate exemption.

### Second-Pass Residual Risks and Testing Gaps

- The logging contract tests in `TestLoggingContract` verify INFO/DEBUG
  content through the library (`make_syncer`) but do not verify that the CLI's
  `--log-level` flag actually configures the logging framework correctly. A
  bug in the `main()` log-level setup code
  ([src/context_sync/_cli.py:504–515](../../src/context_sync/_cli.py#L504))
  would not be caught by any test added in M4-2.
- There is no test that verifies the abort-log requirement from ADR §6.1.
  The existing tests exercise only the happy path; a test that injects a
  `SystemicRemoteError` mid-operation and asserts an INFO abort log is missing.
- The `_make_args` dead `log_level` attribute
  ([tests/test_e2e.py:50](../../tests/test_e2e.py#L50)) is never consumed by
  any code path exercised in the e2e suite, suggesting the test harness was
  designed for a broader integration scope that was not implemented.
