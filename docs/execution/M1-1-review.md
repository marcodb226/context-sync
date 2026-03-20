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
| M1-1-R4 | Medium | Todo | Test Harness | `FakeLinearGateway` batch-method parameter types are narrower than the `LinearGateway` Protocol specification. The Protocol declares `issue_ids: Sequence[str]` for `get_ticket_relations`, `get_refresh_issue_metadata`, `get_refresh_comment_metadata`, and `get_refresh_relation_metadata`, but the fake declares `issue_ids: list[str] \| tuple[str, ...]` for all four methods. Under Protocol structural subtyping with parameter contravariance, the fake's narrower input type does not satisfy the Protocol's declared contract. | [src/context_sync/_gateway.py:345](../../src/context_sync/_gateway.py), [src/context_sync/_testing.py:162](../../src/context_sync/_testing.py), [src/context_sync/_testing.py:173](../../src/context_sync/_testing.py), [src/context_sync/_testing.py:189](../../src/context_sync/_testing.py), [src/context_sync/_testing.py:220](../../src/context_sync/_testing.py) | The fake is the reference implementation that later tickets extend. Having it accept a narrower type than the Protocol declares means static type checkers will reject callers that pass a non-list/tuple `Sequence` to the fake, even though the Protocol allows it. This silently establishes a narrower parameter convention in the reusable harness than the Protocol requires, and any later code that tests with the fake will be constrained to the narrower types. | Align the fake's batch-method parameter types with the Protocol by using `Sequence[str]` (from `collections.abc`) consistently. |
| M1-1-R5 | Low | Todo | API Contract | The `sync()` stub signature places `max_tickets_per_root` on the constructor as a required default with a per-call `int \| None` override, while the top-level design §1 specifies `max_tickets_per_root: int = 200` only on `sync()` with no constructor-level parameter. The other four entry points (`refresh`, `add`, `remove_root`, `diff`) match the design exactly. | [src/context_sync/_sync.py:138](../../src/context_sync/_sync.py), [docs/design/0-top-level-design.md:29](../../docs/design/0-top-level-design.md) | Later tickets implementing `sync()` need an unambiguous authoritative interface. The scaffold establishes a constructor-level-default pattern while the governing design says per-call-only with a hardcoded 200; without an explicit reconciliation the implementor must decide which contract is correct. The implementation's pattern may be an improvement, but it should be deliberate. | Either update [docs/design/0-top-level-design.md](../design/0-top-level-design.md#1-library-api) to reflect the constructor-level default pattern, or align the stub with the design's per-call-only signature. Record the chosen contract in the [M1-1](M1-1.md) execution file so later implementors do not have to re-derive it. |
| M1-1-R6 | Low | Todo | Testing | `test_satisfies_protocol` in [tests/test_gateway.py:191](../../tests/test_gateway.py) does not perform a runtime protocol conformance check. The test annotates a variable as `LinearGateway` and assigns a `FakeLinearGateway`, but Python does not enforce `typing.Protocol` structural conformance at runtime — the assignment always succeeds. `LinearGateway` is not decorated with `@runtime_checkable`, so `isinstance` cannot be used either. The behavioral tests below it do exercise each protocol method individually, so the practical risk is limited, but the test communicates a verification it does not actually perform. | [tests/test_gateway.py:191](../../tests/test_gateway.py), [src/context_sync/_gateway.py:298](../../src/context_sync/_gateway.py) | The test gives false confidence in protocol conformance. As [M1-1-R4](#findings) demonstrates, the fake's parameter types already diverge from the Protocol, and this test did not catch it. If the fake drifts further in method count or signatures, this test will still pass. | Either add `@runtime_checkable` to `LinearGateway` and use `assert isinstance(gw, LinearGateway)` for a genuine runtime check, or add a static type-checking step (mypy/pyright) to the validation commands so protocol mismatches surface during CI, or rename the test to reflect what it actually verifies (e.g., `test_instantiates_without_error`). |

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

## Second Review Notes

- Second review validation: `ruff check src/ tests/` passed, `ruff format
  --check src/ tests/` passed, and `PYTHONPATH=src pytest -q` passed all 82
  tests. Results are consistent with the first review.
- The first review's three findings ([M1-1-R1](#findings), [M1-1-R2](#findings),
  [M1-1-R3](#findings)) are confirmed still present and accurately described.
- The second review focused on protocol-contract fidelity, design-to-
  implementation alignment, and test-suite verification depth — areas
  orthogonal to the first review's focus on fake-gateway behavioral
  completeness and documentation accuracy.
- The [M1-1-R4](#findings) parameter-type mismatch is structurally related to
  [M1-1-R1](#findings): both weaken the reusable harness contract that
  [M1-1](../implementation-plan.md#m1-1---project-scaffold-and-public-runtime-contracts)
  is supposed to establish. [M1-1-R1](#findings) concerns missing behavioral
  modeling (visibility=False), while [M1-1-R4](#findings) concerns the type-
  level Protocol contract (Sequence vs list|tuple). Fixing both together would
  produce a more faithful reference implementation.
- The `make_syncer()` factory defaults its `context_dir` to
  `Path("test-context")`, a relative path. The docstring says tests should
  place it inside a `tmp_path` fixture, but this is not enforced. Since all
  stub methods raise `NotImplementedError`, no file I/O can happen yet. Once
  later tickets implement file operations, tests that omit `context_dir` would
  silently write to the working directory. This is not recorded as a formal
  finding because the risk is future-only and documented, but it is worth
  noting for implementors of [M1-2](../implementation-plan.md#m1-2---manifest-lock-and-rendering-primitives)
  and beyond.
- The scaffold's data types (`IssueData`, `TicketBundle`, etc.) use
  `frozen=True` dataclasses with mutable `list` fields. The `frozen` flag
  prevents field reassignment but not in-place list mutation. This is a known
  Python limitation rather than a code defect — the design contracts in
  [docs/design/0-top-level-design.md](../design/0-top-level-design.md) also
  specify `list` return types — so it is not recorded as a formal finding.
  Implementors should be aware that `frozen=True` does not make list-valued
  fields deeply immutable.
- No additional evidence of Linear-boundary violations was found. The fake
  gateway remains read-only and no `linear-client` imports appear outside the
  documented testing hook path.
