# M5-D1 Review

## Review Pass 1

> **LLM**: Claude Opus 4.6 (1M context)
> **Effort**: N/A
> **Time spent**: ~40m

### Scope

Design review of [M5-D1](../implementation-plan.md#m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110)
(Linear domain-coverage audit and adapter boundary -- v1.1.0). The
primary deliverable is
[docs/design/linear-domain-coverage-audit-v1.1.0.md](../design/linear-domain-coverage-audit-v1.1.0.md);
the secondary deliverable is the compatibility index at
[docs/design/linear-domain-coverage-audit.md](../design/linear-domain-coverage-audit.md).
The execution artifact is [docs/execution/M5-D1.md](M5-D1.md).

Review checklist used:
[docs/policies/common/reviews/design-review.md](../policies/common/reviews/design-review.md).

### Dependency-Satisfaction Verification

[M5-D1](../implementation-plan.md#m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110)
lists `None` for dependencies. The execution artifact confirms no
dependencies needed satisfaction. Verified.

### Factual-Accuracy Verification

The review independently inspected the installed `linear-client` v1.1.0
source files that the audit cites. Key claims verified:

- **Per-issue comment metadata**: `Comment.updated_at`, `.resolved_at`,
  `.parent`, `.children` are confirmed present in
  [linear-client src/linear_client/domain/comment.py](../../../linear-client/src/linear_client/domain/comment.py).
- **Per-issue relation reads**: `Issue.get_links()` confirmed at
  [linear-client src/linear_client/domain/issue.py:894](../../../linear-client/src/linear_client/domain/issue.py)
  returning typed `IssueLink` objects with `peek_link_type()` returning
  `IssueLinkType`.
- **Label gap**: `Issue.get_labels()` at
  [linear-client src/linear_client/domain/issue.py:728](../../../linear-client/src/linear_client/domain/issue.py)
  explicitly raises `LinearConfigurationError` stating labels are not
  available from the current issue GraphQL payload. Gap confirmed.
- **Workspace-identity gap**: `Linear.me()` at
  [linear-client src/linear_client/linear.py:273](../../../linear-client/src/linear_client/linear.py)
  performs a `ViewerMe` query returning only `viewer { id name email }`.
  No workspace UUID or slug in the response. Gap confirmed.
- **Type vocabulary**: All 18 `NewType` aliases in
  [linear-client src/linear_client/types.py](../../../linear-client/src/linear_client/types.py)
  verified. The five exact semantic duplicates (`IssueId`, `IssueKey`,
  `CommentId`, `AttachmentId`, `IsoTimestamp`/`Timestamp`) and the
  additional upstream aliases (`UserId`, `TeamId`, `TeamKey`, `StatusId`,
  `LabelId`, `IssueLinkId`, `IssueLinkType`, `AssetUrl`, `StatusCategory`)
  match the audit's type-mapping analysis.
- **Batch-read gaps**: No batch-by-issue-set read surface found for issue
  metadata, comment metadata, or relation metadata. Gaps confirmed.

### Terminology Compliance

Checked all new text in the audit artifact and execution file against
[docs/policies/terminology.md](../policies/terminology.md). No occurrences
of banned terms.

### Design-Artifact Boundary Check

The audit artifact is self-contained for implementation purposes. It
contains no review findings, execution logs, or process-state material.
The sole reference to a plan ticket (`M5-D1` in the status header) is
clearly non-normative historical traceability. An implementor can
understand the current boundary contract from the audit plus the ADR and
top-level design without reading execution artifacts.

### Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M5-D1-R1 | Medium | Todo | Design-code consistency | The audit moves `get_ticket_relations` from raw-GQL to domain-layer fan-out, but does not acknowledge that the existing `LinearGateway` protocol docstring and module docstring already reference the v1.1.0 audit as the governing document while contradicting its boundary decision. The class docstring describes `get_ticket_relations` as "raw-GraphQL batched relation read" and the `get_refresh_relation_metadata` docstring says the implementation "may share the underlying query with `get_ticket_relations`" -- both statements are invalidated by the audit's boundary change. | [src/context_sync/_gateway.py:7-8](../../src/context_sync/_gateway.py) -- module docstring references v1.1.0 audit; [src/context_sync/_gateway.py:320-321](../../src/context_sync/_gateway.py) -- protocol docstring says "raw-GraphQL batched relation read"; [src/context_sync/_gateway.py:487-488](../../src/context_sync/_gateway.py) -- refresh-relation docstring says "may share the underlying query with `get_ticket_relations`"; [docs/design/linear-domain-coverage-audit-v1.1.0.md:21](../design/linear-domain-coverage-audit-v1.1.0.md) -- `get_ticket_relations` approved path is domain-layer fan-out | An [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring) implementor who reads the gateway module first sees "raw-GraphQL" in the protocol docstring for a method the audit says should be domain-layer. The module docstring claims the audit is the authority, but the protocol description contradicts it. This creates a silent inconsistency where the code and its own cited authority disagree, and the audit does not flag the discrepancy for cleanup. | Add a brief note to the audit's boundary decision (section 2) or risks section (section 6) acknowledging that the existing `LinearGateway` protocol docstring at [src/context_sync/_gateway.py:314-325](../../src/context_sync/_gateway.py) describes `get_ticket_relations` as raw-GQL and that [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring) must update both the class docstring and the `get_refresh_relation_metadata` docstring to reflect the domain-layer fan-out path and the removal of the query-sharing option. |
| M5-D1-R2 | Low | Todo | Internal consistency | The audit uses `get_issue_workspace_identity(issue_id)` in section 1 (coverage matrix) and section 2 (boundary decision) but `get_workspace_identity(issue_id)` in section 3 (type-mapping table). The existing gateway protocol method is `get_workspace_identity`. The audit does not explain whether these refer to different things (internal raw helper vs. protocol method) or whether the naming difference is accidental. | [docs/design/linear-domain-coverage-audit-v1.1.0.md:16](../design/linear-domain-coverage-audit-v1.1.0.md) -- `get_issue_workspace_identity(issue_id)` in coverage matrix; [docs/design/linear-domain-coverage-audit-v1.1.0.md:38](../design/linear-domain-coverage-audit-v1.1.0.md) -- `get_issue_workspace_identity(issue_id)` in raw helper list; [docs/design/linear-domain-coverage-audit-v1.1.0.md:55](../design/linear-domain-coverage-audit-v1.1.0.md) -- `get_workspace_identity(issue_id)` in type-mapping table; [src/context_sync/_gateway.py:364](../../src/context_sync/_gateway.py) -- protocol method named `get_workspace_identity` | The type-mapping table is supposed to be the authoritative reference [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring) uses when implementing. The naming discrepancy introduces ambiguity about whether the raw helpers in section 2 are internal implementation functions distinct from the protocol methods in section 3, or whether the audit inconsistently names the same thing. | Align the naming within the audit. If sections 1-2 describe internal raw helper functions (implementation-private) while section 3 describes protocol-level boundary positions (public interface), add a clarifying sentence. If they are the same, use one consistent name throughout. |
| M5-D1-R3 | Medium | Todo | Traceability | The [M5-D1 ticket notes](../implementation-plan.md#m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110) require the audit to "verify whether the per-issue domain-layer comment surface in v1.1.0 changes the integration path relative to the [M3-O1](../implementation-plan.md#m3-o1---comments-signature-input-settlement) raw-adapter-only conclusion." The execution file work log records this verification ("does not preserve the old raw-only conclusion for single-ticket fetches"). However, the audit artifact itself -- the lasting design document -- never mentions [M3-O1](../implementation-plan.md#m3-o1---comments-signature-input-settlement) by name and never explicitly states how its per-issue comment boundary relates to the M3-O1 conclusion. The [M3-O1 execution artifact](M3-O1.md) still contains the now-factually-incorrect assertion that per-issue comment metadata is "not available through the `linear-client` domain layer." | [docs/execution/M5-D1.md:44](M5-D1.md) -- work log records the verification in the execution file; [docs/design/linear-domain-coverage-audit-v1.1.0.md:19](../design/linear-domain-coverage-audit-v1.1.0.md) -- audit says comments are domain-layer but does not reference [M3-O1](../implementation-plan.md#m3-o1---comments-signature-input-settlement); [docs/execution/M3-O1.md:145-146](M3-O1.md) -- M3-O1 asserts domain-layer comment metadata is unavailable | An [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring) implementor reading the audit alone knows that per-issue comments are domain-layer. But a reader cross-referencing earlier artifacts could be confused by the contradicting [M3-O1](../implementation-plan.md#m3-o1---comments-signature-input-settlement) assertion. The reconciliation exists only in the execution file, not in the design deliverable. Per execution-model section 4.3 rule 3, design documents should be self-contained for implementors -- the M3-O1 reconciliation is the kind of clarification an implementor benefits from seeing in the audit rather than discovering by reading upstream execution artifacts. | Add a brief non-normative note to the audit's comment-coverage section (section 1, "Comment rendering" or "Refresh comment cursor" row) or to section 5 (recorded missing capabilities) stating that v1.1.0 domain-layer comment reads supersede the [M3-O1](../implementation-plan.md#m3-o1---comments-signature-input-settlement) raw-adapter-only path for per-issue fetches, while the batched refresh path retains the raw helper. |
| M5-D1-R4 | Low | Todo | Completeness | The audit covers read operations and data types comprehensively but omits any mention of the `LinearNotFoundError` exception that `linear-client` v1.1.0 provides for entity-not-found handling. The [M5-1 ticket notes](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring) require adopting `LinearNotFoundError`, but the audit -- as the authoritative adapter boundary reference -- does not discuss how upstream exceptions map to the gateway protocol's error contract (`RootNotFoundError`, `SystemicRemoteError`). | [linear-client src/linear_client/errors.py:28](../../../linear-client/src/linear_client/errors.py) -- `LinearNotFoundError` defined; [linear-client src/linear_client/__init__.py:118](../../../linear-client/src/linear_client/__init__.py) -- exported in public API; [src/context_sync/_gateway.py:358-361](../../src/context_sync/_gateway.py) -- protocol defines `RootNotFoundError` for not-found cases | The gap is mitigated by the [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring) ticket notes which mention `LinearNotFoundError` directly. The audit's omission does not block implementation but makes the boundary definition incomplete in its error dimension -- the audit defines exactly which read operations cross the boundary and what types they use, but not what exceptions the domain layer can throw. | Consider adding a brief note to the audit's boundary decision (section 2) or risks section (section 6) that `linear-client` v1.1.0 exports `LinearNotFoundError` for entity-not-found conditions and that the real gateway should catch it and map it to the appropriate gateway-protocol exception. |

### Residual Risks and Testing Gaps

- The factual claims in the audit about the installed v1.1.0 surface are
  accurate as of this review. If `linear-client` is upgraded past v1.1.0
  before [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring)
  executes, the coverage matrix and missing-capability list would need
  re-verification.
- The domain-layer fan-out path for `get_ticket_relations` is architecturally
  sound but has no performance characterization. If the tracked reachable set
  grows large, the per-issue `Issue.get_links()` fan-out could produce
  materially more upstream round trips than a batched raw alternative. The
  audit's section 6 correctly defers this to future measurement, but
  [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring)
  should include at least a rough performance observation for the fan-out path.
- The root-thread projection flattening described in the audit's coverage
  matrix (section 1, "Comment rendering" row) is the key novel mapping that
  [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring)
  must implement. The mapping from `Comment.children` recursive tree to flat
  `CommentData` list plus `ThreadData` list is straightforward but should be
  validated with multi-level thread fixtures in M5-1 tests.

### Overall Assessment

The audit is a strong deliverable. The coverage matrix is factually accurate
against the installed v1.1.0 source. The boundary decision is sound -- it
correctly narrows the raw-GQL escape hatch by moving per-issue comments and
relations to the domain layer while preserving raw helpers only where the
packaged surface has genuine gaps. The type-mapping table gives
[M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring)
a specific, implementable reference for every boundary position. The
non-adoption decisions for optional v1.1.0 enrichments (team, delegate,
status category, actor type) are well-justified by the current v1 snapshot
contract.

The four findings are about documentation completeness and traceability, not
about incorrect boundary decisions. The two medium findings
([M5-D1-R1](#m5-d1-r1), [M5-D1-R3](#m5-d1-r3)) both concern cases where the
audit changes a boundary assumption without acknowledging the impact on
existing artifacts that
[M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring)
will need to reconcile.

## Review Pass 2

> **LLM**: GPT-5 (Codex)
> **Effort**: N/A
> **Time spent**: ~45m

### Scope

Additional strict Phase B design review of
[M5-D1](../implementation-plan.md#m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110),
focused on whether the approved v1.1.0 domain-layer paths are fully specified
enough for
[M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring)
to implement traversal, relation rendering, and comment rendering without
inventing new boundary rules. Primary artifact reviewed:
[docs/design/linear-domain-coverage-audit-v1.1.0.md](../design/linear-domain-coverage-audit-v1.1.0.md).
Supporting artifacts reviewed:
[docs/execution/M5-D1.md](M5-D1.md),
[src/context_sync/_gateway.py](../../src/context_sync/_gateway.py),
[src/context_sync/_traversal.py](../../src/context_sync/_traversal.py), and
the inspected `linear-client` v1.1.0 source under the sibling workspace.

Review checklists used:
[docs/policies/common/reviews/design-review.md](../policies/common/reviews/design-review.md)
and
[docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md).

### Dependency-Satisfaction Verification

[M5-D1](../implementation-plan.md#m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110)
still lists `None` for dependencies, and
[docs/execution/M5-D1.md:38-40](M5-D1.md) records that Phase A verified the
active-plan state, dependency status, and installed `linear-client` version.
Verified.

### Terminology Compliance

Re-opened [docs/policies/terminology.md](../policies/terminology.md) during
this pass. No banned-term violations were found in the reviewed artifact.

### Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M5-D1-R5 | High | Todo | Boundary completeness | The audit approves domain-layer fan-out over `Issue.get_links()` for `get_ticket_relations(issue_ids)`, but it never records that the upstream relation read is itself capped at 250 forward links and 250 inverse links per issue. The audit therefore treats the domain-layer path as the authoritative single-issue relation source without addressing whether that built-in cap is acceptable for context-sync's traversal and relation-rendering contract. | [docs/design/linear-domain-coverage-audit-v1.1.0.md:21](../design/linear-domain-coverage-audit-v1.1.0.md) and [docs/design/linear-domain-coverage-audit-v1.1.0.md:33](../design/linear-domain-coverage-audit-v1.1.0.md) approve domain-layer fan-out; [linear-client src/linear_client/domain/issue.py:896-901](../../../linear-client/src/linear_client/domain/issue.py) says `Issue.get_links()` aggregates both directions only up to a safety cap of 250; [linear-client src/linear_client/gql/services/issues.py:972-975](../../../linear-client/src/linear_client/gql/services/issues.py) and [linear-client src/linear_client/gql/services/issues.py:1000-1013](../../../linear-client/src/linear_client/gql/services/issues.py) implement `MAX_LINK_FETCH` per direction; [src/context_sync/_traversal.py:262-268](../../src/context_sync/_traversal.py) treats `RelationData.dimension` edges as the traversal input | A heavily connected ticket can silently lose traversal edges and rendered frontmatter relations if [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring) implements the audited domain-layer path literally. That changes reachability and snapshot completeness, not just performance. | Amend the audit to acknowledge the upstream per-direction cap explicitly and decide the contract: either accept that cap for v1 with rationale, require a raw fallback once the cap is encountered, or record a follow-on amendment/probe as a prerequisite before [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring) treats `Issue.get_links()` as the full relation source. |
| M5-D1-R6 | Medium | Todo | Boundary normalization | The audit moves per-issue relation reads to the domain layer but does not define how perspective-neutral `IssueLink` objects map into context-sync's directional traversal dimensions. Upstream returns both forward and inverse relations and exposes raw link-type strings such as `"blocks"` and `"related"`, while context-sync traversal filters on local dimension names such as `blocks`, `is_blocked_by`, `parent`, `child`, and `relates_to`. The design artifact never states the normalization rule from upstream `(from_issue, to_issue, link_type)` into `RelationData.dimension`. | [docs/design/linear-domain-coverage-audit-v1.1.0.md:21](../design/linear-domain-coverage-audit-v1.1.0.md) and [docs/design/linear-domain-coverage-audit-v1.1.0.md:33](../design/linear-domain-coverage-audit-v1.1.0.md) move `get_ticket_relations(issue_ids)` to domain-layer fan-out; [linear-client src/linear_client/domain/issue.py:896-901](../../../linear-client/src/linear_client/domain/issue.py) says `Issue.get_links()` merges forward and inverse relations; [linear-client src/linear_client/domain/issue_link.py:27-29](../../../linear-client/src/linear_client/domain/issue_link.py) describes `IssueLink` as perspective-neutral `from_issue` / `to_issue`; [linear-client src/linear_client/gql/models.py:168](../../../linear-client/src/linear_client/gql/models.py) documents upstream link types such as `"blocks"` and `"related"`; [docs/adr.md:30-39](../adr.md) and [src/context_sync/_traversal.py:267-268](../../src/context_sync/_traversal.py) show the local dimension vocabulary that the gateway must emit | Without an explicit normalization rule, [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring) has to invent how inverse blockers become `is_blocked_by`, how informational upstream values become `relates_to`, and how parent/child direction is derived. Different reasonable implementations would produce different reachable graphs and different persisted relation frontmatter. | Add a short normalization table or prose rule to the audit covering each supported relation shape: how direction is determined from `from_issue` / `to_issue`, which upstream link-type values map to which local dimensions, and which raw value should be preserved in `RelationData.relation_type`. |
| M5-D1-R7 | Medium | Todo | Comment-boundary completeness | The audit says the v1.1.0 root-thread projection can be flattened into `CommentData` plus `ThreadData`, but it omits the upstream placeholder-parent case. `Issue.get_comments()` may return synthetic placeholder root comments when a reply references a parent absent from the hydrated set, and `Comment.is_placeholder()` is the documented discriminator. The audit never states whether the gateway should surface those placeholders, drop them, or normalize them into some other thread representation. | [docs/design/linear-domain-coverage-audit-v1.1.0.md:19](../design/linear-domain-coverage-audit-v1.1.0.md) says the gateway must flatten the root-thread projection; [docs/planning/change-requests/CR-26.04.07.md:55](../planning/change-requests/CR-26.04.07.md) explicitly calls out `Comment.is_placeholder()` as part of the new domain-layer surface; [linear-client src/linear_client/domain/repos/comment_repo.py:31-47](../../../linear-client/src/linear_client/domain/repos/comment_repo.py) says `list_for_issue()` returns root comments with synthetic placeholder parents appended when needed; [linear-client src/linear_client/domain/comment.py:642-649](../../../linear-client/src/linear_client/domain/comment.py) states placeholders have no non-id fields and must be detected via `is_placeholder()` | If [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring) encounters this case, it has no design-level guidance for whether an empty placeholder becomes a rendered thread root, is omitted from the bundle, or is replaced with a local synthetic marker. That can produce malformed comment rendering or inconsistent alignment between full-fetch bundles and refresh metadata. | Extend the audit's comment-boundary notes with an explicit rule for `Comment.is_placeholder()` handling during flattening. The rule should say whether placeholder parents are excluded from rendered bundles, surfaced as synthetic thread stubs, or handled some other way, and how that choice preserves the current comment-rendering and `comments_signature` contracts. |

### Residual Risks and Testing Gaps

- The audit's core factual claim remains correct: v1.1.0 genuinely closes the
  per-issue relation-read and per-issue comment-metadata gaps. The additional
  findings in this pass are about edge-case contract completeness, not about
  the main boundary direction.
- Once the design is amended, [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring)
  should add focused tests for: very high relation counts (or a documented cap
  behavior), inverse-relation normalization into local dimensions, and
  placeholder-parent comment threads.

### Overall Assessment

This pass agrees with Review Pass 1 that the audit's main v1.1.0 boundary
shift is directionally correct. The new findings are stricter contract issues:
the design currently says "use the domain layer here" in a few places where
the upstream domain objects still require additional normalization or edge-case
policy decisions before they are a self-contained implementation reference for
[M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring).
