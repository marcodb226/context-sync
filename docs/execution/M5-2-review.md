# Review: [M5-2](../implementation-plan.md#m5-2---supported-public-runtime-validation-and-smoke-path)

> **Status**: Phase B complete
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
| M5-2-R1 | High | Todo | Validation Completeness | The ticket still does not satisfy its live-validation contract. The plan makes real-environment smoke validation part of M5-2 itself, and the Phase A execution record explicitly says that live-workspace smoke validation "was not performed in this session." That means the ticket currently stops at automated public-surface coverage plus a documented recipe, not the credentialed smoke validation that M5-2 is supposed to deliver before the runtime is treated as proven. | [docs/implementation-plan.md:908](../implementation-plan.md#L908), [docs/implementation-plan.md:1076](../implementation-plan.md#L1076), [docs/implementation-plan.md:1082](../implementation-plan.md#L1082), [docs/implementation-plan.md:1103](../implementation-plan.md#L1103), [docs/execution/M5-2.md:110](M5-2.md#L110) | The repository still lacks durable evidence that the shipped CLI path works in a credentialed Linear environment. That leaves [M4-2-R3](M4-2-review.md#L24) only partially closed, keeps auth/bootstrap regressions invisible, and means M5-2 is not review-clean even though the automated suite passes locally. | Keep [M5-2](../implementation-plan.md#m5-2---supported-public-runtime-validation-and-smoke-path) open until one happy-path and one representative failure-path smoke run are actually executed against a real workspace or equivalent maintained live environment and recorded in repository artifacts (for example in [docs/execution/M5-2.md](M5-2.md) or a linked companion evidence file). |
| M5-2-R2 | Medium | Todo | Smoke Documentation | The new README smoke recipe's "missing credentials" check is not deterministic for the auth modes this repository documents. It tells operators to unset only `LINEAR_API_KEY`, but `linear-client.Linear()` defaults to `auth_mode=\"oauth\"`, and in that mode initialization succeeds whenever `LINEAR_CLIENT_ID` and `LINEAR_CLIENT_SECRET` are still set. It can also proceed from a persisted OAuth token file. So a reader can follow the documented failure-path step exactly and still not get the promised startup failure. | [README.md:247](../../README.md#L247), [README.md:280](../../README.md#L280), [docs/implementation-plan.md:1097](../implementation-plan.md#L1097), [linear-client src/linear_client/linear.py:72](../../../linear-client/src/linear_client/linear.py#L72), [linear-client src/linear_client/linear.py:99](../../../linear-client/src/linear_client/linear.py#L99), [linear-client src/linear_client/config.py:305](../../../linear-client/src/linear_client/config.py#L305), [linear-client src/linear_client/auth/oauth.py:90](../../../linear-client/src/linear_client/auth/oauth.py#L90) | Operators can get a false-negative smoke result and waste time debugging the CLI when the real problem is that the recipe left another supported auth path intact. The same omission also conflicts with M5-2's own note that OAuth and client-credentials validation must use a fresh v1.1.0 token file. | Rewrite the failure-path recipe so it explicitly neutralizes every supported auth path (API key, OAuth/client-credentials env vars, and persisted token file) or uses a deterministic isolated environment for the negative case. Also document the v1.1.0 token-file precondition from [docs/implementation-plan.md:1097](../implementation-plan.md#L1097) so reused legacy token files do not masquerade as runtime failures. |

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
