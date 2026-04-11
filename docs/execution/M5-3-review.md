# Review: [M5-3](../implementation-plan.md#m5-3---cli-auth-mode-selection)

> **Status**: Phase B review complete; findings recorded
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
| M5-3-R1 | High | Todo | Auth-mode Default Contract | Ticket-owner clarification says `context-sync` is intended to default to `client_credentials` because the tool is primarily for app-actor workflows. The current implementation does not actually make `client_credentials` the tool default; it implements an environment heuristic: `api_key` when unprefixed `LINEAR_API_KEY` is set, `client_credentials` when unprefixed `LINEAR_CLIENT_ID` is set, otherwise `oauth`. That means the no-flag behavior still falls back to `oauth`, and the README now documents that heuristic as the CLI contract. | [src/context_sync/_cli.py:181](../../src/context_sync/_cli.py#L181), [src/context_sync/_cli.py:212](../../src/context_sync/_cli.py#L212), [README.md:39](../../README.md#L39), [README.md:57](../../README.md#L57), [README.md:108](../../README.md#L108), [README.md:111](../../README.md#L111), [linear-client src/linear_client/linear.py:99](../../../linear-client/src/linear_client/linear.py#L99) | If the intended product contract is "context-sync defaults to app-actor auth," the shipped behavior is still wrong in important cases: a no-env invocation falls back to `oauth`, an API-key shell silently changes the default again, and operators cannot tell whether no-flag mode means a real fixed default or just env probing. That makes the auth contract harder to reason about and leaves the repo with docs that encode a different policy than the one you just stated. | Decide and encode one explicit no-flag policy. If `context-sync` should default to `client_credentials`, set that mode directly in `_create_linear_client()` when `--auth-mode` is omitted, update the README quick-start and credential examples to match, and require `--auth-mode api_key` / `--auth-mode oauth` for non-default flows. If env-driven convenience is preferred instead, document that as the intended contract and add an unambiguous rule that does not imply a fixed default. |
| M5-3-R2 | Medium | Todo | Prefix-Aware Config Compatibility | The new inference helper ignores `linear-client`'s environment-prefix contract. `_create_linear_client()` checks only raw `LINEAR_API_KEY` and `LINEAR_CLIENT_ID`, but `linear-client` resolves `<PREFIX>LINEAR_*` keys using `LINEAR_ENV_PREFIX` (for example `PM_LINEAR_API_KEY`). That means a prefixed configuration can fully satisfy the underlying library while this ticket's inference still falls back to the wrong mode. The new tests only cover unprefixed environment variables, so this compatibility gap is untested. | [src/context_sync/_cli.py:212](../../src/context_sync/_cli.py#L212), [linear-client src/linear_client/config.py:140](../../../linear-client/src/linear_client/config.py#L140), [linear-client src/linear_client/config.py:148](../../../linear-client/src/linear_client/config.py#L148), [linear-client docs/pub/configuration.md:54](../../../linear-client/docs/pub/configuration.md#L54), [linear-client docs/pub/configuration.md:67](../../../linear-client/docs/pub/configuration.md#L67), [tests/test_cli.py:783](../../tests/test_cli.py#L783), [tests/test_public_surface.py:523](../../tests/test_public_surface.py#L523) | Users relying on prefixed Linear environments cannot safely omit `--auth-mode`: a valid prefixed API-key or client-credentials setup can be misdetected as `oauth`, leading to confusing initialization failures or the wrong auth path. Because the explicit flag works, this may escape notice until a prefixed deployment uses the convenience path. | Make inference use the same prefix resolution rules as `linear-client`, including `LINEAR_ENV_PREFIX`, and add tests for prefixed `api_key` and prefixed `client_credentials` environments. If that added complexity is not wanted, remove custom inference and preserve the explicit-flag-only behavior. |

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
