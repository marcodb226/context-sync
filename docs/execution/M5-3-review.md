# Review: [M5-3](../implementation-plan.md#m5-3---cli-auth-mode-selection)

> **Status**: Phase C complete; all findings addressed
> **Plan ticket**:
> [M5-3](../implementation-plan.md#m5-3---cli-auth-mode-selection)
> **Execution record**:
> [docs/execution/M5-3.md](M5-3.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/python/coding-guidelines.md](../policies/common/python/coding-guidelines.md),
> [docs/policies/common/cli-conventions.md](../policies/common/cli-conventions.md),
> [docs/policies/terminology.md](../policies/terminology.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [README.md](../../README.md)

## Review Pass 1

> **LLM**: GPT-5
> **Effort**: N/A
> **Time spent**: ~35m

### Scope

Strict implementation review of
[M5-3](../implementation-plan.md#m5-3---cli-auth-mode-selection),
covering the Phase A artifact at [docs/execution/M5-3.md](M5-3.md), the CLI
implementation in [src/context_sync/_cli.py](../../src/context_sync/_cli.py),
the new parser and passthrough tests in [tests/test_cli.py](../../tests/test_cli.py)
and [tests/test_public_surface.py](../../tests/test_public_surface.py), the
operator docs in [README.md](../../README.md), and the upstream auth contract
in
[linear-client src/linear_client/linear.py](../../../linear-client/src/linear_client/linear.py),
[linear-client src/linear_client/config.py](../../../linear-client/src/linear_client/config.py),
[linear-client docs/pub/getting-started.md](../../../linear-client/docs/pub/getting-started.md),
and
[linear-client docs/pub/configuration.md](../../../linear-client/docs/pub/configuration.md).

Validation run during review:
`source .venv/bin/activate && PYTHON_BIN=python3 bash scripts/validate.sh`
passed cleanly (Ruff lint, Ruff format check, Pyright, full pytest suite: 581
tests, 92% coverage). `source .venv/bin/activate && pytest -q tests/test_cli.py -k 'auth_mode' tests/test_public_surface.py -k 'auth_mode'`
also passed cleanly (10 auth-mode-focused tests).

### Dependency-Satisfaction Verification

[M5-3](../implementation-plan.md#m5-3---cli-auth-mode-selection) depends only
on [M5-2](../implementation-plan.md#m5-2---supported-public-runtime-validation-and-smoke-path).
The active plan marks [M5-2](../implementation-plan.md#m5-2---supported-public-runtime-validation-and-smoke-path)
as `Done`, and the execution artifact at [docs/execution/M5-3.md](M5-3.md)
records that dependency as satisfied. Verified.

### Terminology Compliance

Checked the reviewed files against
[docs/policies/terminology.md](../policies/terminology.md). No banned-term
violations found.

### Changelog Review

[src/context_sync/version.py](../../src/context_sync/version.py#L11) is
`0.1.0.dev0`, so this repository has not yet shipped a stable `>=1.0.0`
release. The changelog gate does not apply.

### Linear Boundary Check

No Linear-boundary violation found in this ticket. The change stays in the CLI
construction layer and does not add new raw-GraphQL or out-of-boundary
`linear-client` usage outside the existing runtime entry path.

### Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M5-3-R1 | High | Done | Auth-mode Default Contract | Ticket-owner clarification says `context-sync` is intended to default to `client_credentials` because the tool is primarily for app-actor workflows. The current implementation does not actually make `client_credentials` the tool default; it implements an environment heuristic: `api_key` when unprefixed `LINEAR_API_KEY` is set, `client_credentials` when unprefixed `LINEAR_CLIENT_ID` is set, otherwise `oauth`. That means the no-flag behavior still falls back to `oauth`, and the README now documents that heuristic as the CLI contract. | [src/context_sync/_cli.py:181](../../src/context_sync/_cli.py#L181), [src/context_sync/_cli.py:212](../../src/context_sync/_cli.py#L212), [README.md:39](../../README.md#L39), [README.md:57](../../README.md#L57), [README.md:108](../../README.md#L108), [README.md:111](../../README.md#L111), [linear-client src/linear_client/linear.py:99](../../../linear-client/src/linear_client/linear.py#L99) | If the intended product contract is "context-sync defaults to app-actor auth," the shipped behavior is still wrong in important cases: a no-env invocation falls back to `oauth`, an API-key shell silently changes the default again, and operators cannot tell whether no-flag mode means a real fixed default or just env probing. That makes the auth contract harder to reason about and leaves the repo with docs that encode a different policy than the one you just stated. | Decide and encode one explicit no-flag policy. If `context-sync` should default to `client_credentials`, set that mode directly in `_create_linear_client()` when `--auth-mode` is omitted, update the README quick-start and credential examples to match, and require `--auth-mode api_key` / `--auth-mode oauth` for non-default flows. If env-driven convenience is preferred instead, document that as the intended contract and add an unambiguous rule that does not imply a fixed default. |
| M5-3-R2 | Medium | Discarded | Prefix-Aware Config Compatibility | The new inference helper ignores `linear-client`'s environment-prefix contract. `_create_linear_client()` checks only raw `LINEAR_API_KEY` and `LINEAR_CLIENT_ID`, but `linear-client` resolves `<PREFIX>LINEAR_*` keys using `LINEAR_ENV_PREFIX` (for example `PM_LINEAR_API_KEY`). That means a prefixed configuration can fully satisfy the underlying library while this ticket's inference still falls back to the wrong mode. The new tests only cover unprefixed environment variables, so this compatibility gap is untested. | [src/context_sync/_cli.py:212](../../src/context_sync/_cli.py#L212), [linear-client src/linear_client/config.py:140](../../../linear-client/src/linear_client/config.py#L140), [linear-client src/linear_client/config.py:148](../../../linear-client/src/linear_client/config.py#L148), [linear-client docs/pub/configuration.md:54](../../../linear-client/docs/pub/configuration.md#L54), [linear-client docs/pub/configuration.md:67](../../../linear-client/docs/pub/configuration.md#L67), [tests/test_cli.py:783](../../tests/test_cli.py#L783), [tests/test_public_surface.py:523](../../tests/test_public_surface.py#L523) | Users relying on prefixed Linear environments cannot safely omit `--auth-mode`: a valid prefixed API-key or client-credentials setup can be misdetected as `oauth`, leading to confusing initialization failures or the wrong auth path. Because the explicit flag works, this may escape notice until a prefixed deployment uses the convenience path. | Make inference use the same prefix resolution rules as `linear-client`, including `LINEAR_ENV_PREFIX`, and add tests for prefixed `api_key` and prefixed `client_credentials` environments. If that added complexity is not wanted, remove custom inference and preserve the explicit-flag-only behavior. |

### Reviewer Notes

- The explicit `--auth-mode` plumbing is implemented cleanly. Parser wiring,
  handler passthrough, and `Linear(auth_mode=...)` forwarding are all present
  in [src/context_sync/_cli.py](../../src/context_sync/_cli.py), and the local
  validation gates are green.
- The concerns are about the no-flag contract layered on top of that plumbing.
- After ticket-owner clarification that `context-sync` is meant to default to
  `client_credentials`, [M5-3-R1](M5-3-review.md#L78) should be read as "the
  implemented default policy does not match the intended product default,"
  not as an argument that context-sync must mirror `linear-client`'s upstream
  default.
- I did not find a missing-docstring, typing, lint, formatting, or
  terminology-policy issue in the touched code.

### Residual Risks and Testing Gaps

- There is no regression test for the clarified intended default policy
  ("no flag means `client_credentials`"), so the most important contract is
  not directly asserted anywhere today.
- There is no regression test for a standard OAuth shell with
  `LINEAR_CLIENT_ID` / `LINEAR_CLIENT_SECRET` present and no explicit
  `--auth-mode`, even though the current heuristic treats that as
  `client_credentials`.
- There is no regression test for prefixed environments via `LINEAR_ENV_PREFIX`
  (for example `PM_LINEAR_API_KEY`), which is the gap behind
  [M5-3-R2](M5-3-review.md#L79).

### Overall Assessment

The core feature request is mostly there: operators now have an explicit
`--auth-mode` flag, and the implementation is wired through the real CLI entry
path with passing tests. But M5-3 is not review-clean yet because the no-flag
auth-selection policy is still underspecified in code and docs. With the
clarified intent that `context-sync` should default to `client_credentials`,
the explicit flag support is solid, but the current heuristic fallback is not
the contract you described.

---

## Review Pass 2

> **LLM**: opus-4.6
> **Effort**: N/A
> **Time spent**: ~30m

### Scope

Strict independent review of
[M5-3](../implementation-plan.md#m5-3---cli-auth-mode-selection),
covering the Phase A artifact at [docs/execution/M5-3.md](M5-3.md), the CLI
implementation in [src/context_sync/_cli.py](../../src/context_sync/_cli.py),
the new tests in [tests/test_cli.py](../../tests/test_cli.py) and
[tests/test_public_surface.py](../../tests/test_public_surface.py), the
operator docs in [README.md](../../README.md), the upstream auth contract in
[linear-client src/linear_client/linear.py](../../../linear-client/src/linear_client/linear.py),
the governing ticket notes in
[docs/implementation-plan.md §M5-3](../implementation-plan.md#m5-3---cli-auth-mode-selection),
the pass 1 review at [docs/execution/M5-3-review.md](M5-3-review.md), and
the full `git diff a81adbf..b8f7870` (the two M5-3 commits against the
pre-M5-3 baseline).

Validation run during review:
`source .venv/bin/activate && PYTHON_BIN=python3 bash scripts/validate.sh`
passed cleanly (Ruff lint, Ruff format check, Pyright 0 errors, full pytest
suite: 581 tests, 92% coverage).
`source .venv/bin/activate && pytest -q tests/test_cli.py -k 'auth_mode' tests/test_public_surface.py -k 'auth_mode'`
also passed cleanly (10 auth-mode-focused tests).

### Dependency-Satisfaction Verification

[M5-3](../implementation-plan.md#m5-3---cli-auth-mode-selection) depends only
on [M5-2](../implementation-plan.md#m5-2---supported-public-runtime-validation-and-smoke-path).
The active plan marks
[M5-2](../implementation-plan.md#m5-2---supported-public-runtime-validation-and-smoke-path)
as `Done`, and the execution artifact at [docs/execution/M5-3.md](M5-3.md)
records that dependency as satisfied. Verified.

### Terminology Compliance

Checked
[src/context_sync/_cli.py](../../src/context_sync/_cli.py),
[tests/test_cli.py](../../tests/test_cli.py),
[tests/test_public_surface.py](../../tests/test_public_surface.py),
[README.md](../../README.md), and
[docs/execution/M5-3.md](M5-3.md)
against [docs/policies/terminology.md](../policies/terminology.md). No
banned-term violations found.

### Changelog Review

[src/context_sync/version.py](../../src/context_sync/version.py) is
`0.1.0.dev0` — pre-stable. The changelog gate does not apply.

### Linear Boundary Check

No Linear-boundary violation. The change stays within the CLI construction
layer; `_create_linear_client()` passes the selected mode to `Linear()` and
does not add new raw-GraphQL or out-of-boundary usage.

### Findings

No new findings. The dominant issue in this ticket was correctly identified by
[M5-3-R1](M5-3-review.md#findings) in pass 1. This pass independently
verified the evidence and agrees with the finding and its severity. See
[Agreement with pass 1](#agreement-with-pass-1-findings) below for the
detailed assessment.

### Agreement with Pass 1 Findings

**[M5-3-R1](M5-3-review.md#findings) (High) — Auth-mode default contract:**
Independently confirmed. The implementation plan at
[docs/implementation-plan.md:1116](../implementation-plan.md#m5-3---cli-auth-mode-selection)
is unambiguous:

> The context-sync CLI's no-flag default is `client_credentials`. This tool
> primarily targets app-actor workflows. `--auth-mode` exists so operators
> can opt into `oauth` or `api_key` explicitly when needed.

The implementation at
[src/context_sync/_cli.py:212–219](../../src/context_sync/_cli.py#L212)
instead introduces an environment-probing heuristic (`LINEAR_API_KEY` →
`api_key`, `LINEAR_CLIENT_ID` → `client_credentials`, fallback `oauth`).
This heuristic is then documented as the intended contract in three
surfaces: the `_create_linear_client()` docstring
([src/context_sync/_cli.py:186–193](../../src/context_sync/_cli.py#L186)),
the argparse help text
([src/context_sync/_cli.py:416–420](../../src/context_sync/_cli.py#L416)),
and the README global-options table and inference paragraph
([README.md:108](../../README.md#L108),
[README.md:111](../../README.md#L111)). The tests also encode the
inference contract rather than the plan-specified default: for example,
`test_infers_oauth_when_no_env_vars`
([tests/test_cli.py:807](../../tests/test_cli.py#L807)) asserts `oauth`
as the fallback, and `test_auth_mode_default_is_none`
([tests/test_cli.py:202](../../tests/test_cli.py#L202)) asserts the
parser default is `None` (triggering inference) rather than
`client_credentials`.

The mismatch is not a borderline interpretation — the plan states a
fixed default, and the implementation delivers an inferred one. This is
the highest-priority item for Phase C.

**[M5-3-R2](M5-3-review.md#findings) (Medium) — Prefix-aware config
compatibility:** The observation that the inference heuristic ignores
`LINEAR_ENV_PREFIX` is factually accurate. However, this reviewer
**disagrees with the recommendation** to add prefix resolution. The
implementation plan at
[docs/implementation-plan.md:1119–1122](../implementation-plan.md#m5-3---cli-auth-mode-selection)
explicitly constrains the scope:

> Do not make context-sync responsible for mirroring `linear-client`'s
> `LINEAR_ENV_PREFIX` / `env_prefix` behavior. Prefixed library variables
> are not part of the context-sync CLI contract. See
> [LC-9](../linear-client-issues.md#lc-9---environment-variable-prefixing-leaks-caller-policy-into-the-library).

Implementing prefix-aware inference would violate this scope constraint.
Moreover, the correct resolution of
[M5-3-R1](M5-3-review.md#findings) — replacing the inference heuristic
with a fixed `client_credentials` default — eliminates the prefix
compatibility gap entirely: when no env probing occurs, there is no
mismatch to detect. The Phase C response should evaluate
[M5-3-R2](M5-3-review.md#findings) in light of this scope constraint
and the natural resolution via [M5-3-R1](M5-3-review.md#findings).

### Reviewer Notes

- The explicit `--auth-mode` plumbing is mechanically clean. The parser
  wiring, handler passthrough across all four subcommands, `Linear(auth_mode=...)`
  forwarding, the `_AuthMode` type alias, and the `AUTH_MODE_CHOICES` constant
  are all well-structured. The typing is correct (`_AuthMode | None` for the
  parameter, `Literal[...]` for the alias).
- The test coverage for the *implemented* behavior is thorough: 6 parser
  tests, 5 env-inference unit tests, 4 handler-passthrough tests, and 5
  public-surface integration tests. The tests are well-organized across
  `TestParserConstruction`, `TestAuthModeEnvInference`,
  `TestAuthModeHandlerPassthrough`, and `TestCliMainAuthMode`. But the tests
  validate the inference heuristic, not the plan-specified default, so they
  will need to be reworked when [M5-3-R1](M5-3-review.md#findings) is
  addressed.
- No new typing, lint, formatting, or coding-guidelines violations found in
  the M5-3 diff. The `_AuthMode` Literal type is appropriate and avoids
  `Any`. Docstrings include Parameters, Returns, and Raises sections.
- The README updates are well-written and the smoke recipe correctly covers
  both `api_key` and `client_credentials` modes. The credential-setup section
  and environment-variables table are accurate for `linear-client` v1.1.0.
- I did not identify any security, concurrency, or operational-readiness
  issues in the M5-3 diff.

### Residual Risks and Testing Gaps

- The residual risks and testing gaps identified in pass 1 remain valid.
  In particular: no regression test for the plan-specified `client_credentials`
  default, no test for a clean-env invocation asserting
  `client_credentials` (not `oauth`), and the inference tests will need to
  be removed or rewritten when the default is fixed.
- The smoke recipe's `client_credentials` section
  ([README.md:297–305](../../README.md#L297)) uses explicit
  `--auth-mode client_credentials` on every command. Once the default is
  fixed, this section should also exercise the bare no-flag invocation to
  validate the default contract.

### Overall Assessment

This review independently confirms the pass 1 assessment. The explicit
`--auth-mode` flag mechanism is solid — parser construction, handler
forwarding, constructor passthrough, typing, and explicit-flag tests are all
well-implemented. The single blocking issue is that the no-flag default
contract diverges from the implementation plan specification: the plan says
`client_credentials`, the code delivers env-inference with an `oauth` fallback.
All downstream documentation and test surfaces encode the implemented behavior
rather than the specified one.

[M5-3-R1](M5-3-review.md#findings) remains the gating item for Phase C. The
fix is narrowly scoped: set the argparse default to `client_credentials` (or
apply the fixed default in `_create_linear_client`), remove the inference
block, update the docstring/help-text/README, and rework the inference tests
to assert the fixed default. [M5-3-R2](M5-3-review.md#findings) resolves
naturally once the inference heuristic is removed.

## Ticket Owner Response

> **LLM**: opus-4.6
> **Effort**: N/A
> **Time spent**: ~20m

| ID | Verdict | Rationale |
| --- | --- | --- |
| [M5-3-R1](M5-3-review.md#findings) | Fix now | Both reviewers correctly identified that the implementation diverges from the plan-specified fixed default of `client_credentials`. The env-inference heuristic will be removed and replaced with a fixed `client_credentials` default in both the argparse parser and `_create_linear_client()`. Docstrings, help text, README, and tests will be reworked accordingly. |
| [M5-3-R2](M5-3-review.md#findings) | Discard | The plan at [docs/implementation-plan.md:1119–1122](../implementation-plan.md#m5-3---cli-auth-mode-selection) explicitly excludes prefix-aware inference from the context-sync CLI contract: prefixed library variables are not part of this tool's scope, per [LC-9](../linear-client-issues.md#lc-9---environment-variable-prefixing-leaks-caller-policy-into-the-library). Additionally, the [M5-3-R1](M5-3-review.md#findings) fix eliminates env probing entirely, making the prefix compatibility gap moot. |
