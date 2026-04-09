# Review: [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring)

> **Status**: Phase B complete
> **Plan ticket**:
> [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring)
> **Execution record**:
> [docs/execution/M5-1.md](M5-1.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/python/coding-guidelines.md](../policies/common/python/coding-guidelines.md),
> [docs/policies/terminology.md](../policies/terminology.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/design/linear-domain-coverage-audit-v1.1.0.md](../design/linear-domain-coverage-audit-v1.1.0.md)

## Review Pass 1

> **LLM**: GPT-5
> **Effort**: N/A
> **Time spent**: ~55m

### Scope

Implementation review of
[M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring)
covering the Phase A artifact at [docs/execution/M5-1.md](M5-1.md), the new
gateway/runtime code in [src/context_sync/_real_gateway.py](../../src/context_sync/_real_gateway.py),
[src/context_sync/_sync.py](../../src/context_sync/_sync.py), and
[src/context_sync/_gateway.py](../../src/context_sync/_gateway.py), the new
and updated tests in [tests/test_real_gateway.py](../../tests/test_real_gateway.py)
and [tests/test_sync.py](../../tests/test_sync.py), and the relevant
`linear-client` selector/fetch behavior in
[linear-client src/linear_client/linear.py](../../../linear-client/src/linear_client/linear.py),
[linear-client src/linear_client/domain/issue.py](../../../linear-client/src/linear_client/domain/issue.py),
and [linear-client src/linear_client/gql/services/issues.py](../../../linear-client/src/linear_client/gql/services/issues.py).

Validation run during review:
`source .venv/bin/activate && PYTHON_BIN=python3 bash scripts/validate.sh`
passed cleanly (Ruff, format check, Pyright, full pytest suite).

### Dependency-Satisfaction Verification

[M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring)
depends on
[M5-D1](../implementation-plan.md#m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110),
[M3-O1](../implementation-plan.md#m3-o1---comments-signature-input-settlement),
[M4-1](../implementation-plan.md#m4-1---cli-surface-and-command-output-contracts),
[M4.1-1](../implementation-plan.md#m4.1-1---cli-and-library-simplification),
and [M4.2-1](../implementation-plan.md#m4.2-1---quality-gate-entry-point-static-analysis-baseline-and-semantic-types).
The active plan marks all five dependencies `Done`, and the execution record at
[docs/execution/M5-1.md](M5-1.md) records them as satisfied. Verified.

### Terminology Compliance

Checked the reviewed files against
[docs/policies/terminology.md](../policies/terminology.md). No banned-term
violations found.

### Changelog Review

[src/context_sync/version.py](../../src/context_sync/version.py#L11) is
`0.1.0.dev0`, so this repository has not yet shipped a stable `>=1.0.0`
release. The changelog gate does not apply.

### Linear Boundary Check

The implementation stays within the audited helper categories from
[docs/design/linear-domain-coverage-audit-v1.1.0.md](../design/linear-domain-coverage-audit-v1.1.0.md):
the new raw queries are read-only and limited to issue supplementary data,
workspace identity, and refresh metadata. I did not find an unauthorized
`mutate(...)` call or a widened raw relation-read path. The findings below are
instead about selector semantics, fail-open error handling, and missing
coverage around the new gateway path.

### Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M5-1-R1 | Medium | Done | Selector handling | `RealLinearGateway.fetch_issue(issue_id_or_key)` promises a polymorphic UUID-or-key entry point, but it always constructs `linear.issue(id=...)` and therefore never uses `linear-client`'s dedicated key selector or its key-specific fallback path. The public `ContextSync.sync("TEAM-42")` / URL-root flow currently works only by relying on the unproven shortcut that `issue(id: "<KEY>")` behaves exactly like the supported key path. | [src/context_sync/_real_gateway.py:289](../../src/context_sync/_real_gateway.py#L289), [src/context_sync/_real_gateway.py:296](../../src/context_sync/_real_gateway.py#L296), [src/context_sync/_sync.py:479](../../src/context_sync/_sync.py#L479), [linear-client src/linear_client/linear.py:331](../../../linear-client/src/linear_client/linear.py#L331), [linear-client src/linear_client/gql/services/issues.py:149](../../../linear-client/src/linear_client/gql/services/issues.py#L149), [linear-client src/linear_client/domain/issue.py:1412](../../../linear-client/src/linear_client/domain/issue.py#L1412) | The documented add-root path is weaker than the ticket contract and bypasses the client library behavior that exists specifically to resolve issue keys robustly. If the direct `issue(id: key)` shortcut ever fails or loses parity with the key path, first-time root sync by key or URL fails even though `linear-client` has a supported selector for it. | Detect whether the caller supplied a UUID or an issue key and construct the domain object with `id=` or `key=` accordingly, or add a small resolver that tries the supported key path before treating the input as a UUID. Add regression coverage that routes `ContextSync(linear=...)` through a real-gateway-backed key and URL root sync, not only raw UUID fetches. |
| M5-1-R2 | High | Done | Traversal correctness | `get_ticket_relations()` catches every per-issue exception and turns it into `[]`. The traversal layer then interprets that empty list as "no edges" and keeps going. That means a transport/auth/GraphQL failure on one frontier issue silently truncates the reachable graph instead of raising the `SystemicRemoteError` that both the gateway protocol and the M5-1 notes require for non-viable upstream failures. | [src/context_sync/_gateway.py:391](../../src/context_sync/_gateway.py#L391), [src/context_sync/_real_gateway.py:447](../../src/context_sync/_real_gateway.py#L447), [src/context_sync/_real_gateway.py:452](../../src/context_sync/_real_gateway.py#L452), [src/context_sync/_traversal.py:217](../../src/context_sync/_traversal.py#L217), [docs/implementation-plan.md:1060](../implementation-plan.md#L1060) | A single transient upstream failure can cause `sync` or `refresh` to succeed with an incomplete graph, omitting reachable tickets and relations without surfacing any operator-visible error. That is silent snapshot corruption, not graceful degradation. | Only downgrade the explicitly accepted "not visible / not found" cases. Let auth, transport, and GraphQL failures abort the batch as `SystemicRemoteError`, and add regression tests showing that one failing `Issue.get_links()` call aborts traversal instead of being treated as an empty edge set. |
| M5-1-R3 | High | Done | Freshness correctness | The same fail-open pattern appears in `get_refresh_comment_metadata()` and `get_refresh_relation_metadata()`: any per-issue exception becomes empty metadata. `refresh()` and `diff()` then hash those empty lists into canonical signatures, so a transient upstream failure can make a ticket look fresh or produce an arbitrary diff result instead of reporting a remote error. | [src/context_sync/_gateway.py:451](../../src/context_sync/_gateway.py#L451), [src/context_sync/_gateway.py:482](../../src/context_sync/_gateway.py#L482), [src/context_sync/_real_gateway.py:562](../../src/context_sync/_real_gateway.py#L562), [src/context_sync/_real_gateway.py:568](../../src/context_sync/_real_gateway.py#L568), [src/context_sync/_real_gateway.py:654](../../src/context_sync/_real_gateway.py#L654), [src/context_sync/_real_gateway.py:669](../../src/context_sync/_real_gateway.py#L669), [src/context_sync/_sync.py:1286](../../src/context_sync/_sync.py#L1286), [src/context_sync/_diff.py:265](../../src/context_sync/_diff.py#L265), [docs/implementation-plan.md:1062](../implementation-plan.md#L1062) | Incremental maintenance can silently miss remote comment/relation changes or classify them incorrectly under ordinary transient failure. Because the run still completes and writes/returns results, operators have no signal that the freshness decision was made on fabricated empty metadata. | Preserve the current "missing issue" semantics only where the protocol explicitly allows them. For comment and relation metadata, transport/auth/GraphQL failures should abort the refresh/diff path with `SystemicRemoteError`. Add regression tests that simulate one failing metadata query and assert that `refresh()` / `diff()` fail loudly rather than hashing empty lists. |
| M5-1-R4 | Medium | Done | Coverage | The active plan requires integration tests that route `sync` / `refresh` / `remove` / `diff` through the real gateway implementation, but the checked-in coverage stops at unit tests for `RealLinearGateway` plus one readiness check that `ContextSync(linear=object())` raises. The integration suites for refresh, diff, root mutation, and end-to-end behavior still instantiate `ContextSync` through the fake gateway path. | [docs/implementation-plan.md:907](../implementation-plan.md#L907), [tests/test_real_gateway.py:280](../../tests/test_real_gateway.py#L280), [tests/test_sync.py:762](../../tests/test_sync.py#L762), [tests/test_refresh.py:39](../../tests/test_refresh.py#L39), [tests/test_diff.py:59](../../tests/test_diff.py#L59), [tests/test_add_remove_root.py:62](../../tests/test_add_remove_root.py#L62), [tests/test_e2e.py:198](../../tests/test_e2e.py#L198) | The repository currently lacks the exact coverage the ticket promised for the newly shipped runtime path. That gap is why selector-routing and fail-open gateway behavior can survive despite a green full-suite run. | Introduce a maintained fake/fixture-backed `Linear` transport double and route the public `ContextSync(linear=...)` path through `sync`, `refresh`, `remove`, and `diff`. Keep the unit tests in [tests/test_real_gateway.py](../../tests/test_real_gateway.py), but add integration tests that exercise the real gateway in composition with the existing orchestration code. |

### Residual Risks and Testing Gaps

- The new gateway module is directionally well-structured: raw GraphQL stayed
  read-only and inside the audited helper categories, placeholder-thread
  normalization for full-ticket fetches is implemented, and the runtime now
  genuinely constructs a concrete gateway instead of failing immediately with
  "No gateway available".
- Full validation passed during review:
  `source .venv/bin/activate && PYTHON_BIN=python3 bash scripts/validate.sh`
  completed with clean Ruff, format, Pyright, and pytest results.
- Forward-compatibility risk remains around relation normalization: the audit
  only blesses `blocks`, `related`, `duplicate`, and `similar`, but
  [src/context_sync/_real_gateway.py](../../src/context_sync/_real_gateway.py)
  currently maps unknown link types to `relates_to`, and
  [tests/test_real_gateway.py:57](../../tests/test_real_gateway.py#L57)
  locks that behavior in. I did not record this as a standalone finding
  because it matters only if Linear exposes another link type, but it is
  broader than the audit language in
  [docs/design/linear-domain-coverage-audit-v1.1.0.md:42](../design/linear-domain-coverage-audit-v1.1.0.md#L42).
- No live-Linear validation was run during this review. The assessment is
  based on repository artifacts, local validation, and the checked-in
  `linear-client` source.

### Overall Assessment

The core shape of the ticket is good: the repository now has a concrete
gateway module, the constructor/runtime wiring exists, and the quality gates
pass. But the implementation is not review-clean yet. The highest-risk gaps
are all fail-open correctness problems: traversal and refresh/diff can quietly
substitute empty data when upstream calls fail, and the key-based root path
still bypasses the client library's supported key selector behavior. Combined
with the missing real-gateway integration coverage, that is enough to keep
this ticket open.

---

## Review Pass 2

> **LLM**: opus-4.6
> **Effort**: N/A
> **Time spent**: ~40m

### Scope

Second independent implementation review of
[M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring),
covering all Phase A artifacts, the new gateway module at
[src/context_sync/_real_gateway.py](../../src/context_sync/_real_gateway.py),
wiring changes in
[src/context_sync/_sync.py](../../src/context_sync/_sync.py) and
[src/context_sync/_gateway.py](../../src/context_sync/_gateway.py),
the test suite at
[tests/test_real_gateway.py](../../tests/test_real_gateway.py) and
[tests/test_sync.py](../../tests/test_sync.py),
the consuming traversal code at
[src/context_sync/_traversal.py](../../src/context_sync/_traversal.py),
the consuming refresh/diff code at
[src/context_sync/_sync.py:1282–1309](../../src/context_sync/_sync.py#L1282) and
[src/context_sync/_diff.py:265–268](../../src/context_sync/_diff.py#L265),
the governing design artifact at
[docs/design/linear-domain-coverage-audit-v1.1.0.md](../design/linear-domain-coverage-audit-v1.1.0.md),
and the relevant `linear-client` source at
[linear-client src/linear_client/linear.py](../../../linear-client/src/linear_client/linear.py),
[linear-client src/linear_client/domain/issue.py](../../../linear-client/src/linear_client/domain/issue.py),
[linear-client src/linear_client/domain/attachment.py](../../../linear-client/src/linear_client/domain/attachment.py),
and [linear-client src/linear_client/gql/services/issues.py](../../../linear-client/src/linear_client/gql/services/issues.py).

Validation run during review:
`source .venv/bin/activate && PYTHON_BIN=python3 bash scripts/validate.sh`
passed cleanly (Ruff, format check, Pyright, 510 tests, 91% branch coverage).

### Dependency-Satisfaction Verification

All five dependencies
([M5-D1](../implementation-plan.md#m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110),
[M3-O1](../implementation-plan.md#m3-o1---comments-signature-input-settlement),
[M4-1](../implementation-plan.md#m4-1---cli-surface-and-command-output-contracts),
[M4.1-1](../implementation-plan.md#m4.1-1---cli-and-library-simplification),
[M4.2-1](../implementation-plan.md#m4.2-1---quality-gate-entry-point-static-analysis-baseline-and-semantic-types))
are marked `Done` in the active plan and verified in the Phase A execution
record. Verified.

### Terminology Compliance

Checked all reviewed files against
[docs/policies/terminology.md](../policies/terminology.md). No banned-term
violations found.

### Changelog Review

[src/context_sync/version.py](../../src/context_sync/version.py) is
`0.1.0.dev0` — pre-stable, changelog gate does not apply.

### Linear Boundary Check

Raw-GraphQL usage stays within the five audited helper categories from
[docs/design/linear-domain-coverage-audit-v1.1.0.md](../design/linear-domain-coverage-audit-v1.1.0.md).
No `mutate(...)` calls, no unauthorized widening of the raw boundary.
`get_ticket_relations` correctly uses domain-layer `Issue.get_links()` fan-out
per the audit.

### Agreement with Review Pass 1

I independently confirmed all four Review Pass 1 findings:

- **[M5-1-R1](M5-1-review.md) — Selector handling:** Confirmed by reading
  [linear-client src/linear_client/domain/issue.py:1412–1415](../../../linear-client/src/linear_client/domain/issue.py#L1412)
  and
  [linear-client src/linear_client/gql/services/issues.py:149–212](../../../linear-client/src/linear_client/gql/services/issues.py#L149).
  `Issue.fetch()` dispatches to `issues.get(issue_id=...)` when `id` is set
  and `issues.get(issue_key=...)` when only `key` is set. The key path uses
  a dedicated `IssueGetByKeyDirect` query with an automatic team-scoped
  fallback. Constructing `linear.issue(id=UpstreamIssueId(issue_id_or_key))`
  at [src/context_sync/_real_gateway.py:296](../../src/context_sync/_real_gateway.py#L296)
  always routes through the id path, bypassing this entire key resolution
  mechanism. Agree with severity and recommendation.

- **[M5-1-R2](M5-1-review.md) — Traversal correctness:** The bare
  `except Exception` at
  [src/context_sync/_real_gateway.py:452](../../src/context_sync/_real_gateway.py#L452)
  catches auth, transport, and GraphQL failures indiscriminately and maps them
  to empty edge lists. The traversal at
  [src/context_sync/_traversal.py:218](../../src/context_sync/_traversal.py#L218)
  consumes these as "no relations" and proceeds. The test
  [tests/test_real_gateway.py:518–529](../../tests/test_real_gateway.py#L518)
  (`test_error_returns_empty_for_issue`) locks this fail-open behavior in as
  expected. Agree with High severity — this is the single highest-risk gap.

- **[M5-1-R3](M5-1-review.md) — Freshness correctness:** Same fail-open
  pattern at
  [src/context_sync/_real_gateway.py:568](../../src/context_sync/_real_gateway.py#L568)
  and
  [src/context_sync/_real_gateway.py:669](../../src/context_sync/_real_gateway.py#L669).
  The consuming code at
  [src/context_sync/_sync.py:1303](../../src/context_sync/_sync.py#L1303)
  (`remote_comment_meta.get(uid, ([], []))`) and
  [src/context_sync/_sync.py:1309](../../src/context_sync/_sync.py#L1309)
  (`remote_relation_meta.get(uid, [])`) defaults missing entries to empty,
  then hashes them into freshness signatures. A transient per-issue failure
  thus fabricates a "no changes" signal. Agree with High severity.
  [tests/test_real_gateway.py:683–689](../../tests/test_real_gateway.py#L683)
  (`test_error_returns_empty`) similarly locks in the fail-open behavior.

- **[M5-1-R4](M5-1-review.md) — Coverage:** The active-plan test column for
  [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring)
  explicitly requires "integration tests that route `sync` / `refresh` /
  `remove` / `diff` through that real gateway implementation without a live
  workspace." No such tests exist. The existing real-gateway tests are
  unit-level mocks of `RealLinearGateway` in isolation, and existing
  integration suites in
  [tests/test_refresh.py](../../tests/test_refresh.py),
  [tests/test_diff.py](../../tests/test_diff.py),
  [tests/test_add_remove_root.py](../../tests/test_add_remove_root.py), and
  [tests/test_e2e.py](../../tests/test_e2e.py) all use the fake gateway path.
  Agree with severity and recommendation.

### New Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M5-1-R5 | Medium | Done | Concurrency | The M5-D1 audit explicitly requires the gateway to "own bounded concurrency internally" for fan-out operations. All three fan-out methods (`get_ticket_relations`, `get_refresh_comment_metadata`, `get_refresh_relation_metadata`) use unbounded `asyncio.gather(*(fetch_one(uid) for uid in unique_ids))` with no semaphore. The `ContextSync._semaphore` at construction time throttles ticket-level fetches but does not wrap gateway fan-out calls. For N tracked issues, `refresh` fires `get_refresh_comment_metadata` and `get_refresh_relation_metadata` concurrently, producing up to 2×N simultaneous GraphQL queries. | [src/context_sync/_real_gateway.py:457](../../src/context_sync/_real_gateway.py#L457), [src/context_sync/_real_gateway.py:619](../../src/context_sync/_real_gateway.py#L619), [src/context_sync/_real_gateway.py:701](../../src/context_sync/_real_gateway.py#L701), [docs/design/linear-domain-coverage-audit-v1.1.0.md § 2](../design/linear-domain-coverage-audit-v1.1.0.md), [src/context_sync/_sync.py:1286–1289](../../src/context_sync/_sync.py#L1286), [src/context_sync/_traversal.py:218](../../src/context_sync/_traversal.py#L218) | For workspaces with large tracked issue sets, unbounded fan-out risks upstream rate limiting, connection exhaustion, or API throttling. The audit requirement for bounded concurrency exists precisely to prevent this class of operational failure. | Accept a concurrency limit at gateway construction (or derive it from the caller's `concurrency_limit`) and gate each `fetch_one` coroutine through an `asyncio.Semaphore`. Add a test confirming that fan-out concurrency is bounded (for example, by instrumenting the mock to track peak concurrent in-flight calls). |
| M5-1-R6 | Low | Done | Typing | `_flatten_comments`, `_convert_attachments`, and `_normalize_links` use `list[Any]` for domain-object parameters (`# noqa: ANN401`) when the concrete `linear-client` types (`Comment`, `Attachment`, `IssueLink`) are available in `linear_client.domain` and could be imported under `TYPE_CHECKING`. The Python coding guidelines require avoiding `Any` when a concrete type is available and using `TYPE_CHECKING` imports for deferred annotation resolution. | [src/context_sync/_real_gateway.py:806](../../src/context_sync/_real_gateway.py#L806), [src/context_sync/_real_gateway.py:870](../../src/context_sync/_real_gateway.py#L870), [src/context_sync/_real_gateway.py:895–898](../../src/context_sync/_real_gateway.py#L895), [src/context_sync/_real_gateway.py:54–55](../../src/context_sync/_real_gateway.py#L54) (existing `TYPE_CHECKING` block imports only `Linear`) | The `list[Any]` annotations erase the domain-layer contract at the type level, so Pyright cannot detect misuse of these internal methods (for example passing a `list[User]` where `list[Comment]` is expected). The concrete types exist and are importable. | Add `Comment`, `Attachment`, and `IssueLink` (or their equivalents) to the existing `TYPE_CHECKING` block and replace `list[Any]` with the concrete types. Remove the corresponding `# noqa: ANN401` suppressions. |

### Residual Risks and Testing Gaps

- The gateway module's overall structure is sound: raw-GraphQL is contained to
  audited helpers, domain-layer fan-out is used where the audit requires it,
  placeholder-thread normalization is correctly implemented, runtime wiring
  genuinely creates a concrete gateway, and all quality gates pass.
- The `_normalize_link` function maps both informational types (`related`,
  `duplicate`, `similar`) and unknown types to `relates_to`. The two branches
  produce identical output. This is intentional self-documentation matching the
  audit table, but it means a new unknown link type silently becomes
  `relates_to` without any operator signal. Review Pass 1 noted this as a
  residual risk; I agree.
- The `_extract_workspace` defensive-parsing chain at
  [src/context_sync/_real_gateway.py:778–803](../../src/context_sync/_real_gateway.py#L778)
  defaults missing intermediate dicts to `{}`, which means a GraphQL response
  with `{"data": {}}` (issue field absent) falls through to
  `SystemicRemoteError("Workspace identity incomplete")` rather than
  `RootNotFoundError`. In practice the GraphQL API returns `{"data":
  {"issue": null}}` for not-found issues, so this edge case is unlikely, but
  the error classification would be wrong if it occurred.
- No live-Linear validation was run. Assessment is based on repository
  artifacts, local validation, and `linear-client` source.

### Overall Assessment

I independently confirm all four Review Pass 1 findings and add two new ones.
The implementation delivers the right structural shape — the gateway module,
runtime wiring, domain-layer fan-out, and placeholder handling are all
directionally correct and the quality gates pass. However, three classes of
issue keep the ticket from being review-clean:

1. **Fail-open correctness** (M5-1-R2, M5-1-R3): The most critical gap. Bare
   `except Exception` in traversal and refresh fan-out methods silently
   substitutes empty data for upstream failures, producing corrupt snapshots
   and fabricated freshness signals without operator visibility. The existing
   tests lock in this behavior as expected.

2. **Unbounded concurrency** (M5-1-R5): The M5-D1 audit explicitly requires
   bounded concurrency for gateway fan-out, but the implementation fires
   unbounded `asyncio.gather` calls. This is an operational risk for any
   non-trivial workspace.

3. **Selector bypass and missing integration coverage** (M5-1-R1, M5-1-R4):
   The key-based root path bypasses `linear-client`'s supported key
   resolution, and the integration test surface promised in the ticket's test
   column does not exist.

Combined, these issues mean the implementation would ship a runtime that can
silently corrupt snapshots under transient failure, overload the upstream API
under normal load, and bypass the client library's key resolution — with no
integration-level test coverage to catch any of it. The ticket should remain
open.

---

## Ticket Owner Response

> **LLM**: opus-4.6
> **Effort**: N/A
> **Time spent**: ~1h 20m

| ID | Verdict | Rationale |
| --- | --- | --- |
| M5-1-R1 | Fix now | Correct. `issue_id_or_key` should use `key=` when the input matches the issue-key pattern. Implementing a UUID-vs-key heuristic and routing to the correct `linear.issue(id=...)` or `linear.issue(key=...)` constructor. Adding regression test. |
| M5-1-R2 | Fix now | Correct. Bare `except Exception` in `get_ticket_relations` silently swallows systemic failures. Will catch only `LinearNotFoundError` for not-visible issues and let transport/auth/GraphQL errors propagate as `SystemicRemoteError`. Updating the test that locked in fail-open behavior. |
| M5-1-R3 | Fix now | Correct. Same pattern as R2. Will apply the same not-found-only catch in `get_refresh_comment_metadata` and `get_refresh_relation_metadata`, letting systemic failures abort the batch. Updating the test that locked in fail-open behavior. |
| M5-1-R4 | Fix now | Correct. Adding integration tests that construct `ContextSync(linear=...)` with a maintained mock `Linear` transport double and exercise `sync`, `refresh`, `remove`, and `diff` through the real gateway path. |
| M5-1-R5 | Fix now | Correct. Adding an `asyncio.Semaphore` to `RealLinearGateway` (accepted at construction time, defaulting to `DEFAULT_CONCURRENCY_LIMIT`) and gating every `fetch_one` coroutine in fan-out methods through it. |
| M5-1-R6 | Fix now | Correct. Adding `Comment`, `Attachment`, and `IssueLink` to the `TYPE_CHECKING` block and replacing `list[Any]` with concrete types. |
