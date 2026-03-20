# Review: [M1-1](../implementation-plan.md#m1-1---project-scaffold-and-public-runtime-contracts)

> **Status**: Phase B complete
> **Plan ticket**:
> [M1-1](../implementation-plan.md#m1-1---project-scaffold-and-public-runtime-contracts)
> **Execution record**:
> [docs/execution/M1-1.md](M1-1.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/coding-guidelines-python.md](../policies/common/coding-guidelines-python.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/adr.md](../adr.md#31-foundation),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#1-library-api),
> [docs/design/linear-domain-coverage-audit.md](../design/linear-domain-coverage-audit.md),
> [README.md](../../README.md)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M1-1-R1 | Medium | Todo | Test Harness | The reusable fake gateway cannot model a tracked issue that is known to the harness but currently not visible to the caller. `RefreshIssueMeta` explicitly carries a `visible` flag, and later plan items require quarantined-root and missing-visibility tests, but `FakeLinearGateway.get_refresh_issue_metadata()` only returns `visible=True` for bundled issues and omits all other issue IDs. There is no fake-side hook to preserve issue identity while reporting `visible=False`. | [src/context_sync/_gateway.py:227](../../src/context_sync/_gateway.py), [src/context_sync/_testing.py:173](../../src/context_sync/_testing.py), [tests/test_gateway.py:241](../../tests/test_gateway.py), [docs/implementation-plan.md:268](../implementation-plan.md), [docs/implementation-plan.md:378](../implementation-plan.md) | Later tickets, especially [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery), cannot use the advertised reusable harness to exercise root-quarantine and visibility-recovery behavior. That pushes later work toward ad-hoc fake implementations or leaves a key refresh scenario under-tested. | Extend `FakeLinearGateway` with an explicit visibility override or unavailable-issue registry so it can return `RefreshIssueMeta(..., visible=False)` for known tracked IDs, and add tests that cover visible-to-invisible behavior. |
| M1-1-R2 | Medium | Todo | Test Harness | `FakeLinearGateway.get_refresh_comment_metadata()` computes each reply's `root_comment_id` as its direct `parent_comment_id` instead of the thread's actual root comment ID. The refresh contract distinguishes `root_comment_id` from `parent_comment_id` explicitly, and the current tests only cover a top-level comment with no reply chain, so this bug remains hidden. | [src/context_sync/_gateway.py:249](../../src/context_sync/_gateway.py), [src/context_sync/_testing.py:189](../../src/context_sync/_testing.py), [tests/test_gateway.py:248](../../tests/test_gateway.py), [docs/design/0-top-level-design.md:426](../design/0-top-level-design.md) | Later refresh-signature tests can pass against the fake while hashing incorrect thread topology for nested replies. That weakens the reusable-harness contract that [M1-1](../implementation-plan.md#m1-1---project-scaffold-and-public-runtime-contracts) is supposed to establish and risks masking defects until real adapter work or live data. | Derive `root_comment_id` by walking the parent chain within the bundle comments, or carry explicit root-comment data in the fixture builders, and add at least one multi-level reply test that proves root and parent are not conflated. |
| M1-1-R3 | Low | Todo | Documentation | The README update points the `M1-O1` reference at `docs/planning/implementation-plan.md`, but the active implementation plan lives at `docs/implementation-plan.md` and the `docs/planning/implementation-plan.md` path does not exist. | [README.md:55](../../README.md), [docs/implementation-plan.md:138](../implementation-plan.md) | The onboarding docs now contain a broken source-of-truth link right where they explain the Linear bootstrap prerequisite. That is small, but it makes the repository feel less trustworthy and sends readers to a missing path. | Update the README link to the active [docs/implementation-plan.md](../implementation-plan.md) location for [M1-O1](../implementation-plan.md#m1-o1---live-linear-validation-environment-available). |

## Reviewer Notes

- The scaffold itself is otherwise in reasonable shape for an `M1-1` baseline.
  The package layout, public re-exports, configuration constants, result
  models, exception hierarchy, and stub async entry points all line up with the
  ticket's intended baseline and with the narrow adapter boundary from
  [docs/design/linear-domain-coverage-audit.md](../design/linear-domain-coverage-audit.md).
- Validation claims are mostly reproducible:
  `ruff check src/ tests/` passed,
  `ruff format --check src/ tests/` passed,
  and `PYTHONPATH=src pytest -q` passed all 82 tests during review.
- A bare `pytest -v` in a shell where the package has not been installed
  editable fails with `ModuleNotFoundError: context_sync`. That is consistent
  with the README's earlier `pip install -e ".[dev]"` step, so I am not
  recording it as a code finding, but it does mean the execution record's
  validation commands are only reproducible after following the documented
  install step.
- I did not find evidence that the scaffold violates the current
  [M1-D2](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary)
  Linear boundary. The real `linear-client` integration is still deferred and
  the fake gateway remains read-only.

## Residual Risks and Testing Gaps

- Even after [M1-1-R1](#findings) and [M1-1-R2](#findings) are fixed, the fake
  harness will still need later tickets to extend it with scenario-specific
  behaviors such as ticket-pruning, alias history, and lock-state modeling.
  That is expected; the risk here is specifically that the current baseline
  already misses two refresh-critical behaviors it claims to standardize.
- The scaffold currently has no tests that assert the documented developer
  command set from [README.md](../../README.md) is runnable from a fresh repo
  checkout after the documented editable install step. This is not yet a
  blocker, but it is why validation reproducibility depends on local setup
  discipline rather than on an explicit repo-side launcher.
- This review used repository artifacts plus direct inspection of the code and
  test suite. No live Linear calls were needed or attempted.
