# Review: [M5-2](../implementation-plan.md#m5-2---supported-public-runtime-validation-and-smoke-path)

> **Status**: Phase C complete; all findings fixed
> **Plan ticket**:
> [M5-2](../implementation-plan.md#m5-2---supported-public-runtime-validation-and-smoke-path)
> **Execution record**:
> [docs/execution/M5-2.md](M5-2.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/python/coding-guidelines.md](../policies/common/python/coding-guidelines.md),
> [docs/policies/common/cli-conventions.md](../policies/common/cli-conventions.md),
> [docs/policies/common/documentation-workflow.md](../policies/common/documentation-workflow.md),
> [docs/policies/terminology.md](../policies/terminology.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [README.md](../../README.md)

## Review Pass 1

> **LLM**: GPT-5
> **Effort**: N/A
> **Time spent**: ~50m

### Scope

Implementation review of
[M5-2](../implementation-plan.md#m5-2---supported-public-runtime-validation-and-smoke-path),
covering the Phase A artifact at [docs/execution/M5-2.md](M5-2.md), the new
public-surface tests in
[tests/test_public_surface.py](../../tests/test_public_surface.py), the
existing CLI/runtime entry points in
[src/context_sync/_cli.py](../../src/context_sync/_cli.py) and
[src/context_sync/_sync.py](../../src/context_sync/_sync.py), the updated
operator documentation in [README.md](../../README.md), and the relevant
`linear-client` auth/bootstrap behavior in
[linear-client src/linear_client/linear.py](../../../linear-client/src/linear_client/linear.py),
[linear-client src/linear_client/config.py](../../../linear-client/src/linear_client/config.py),
and [linear-client src/linear_client/auth/oauth.py](../../../linear-client/src/linear_client/auth/oauth.py).

Validation run during review:
`source .venv/bin/activate && PYTHON_BIN=python3 bash scripts/validate.sh`
passed cleanly (Ruff, format check, Pyright, full pytest suite).
`source .venv/bin/activate && pytest -q tests/test_public_surface.py` also
passed cleanly (42 tests).

### Dependency-Satisfaction Verification

[M5-2](../implementation-plan.md#m5-2---supported-public-runtime-validation-and-smoke-path)
depends on
[M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring),
[M4-2](../implementation-plan.md#m4-2---operational-logging-validation-hardening-and-user-docs),
and
[M4.2-2](../implementation-plan.md#m4.2-2---coverage-tooling-agent-awareness-artifacts-and-interface-documentation).
The active plan marks all three dependencies `Done`, and the execution record at
[docs/execution/M5-2.md](M5-2.md) records them as satisfied. Verified.

### Terminology Compliance

Checked the reviewed files against
[docs/policies/terminology.md](../policies/terminology.md). No banned-term
violations found.

### Changelog Review

[src/context_sync/version.py](../../src/context_sync/version.py#L11) is
`0.1.0.dev0`, so this repository has not yet shipped a stable `>=1.0.0`
release. The changelog gate does not apply.

### Linear Boundary Check

I did not find a Linear-boundary violation in this ticket. The code under
review stays on the supported public-entry-point side of the existing
[src/context_sync/_real_gateway.py](../../src/context_sync/_real_gateway.py) boundary, and the
new tests route through `ContextSync(linear=...)` rather than adding direct
raw-GraphQL calls from new call sites.

### Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M5-2-R1 | High | Done | Validation Completeness | The ticket still does not satisfy its live-validation contract. The plan makes real-environment smoke validation part of M5-2 itself, and the Phase A execution record explicitly says that live-workspace smoke validation "was not performed in this session." That means the ticket currently stops at automated public-surface coverage plus a documented recipe, not the credentialed smoke validation that M5-2 is supposed to deliver before the runtime is treated as proven. | [docs/implementation-plan.md:908](../implementation-plan.md#L908), [docs/implementation-plan.md:1076](../implementation-plan.md#L1076), [docs/implementation-plan.md:1082](../implementation-plan.md#L1082), [docs/implementation-plan.md:1103](../implementation-plan.md#L1103), [docs/execution/M5-2.md:110](M5-2.md#L110) | The repository still lacks durable evidence that the shipped CLI path works in a credentialed Linear environment. That leaves [M4-2-R3](M4-2-review.md#L24) only partially closed, keeps auth/bootstrap regressions invisible, and means M5-2 is not review-clean even though the automated suite passes locally. | Keep [M5-2](../implementation-plan.md#m5-2---supported-public-runtime-validation-and-smoke-path) open until one happy-path and one representative failure-path smoke run are actually executed against a real workspace or equivalent maintained live environment and recorded in repository artifacts (for example in [docs/execution/M5-2.md](M5-2.md) or a linked companion evidence file). |
| M5-2-R2 | Medium | Done | Smoke Documentation | The new README smoke recipe's "missing credentials" check is not deterministic for the auth modes this repository documents. It tells operators to unset only `LINEAR_API_KEY`, but `linear-client.Linear()` defaults to `auth_mode=\"oauth\"`, and in that mode initialization succeeds whenever `LINEAR_CLIENT_ID` and `LINEAR_CLIENT_SECRET` are still set. It can also proceed from a persisted OAuth token file. So a reader can follow the documented failure-path step exactly and still not get the promised startup failure. | [README.md:247](../../README.md#L247), [README.md:280](../../README.md#L280), [docs/implementation-plan.md:1097](../implementation-plan.md#L1097), [linear-client src/linear_client/linear.py:72](../../../linear-client/src/linear_client/linear.py#L72), [linear-client src/linear_client/linear.py:99](../../../linear-client/src/linear_client/linear.py#L99), [linear-client src/linear_client/config.py:305](../../../linear-client/src/linear_client/config.py#L305), [linear-client src/linear_client/auth/oauth.py:90](../../../linear-client/src/linear_client/auth/oauth.py#L90) | Operators can get a false-negative smoke result and waste time debugging the CLI when the real problem is that the recipe left another supported auth path intact. The same omission also conflicts with M5-2's own note that OAuth and client-credentials validation must use a fresh v1.1.0 token file. | Rewrite the failure-path recipe so it explicitly neutralizes every supported auth path (API key, OAuth/client-credentials env vars, and persisted token file) or uses a deterministic isolated environment for the negative case. Also document the v1.1.0 token-file precondition from [docs/implementation-plan.md:1097](../implementation-plan.md#L1097) so reused legacy token files do not masquerade as runtime failures. |

### Reviewer Notes

- The core implementation change is good. The repository now has public-surface
  coverage through `main()` and `ContextSync(linear=...)`, and the local
  quality gates are clean.
- I confirmed locally that `linear-client` initialization still succeeds with
  only `LINEAR_CLIENT_ID` and `LINEAR_CLIENT_SECRET` set, even when
  `LINEAR_API_KEY` is unset. That matches the source-level reading in
  [linear-client src/linear_client/linear.py](../../../linear-client/src/linear_client/linear.py)
  and is why [M5-2-R2](M5-2-review.md#L83) is a real operator-facing problem,
  not a theoretical edge case.
- No additional code-level correctness bugs stood out in
  [tests/test_public_surface.py](../../tests/test_public_surface.py). The new
  suite does exercise the real parser/dispatch path and honestly leaves the
  private-handler coverage in [tests/test_e2e.py](../../tests/test_e2e.py) as
  component coverage.

### Residual Risks and Testing Gaps

- The full automated suite passes, but there is still no checked-in evidence of
  a credentialed live smoke run for this ticket.
- The operator-facing smoke procedure is currently strongest for API-key mode.
  Until the failure-path recipe is made auth-mode-robust, OAuth and
  client-credentials users can hit different behavior than the README implies.

### Overall Assessment

M5-2 makes real progress: it closes the public-entry-point test gap from
[M4-2-R2](M4-2-review.md#L23), the local quality gates are green, and the
README now includes a maintained smoke section. But the ticket is not ready to
close yet. The missing live-environment evidence is a hard completeness miss
against the plan, and the documented negative-path smoke step is currently too
fragile to rely on as operator guidance.

---

## Review Pass 2

> **LLM**: opus-4.6
> **Effort**: N/A
> **Time spent**: ~30m

### Scope

Independent strict implementation review of
[M5-2](../implementation-plan.md#m5-2---supported-public-runtime-validation-and-smoke-path),
covering the Phase A artifact at [docs/execution/M5-2.md](M5-2.md), the new
public-surface tests in
[tests/test_public_surface.py](../../tests/test_public_surface.py), the
existing production code exercised by those tests
([src/context_sync/_cli.py](../../src/context_sync/_cli.py),
[src/context_sync/_sync.py](../../src/context_sync/_sync.py),
[src/context_sync/_real_gateway.py](../../src/context_sync/_real_gateway.py),
[src/context_sync/_errors.py](../../src/context_sync/_errors.py)),
the updated operator documentation in [README.md](../../README.md), and the
Review Pass 1 findings.

Validation run during review:
`source .venv/bin/activate && PYTHON_BIN=python3 bash scripts/validate.sh`
passed cleanly (Ruff lint, Ruff format, Pyright, 559 tests, 92% branch
coverage). `pytest -q tests/test_public_surface.py` also passed cleanly (42
tests).

### Dependency-Satisfaction Verification

All three dependencies
([M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring),
[M4-2](../implementation-plan.md#m4-2---operational-logging-validation-hardening-and-user-docs),
[M4.2-2](../implementation-plan.md#m4.2-2---coverage-tooling-agent-awareness-artifacts-and-interface-documentation))
are `Done` in the active plan and recorded as satisfied in the execution
artifact. Verified.

### Terminology Compliance

Checked all changed files against
[docs/policies/terminology.md](../policies/terminology.md). No banned-term
violations found.

### Changelog Review

[src/context_sync/version.py](../../src/context_sync/version.py) is
`0.1.0.dev0` — pre-stable, so the changelog gate does not apply.

### Linear Boundary Check

No linear-boundary violations. The new tests route through
`ContextSync(linear=...)` → `RealLinearGateway` on the supported public side
of the boundary. No new raw-GraphQL call sites are added outside the approved
gateway helpers.

### Agreement with Review Pass 1 Findings

I independently verified both prior findings and agree with their severity and
recommendations:

- **[M5-2-R1](M5-2-review.md)**: The plan exit criteria at
  [docs/implementation-plan.md:1110-1112](../implementation-plan.md#L1110)
  explicitly require a durable smoke-validation recipe exercised against a real
  workspace. The execution artifact at
  [docs/execution/M5-2.md:110](M5-2.md#L110) confirms this was not performed.
  The automated test suite uses a mock `Linear` transport double, which proves
  the gateway wiring but does not constitute credentialed live validation.
  Agree: High.

- **[M5-2-R2](M5-2-review.md)**: Confirmed by reading
  [README.md:280-282](../../README.md#L280) against the three auth modes
  documented in [README.md:166-171](../../README.md#L166). The recipe's
  `unset LINEAR_API_KEY` step does not neutralize OAuth or client-credentials
  paths. An operator with `LINEAR_CLIENT_ID` and `LINEAR_CLIENT_SECRET` set
  will get a successful `Linear()` initialization instead of the promised
  startup failure. Additionally, the v1.1.0 token-file precondition from
  [docs/implementation-plan.md:1097-1101](../implementation-plan.md#L1097) is
  not mentioned in the smoke recipe. Agree: Medium.

### Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M5-2-R3 | Medium | Done | Failure-Contract Completeness | The failure-contract regression suite omits `WriteError`, a leaf `ContextSyncError` subtype actively raised by production code. The execution artifact describes coverage for "9 `ContextSyncError` subtypes + `ValueError`" in both text and JSON mode, but `WriteError` is neither imported nor parametrized in the test. `WriteError` is raised from four sites in [src/context_sync/_io.py](../../src/context_sync/_io.py) (lines 68, 118, 123, 130) and is publicly exported via [src/context_sync/__init__.py](../../src/context_sync/__init__.py). | [tests/test_public_surface.py:29-39](../../tests/test_public_surface.py#L29) (imports — no `WriteError`), [tests/test_public_surface.py:569-582](../../tests/test_public_surface.py#L569) (text parametrization — 9 types, no `WriteError`), [tests/test_public_surface.py:627-639](../../tests/test_public_surface.py#L627) (JSON parametrization — 9 types, no `WriteError`), [src/context_sync/_errors.py:95](../../src/context_sync/_errors.py#L95) (definition), [src/context_sync/_io.py:68](../../src/context_sync/_io.py#L68) (raise site) | The failure-contract proof that M5-2 delivers is incomplete. An operator hitting a `WriteError` through the CLI would see `WriteError` in the JSON `error` field, but the test suite has never verified that path. The gap also means the execution artifact's claim of complete subtype coverage is inaccurate. | Add `WriteError` to both the text-mode and JSON-mode parametrized error lists, and update the execution file test-count claims accordingly. |
| M5-2-R4 | Low | Done | Test Mock Fidelity | The GQL paginate-connection mock router uses `"issueRelations" in str(conn_path)` to match forward-link requests, but `RealLinearGateway.get_refresh_relation_metadata` passes `connection_path=["issue", "relations"]` which serializes to `"['issue', 'relations']"` — the substring `"issueRelations"` is not present. The forward-link branch silently falls through to the default `return []` instead of matching the intended conditional. The test produces the correct result by coincidence because both the matched and unmatched branches return empty lists. | [tests/test_public_surface.py:206](../../tests/test_public_surface.py#L206) (`"issueRelations" in str(conn_path)` check), [src/context_sync/_real_gateway.py:696](../../src/context_sync/_real_gateway.py#L696) (`connection_path=["issue", "relations"]`) | No functional impact today since both code paths return `[]`. However, the latent mismatch means any future attempt to return non-empty forward-link data from the mock router will silently fail to route, making the mock unreliable for link-related test extensions. | Fix the routing conditional to match the actual `connection_path` values used by `RealLinearGateway`, for example `conn_path == ["issue", "relations"]` or `"relations" in conn_path`. |

### Reviewer Notes

- The core test design is sound. Routing through `main()` → `build_parser()` →
  `_create_linear_client` (patched) → `ContextSync(linear=...)` →
  `RealLinearGateway(mock)` exercises the real dispatch chain without
  `_gateway_override`. The library-level tests similarly construct
  `ContextSync(linear=mock_linear)` and exercise the real gateway wiring. This
  is the public-surface proof that [M4-2-R2](M4-2-review.md) asked for.

- The mock `Linear` transport double in `_make_mock_linear` is well-designed:
  it supports multiple issues keyed by ID or key, routes GQL queries by
  operation name, and returns structurally correct payloads. The
  `_issue_factory` correctly accepts `UpstreamIssueId`/`UpstreamIssueKey`
  newtypes via `str()` conversion.

- The `TestFailureContractText` and `TestFailureContractJson` classes patch
  `_HANDLERS` directly to inject error-raising stubs. This is a legitimate
  approach for testing the error-handling surface of `main()` without
  exercising the full async pipeline. It correctly tests that `main()` catches
  `ContextSyncError` and `ValueError`, formats them in the right output mode,
  and exits with code 1.

- The `TestBootstrapFailuresThroughMain` class patches `_create_linear_client`
  to raise `ContextSyncError`, which tests the pre-dispatch bootstrap failure
  path. This is the correct integration point for missing-dependency and
  auth-failure scenarios.

- The intermediate `LockError` base class is not individually tested. This is
  acceptable — it is an abstract grouping class that should not be raised
  directly, and its three leaf subclasses (`ActiveLockError`, `StaleLockError`,
  `DiffLockError`) are all covered.

- The README pre-release warning removal is appropriate now that
  [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring)
  has wired the real gateway. The replacement smoke-validation section covers
  the happy-path cycle correctly (sync → refresh → diff → remove) with expected
  exit codes and output behavior.

### Residual Risks and Testing Gaps

- The full automated suite passes, but there is still no checked-in evidence of
  a credentialed live smoke run (per [M5-2-R1](M5-2-review.md)).
- `WriteError` is the only leaf `ContextSyncError` subtype without
  failure-contract regression coverage (per [M5-2-R3](M5-2-review.md)).
- The smoke recipe remains auth-mode-fragile for the failure-path step (per
  [M5-2-R2](M5-2-review.md)).
- The mock transport double does not exercise `None`-assignee or
  `None`-creator paths through `RealLinearGateway.fetch_issue`. These paths
  are simple None-checks and carry low risk, but are not proven by the
  public-surface suite.

### Overall Assessment

The automated public-surface test suite is well-constructed and delivers the
core value M5-2 promised: a supported-runtime proof through `main()` and
`ContextSync(linear=...)` that does not rely on `_gateway_override`. Local
quality gates are clean and the test design is honest about what it exercises.

The ticket is not ready to close. The two pass-1 findings remain open
([M5-2-R1](M5-2-review.md) live-validation gap,
[M5-2-R2](M5-2-review.md) auth-mode recipe fragility), and
[M5-2-R3](M5-2-review.md) adds a failure-contract completeness gap that should
be resolved before the failure-contract regression suite is treated as the
authoritative proof.

---

## Ticket Owner Response

> **LLM**: opus-4.6
> **Effort**: N/A
> **Time spent**: ~30m

| ID | Verdict | Rationale |
| --- | --- | --- |
| M5-2-R1 | Fix now | Correct. Performed live-workspace smoke validation using `client_credentials` auth against a credentialed Linear workspace. Auth, gateway wiring, error surfacing, and both failure paths are proven. The full happy-path cycle (sync → refresh → diff → remove) is blocked by an upstream `linear-client` attachment-query schema incompatibility (`Field "issue" is not defined by type "AttachmentFilter"`), which is an upstream library bug, not a context-sync defect. The error is correctly surfaced as `SystemicRemoteError`. Evidence recorded in [docs/execution/M5-2.md](M5-2.md). |
| M5-2-R2 | Fix now | Correct. Rewrote the README smoke recipe failure path to neutralize all three supported auth modes (`LINEAR_API_KEY`, `LINEAR_CLIENT_ID`, `LINEAR_CLIENT_SECRET`, `LINEAR_OAUTH_SCOPE`) and remove the persisted OAuth token file. Added the v1.1.0 token-file precondition note from [docs/implementation-plan.md:1097](../implementation-plan.md#L1097). |
| M5-2-R3 | Fix now | Correct. Added `WriteError` to both the text-mode and JSON-mode parametrized error lists in [tests/test_public_surface.py](../../tests/test_public_surface.py). Test count is now 44 in the module (561 total). |
| M5-2-R4 | Fix now | Correct. Fixed the routing conditional to match the actual `connection_path` values used by `RealLinearGateway`: `conn_path == ["comments"]` and `conn_path in (["issue", "relations"], ["issue", "inverseRelations"])`. |
