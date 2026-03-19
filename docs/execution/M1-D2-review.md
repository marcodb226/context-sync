# Review: [M1-D2](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary)

> **Status**: Phase B complete
> **Plan ticket**:
> [M1-D2](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary)
> **Execution record**:
> [docs/execution/M1-D2.md](M1-D2.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/design-review.md](../policies/common/reviews/design-review.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/adr.md](../adr.md#31-foundation),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#11-linear-dependency-boundary),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#62-refresh-flow),
> [docs/design/linear-client.md](../design/linear-client.md),
> [docs/design/linear-domain-coverage-audit.md](../design/linear-domain-coverage-audit.md),
> [docs/execution/M1-D3.md](M1-D3.md)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M1-D2-R1 | Medium | Todo | Refresh Contract | The plan made [M1-D2](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) responsible for either confirming that comment-level `updated_at` advances on comment edits or, if it could not, defining the fallback remote input or follow-on design work needed before [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery). The delivered audit records the uncertainty but still punts the resolution to later implementation work instead of settling the fallback path now. | [docs/implementation-plan.md:242](../implementation-plan.md), [docs/design/linear-domain-coverage-audit.md:87](../design/linear-domain-coverage-audit.md), [docs/execution/M1-D2.md:89](M1-D2.md), [.venv/lib/python3.13/site-packages/linear_client/domain/repos/comment_repo.py:120](../../.venv/lib/python3.13/site-packages/linear_client/domain/repos/comment_repo.py) | If comment `updatedAt` does not exist in the needed raw GraphQL shape or does not advance on edit, [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery) still lacks an authoritative repository-level fallback for `comments_signature`. That reopens the same correctness risk that [M1-D3](../implementation-plan.md#m1-d3---refresh-composite-freshness-contract-amendment) deliberately tried to contain and leaves the downstream implementation to invent contract details ad hoc. | Amend the audit so it either records the accepted fallback remote input for `comments_signature` now or names the required follow-on design/probe work as an explicit prerequisite before [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery) starts. |
| M1-D2-R2 | Medium | Todo | Adapter Boundary | The audit omits workspace-identity lookup from the required-operation matrix and treats it as a hypothetical later need, even though the active ADR and top-level design already require the manifest to store stable workspace identity and require `sync`/`add` to verify fetched tickets against that workspace. | [docs/design/linear-domain-coverage-audit.md:94](../design/linear-domain-coverage-audit.md), [docs/execution/M1-D2.md:125](M1-D2.md), [docs/design/0-top-level-design.md:149](../design/0-top-level-design.md), [docs/design/0-top-level-design.md:316](../design/0-top-level-design.md), [docs/design/0-top-level-design.md:524](../design/0-top-level-design.md), [docs/adr.md:196](../adr.md), [docs/adr.md:203](../adr.md), [docs/adr.md:305](../adr.md) | Later implementation tickets can still discover the workspace-validation read path ad hoc, which is exactly the boundary drift [M1-D2](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) was supposed to prevent. In the worst case, a later implementation could weaken the single-workspace contract to a team-level proxy because the required Linear read was never explicitly audited. | Add workspace-identity validation to the coverage matrix as a required v1 read operation and explicitly record whether it is satisfied by the audited domain layer or requires its own narrow adapter/helper path for stable workspace ID plus slug lookup. |

## Reviewer Notes

- The core package-surface audit is otherwise solid. Review-time inspection of
  the installed `linear-client` source confirms that comment and attachment
  reads already drop to package-internal raw GraphQL while relation reads are
  still mutation-only in the typed surfaces. Supporting context:
  [docs/design/linear-domain-coverage-audit.md:27](../design/linear-domain-coverage-audit.md),
  [docs/design/linear-domain-coverage-audit.md:30](../design/linear-domain-coverage-audit.md),
  [.venv/lib/python3.13/site-packages/linear_client/domain/repos/comment_repo.py:16](../../.venv/lib/python3.13/site-packages/linear_client/domain/repos/comment_repo.py),
  [.venv/lib/python3.13/site-packages/linear_client/domain/repos/attachment_repo.py:16](../../.venv/lib/python3.13/site-packages/linear_client/domain/repos/attachment_repo.py),
  [.venv/lib/python3.13/site-packages/linear_client/gql/services/issues.py:459](../../.venv/lib/python3.13/site-packages/linear_client/gql/services/issues.py).
- The ticket also keeps faith with the repository-wide boundary rule from
  [docs/adr.md](../adr.md#31-foundation): domain layer by default, with any
  `linear.gql.*` escape hatch constrained to one narrow adapter module rather
  than scattered through traversal or refresh orchestration. Evidence:
  [docs/design/linear-domain-coverage-audit.md:37](../design/linear-domain-coverage-audit.md),
  [docs/execution/M1-D2.md:72](M1-D2.md),
  [docs/adr.md:260](../adr.md).

## Residual Risks and Testing Gaps

- Even after the findings above are addressed, the accepted metadata-only
  comment freshness path still carries the cost risk already documented by the
  ticket. The design correctly keeps that risk visible instead of weakening the
  default v1 refresh contract by implication. Evidence:
  [docs/design/linear-domain-coverage-audit.md:80](../design/linear-domain-coverage-audit.md),
  [docs/implementation-plan.md:234](../implementation-plan.md).
- This review verified the audited package surface against the installed
  `.venv` source, but it did not rerun live Linear probes. Exact raw-GraphQL
  helper feasibility for the missing metadata shapes therefore remains a later
  implementation-time verification step rather than something this Phase B
  review re-proved.
- This was a docs-only design ticket, so no repository-wide lint, format, or
  test commands were rerun during review. Validation consisted of
  cross-document consistency checks plus direct inspection of the installed
  `linear-client` package surface.

---

## Supplementary Independent Review

> **Reviewer session**: independent second-pass Phase B review
> **Date**: 2026-03-19
> **Review scope**: strictest unbiased re-review of all
> [M1-D2](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary)
> deliverables, covering the coverage matrix, boundary decision, recorded
> missing capabilities, risk section, cross-links, and the execution record,
> verified independently against the installed `linear-client` 1.0.0 package
> source and the governing plan, ADR, and top-level design

### Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M1-D2-R3 | Medium | Todo | Adapter Boundary | The four adapter helpers defined by the boundary decision all accept `issue_ids` and are expected to read across the tracked reachable set, which can be arbitrarily large. The installed package exposes both `linear.gql.query()` (single-response, retried reads) and `linear.gql.paginate_connection()` (Relay-cursor pagination with automatic page aggregation, configurable `page_size` and `limit`), with materially different retry, error-handling, and data-aggregation semantics. The boundary decision records helper names and parameter shapes but does not address whether the helpers should use `query()` or `paginate_connection()`, whether they are expected to handle pagination internally, or whether single-query truncation is an accepted risk for small tracked sets. The implementation plan explicitly asks for the "expected `linear.gql.*` fallback shape" to be recorded inside the boundary so later tickets do not rediscover it ad hoc. | [docs/design/linear-domain-coverage-audit.md:46](../design/linear-domain-coverage-audit.md) (boundary specification — no pagination mention), [docs/design/linear-domain-coverage-audit.md:58](../design/linear-domain-coverage-audit.md) (helpers should be called instead of `linear.gql.query(...)` directly — implies `query` is the raw entry point, silent on `paginate_connection`), [.venv/lib/python3.13/site-packages/linear_client/gql/facade.py:150](../../.venv/lib/python3.13/site-packages/linear_client/gql/facade.py) (`paginate_connection` — structurally different from `query`), [docs/design/0-top-level-design.md:384](../design/0-top-level-design.md) (batch-query across tracked reachable set), [docs/implementation-plan.md:231](../implementation-plan.md) (record the expected fallback shape) | Without recording pagination as a boundary concern, the adapter helpers may be implemented inconsistently — some using raw `query()` with manual cursor handling, others using `paginate_connection()` — producing exactly the kind of ad-hoc raw-GraphQL usage patterns the boundary was designed to prevent. A naive single-query implementation that works for small tracked sets may also silently truncate results for larger ones if Linear enforces connection-level node limits. | Record whether the batch adapter helpers are expected to use `paginate_connection` (or an equivalent exhaustive-pagination strategy) and whether they should handle pagination internally or expose it to callers. This is a brief addition to the boundary decision, not a new design artifact. |
| M1-D2-R4 | Low | Todo | Adapter Boundary | The audit's risk section frames workspace-identity as a conditional future need ("if later tickets need an authoritative fetched-workspace identity"), but the governing ADR and top-level design have already made workspace-identity validation mandatory: the manifest must store stable workspace ID and slug, `sync` must verify that the fetched root ticket belongs to the configured workspace, and the `context_dir` is scoped to exactly one workspace. Beyond the coverage-matrix omission already identified by [M1-D2-R2](#findings), the risk section actively understates the gap's urgency by treating a required v1 capability as hypothetical. Independent package inspection also confirms the gap is absolute rather than ambiguous: `Linear.me()` returns `viewer { id name email }` with no organization or workspace data, the team-resolution query returns `teams(filter: ...) { nodes { id key name } }` with no workspace parent, and no other audited domain object, repository method, or GraphQL service returns workspace-level identity. | [docs/design/linear-domain-coverage-audit.md:94](../design/linear-domain-coverage-audit.md) (risk item framed as conditional), [docs/design/0-top-level-design.md:152](../design/0-top-level-design.md) (manifest stores stable workspace ID and slug), [docs/design/0-top-level-design.md:317](../design/0-top-level-design.md) (sync verifies workspace), [docs/adr.md:196](../adr.md) (manifest stores workspace identity), [docs/adr.md:305](../adr.md) (single-workspace boundary), [.venv/lib/python3.13/site-packages/linear_client/linear.py:25](../../.venv/lib/python3.13/site-packages/linear_client/linear.py) (ME_QUERY — no workspace), [.venv/lib/python3.13/site-packages/linear_client/gql/services/issues.py:459](../../.venv/lib/python3.13/site-packages/linear_client/gql/services/issues.py) (_resolve_team_id — no workspace parent) | The risk section is a primary guidance artifact for later implementation. Framing a required v1 capability as conditional encourages implementers to defer planning for it further rather than treating it as a known adapter-boundary gap that must be solved by implementation time. This compounds the [M1-D2-R2](#findings) matrix omission: the matrix doesn't list the operation, and the risk section implies it might not even be needed. | Rewrite risk item 3 to reflect that workspace-identity validation is a required v1 capability, not a conditional future need, and record the confirmed absolute absence of any workspace-identity read path in the audited package surface. |
| M1-D2-R5 | Low | Todo | Coverage Matrix | The coverage matrix includes "Team-scoped discovery" as a covered v1 operation, but no active v1 flow in the implementation plan or top-level design requires team-scoped issue search. Root resolution uses single-ticket fetch by ID or key. Traversal follows relation edges. Refresh batch-reads by tracked ID set. `add` resolves by ticket ID/key. Including a non-required operation in the same matrix as genuinely required ones inflates apparent domain-layer coverage without serving the boundary-stabilization purpose of the audit. | [docs/design/linear-domain-coverage-audit.md:26](../design/linear-domain-coverage-audit.md) (team-scoped discovery row), [docs/design/0-top-level-design.md:306](../design/0-top-level-design.md) (sync flow — no team search), [docs/design/0-top-level-design.md:363](../design/0-top-level-design.md) (refresh flow — no team search), [docs/implementation-plan.md:225](../implementation-plan.md) (v1 operations — no team search mentioned) | A later implementer reading the matrix may treat team-scoped search as part of the approved v1 adapter surface and build flows around it. If those flows produce results inconsistent with the tracked-id-based approach (for example, discovering tickets by filter rather than by explicit root-add), the boundary would be effectively widened by a non-required "covered" operation that was never design-reviewed for that purpose. | Either annotate the team-scoped discovery row to indicate it is not required by any v1 flow and is recorded only for surface completeness, or remove it from the required-operation matrix and mention it in a separate informational note. |

### Reviewer Notes

- The first review's findings [M1-D2-R1](#findings) and [M1-D2-R2](#findings)
  remain valid. [M1-D2-R4](#supplementary-independent-review) above reinforces
  [M1-D2-R2](#findings) from the risk-characterization side: the matrix
  omission and the understated risk section are two facets of the same
  workspace-identity gap.
- The most material new finding is [M1-D2-R3](#supplementary-independent-review).
  The boundary decision defines helper names and parameters but stops short of
  recording the pagination strategy, even though the implementation plan
  explicitly asks for the "expected `linear.gql.*` fallback shape." The
  installed package's `paginate_connection()` helper is a structurally
  different entry point from `query()` — it handles cursor advancement, page
  aggregation, and limit enforcement — and the adapter helpers' batch nature
  means pagination is a first-class design concern rather than an
  implementation detail. Additionally, the installed `gql()` raw helper
  executes with mutation semantics (`is_mutation=True, allow_retry=False`),
  which means an adapter helper that accidentally uses `gql()` instead of
  `query()` would lose retry protection on a read path. The boundary
  specification should at minimum note that adapter helpers are read-only and
  should use `query()` or `paginate_connection()`, never `gql()` or
  `mutate()`.
- The core audit conclusions are otherwise sound and independently verified.
  Review-time inspection of the installed `linear-client` source confirms:
  comment bodies are fetched via package-internal raw GraphQL selecting only
  `{id body createdAt user{id name}}` with no `updatedAt`; attachment reads
  select `{id title url createdAt}` plus creator; issue fetches include
  `updatedAt`; `IssueLink` has only a `link()` mutation with no read/list
  path; and the `IssueLinkModel` typed model defines `id`, `link_type`,
  `issue_id`, and `related_issue_id` fields that anticipate a relation-query
  response shape even though no such query exists in the package.
- The boundary decision is faithful to
  [docs/adr.md](../adr.md#31-foundation): domain layer by default, raw
  `linear.gql.*` only behind a narrow adapter module. The four helper
  categories are well-chosen for the v1 scope.

### Residual Risks and Testing Gaps

- The comment `updatedAt` validation gap identified by [M1-D2-R1](#findings)
  and the workspace-identity gap identified by [M1-D2-R2](#findings) and
  [M1-D2-R4](#supplementary-independent-review) both remain open and must be
  resolved before their downstream implementation tickets begin. These are the
  highest-priority open items from this review.
- The adapter helpers' interaction with Linear API rate limits is not addressed
  by the audit. The ADR delegates rate-limit behavior to `linear-client`, but
  the batch helpers will issue queries that are structurally different from the
  domain-layer single-ticket calls the package was designed around. Whether
  `linear-client`'s existing retry and backoff behavior extends correctly to
  raw `query()` and `paginate_connection()` calls is an implementation-time
  verification concern.
- This review verified the audited package surface against the installed
  `.venv` source but did not rerun live Linear probes. The confirmed absolute
  absence of workspace-identity data in the installed package does not prove
  that the Linear GraphQL schema lacks a workspace/organization query — only
  that no packaged path exposes it. A raw-GraphQL helper may still be feasible.
- This was a docs-only design ticket, so no repository-wide lint, format, or
  test commands were rerun during this supplementary review. Validation
  consisted of cross-document consistency checks across the governing plan,
  ADR, top-level design, execution record, coverage-matrix artifact, installed
  package source, and the prior Phase B review.
