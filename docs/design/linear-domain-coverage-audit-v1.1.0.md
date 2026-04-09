# Linear Domain-Coverage Audit and Adapter Boundary

> **Status**: Phase A design artifact for [M5-D1](../implementation-plan.md#m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110)
> **Inspected package**: `linear-client` 1.1.0 from the repo-local `.venv`
> **Governing design inputs**: [docs/adr.md](../adr.md#31-foundation), [docs/design/0-top-level-design.md](0-top-level-design.md#11-linear-dependency-boundary), and [docs/design/0-top-level-design.md](0-top-level-design.md#62-refresh-flow)
> **Inspection inputs**: [docs/planning/change-requests/CR-26.04.07.md](../planning/change-requests/CR-26.04.07.md), [src/context_sync/_gateway.py](../../src/context_sync/_gateway.py), [src/context_sync/_types.py](../../src/context_sync/_types.py), [src/context_sync/_renderer.py](../../src/context_sync/_renderer.py), [linear-client docs/pub/release-1.1.0.md](../../../linear-client/docs/pub/release-1.1.0.md), [linear-client src/linear_client/__init__.py](../../../linear-client/src/linear_client/__init__.py), and [linear-client src/linear_client/types.py](../../../linear-client/src/linear_client/types.py)
> **Supersedes**: [docs/design/linear-domain-coverage-audit-v1.0.0.md](linear-domain-coverage-audit-v1.0.0.md) as the authoritative adapter-boundary reference for future real-gateway work

This audit re-checks the installed `linear-client` surface against the current `context-sync` v1 snapshot contract rather than against the narrower v1.0.0 gap list alone. The main boundary change from the historical audit is that per-issue comment metadata and per-issue relation reads are now domain-layer capabilities, so the local raw-GraphQL escape hatch can shrink on the ticket-fetch and traversal paths. Two required ticket-rendering gaps still remain outside the packaged surface: workspace identity and current issue labels. The batched refresh metadata contract also remains outside the packaged surface and still requires narrow local helpers.

## 1. Coverage Matrix

| Area | Required operation | Current best v1.1.0 surface | Coverage | Boundary outcome / notes |
| --- | --- | --- | --- | --- |
| Root and ticket resolution | Fetch one issue by `issue_id` or `issue_key`, including scalar issue metadata and `updated_at` | `linear.issue(id=...).fetch()`, `linear.issue(key=...).fetch()`, or `linear.gql.issues.get(...)` | Covered by domain layer | Sufficient for explicit root resolution, single-ticket fallback fetches, and current-key / previous-key resolution through the normal issue lookup path. |
| Workspace identity validation | Read stable workspace id plus workspace slug for a fetched ticket and compare them against the manifest workspace | None in the inspected packaged surface; `Linear.me()` still exposes only `viewer { id name email }` and no inspected issue/team/user path exposes workspace identity | Missing | Keep one narrow raw helper for `get_issue_workspace_identity(issue_id)`. |
| Label rendering | Read the current issue labels and normalize them to the persisted `Group / Label` or `Label` strings used in ticket frontmatter | No packaged issue-label read path; `Issue.get_labels()` explicitly documents that the current issue payload is insufficient for label reads | Missing | Keep one narrow raw helper for single-issue label rendering inside `fetch_issue`. |
| Full ticket fetch | Assemble one renderable ticket bundle with issue scalars, labels, comments, attachments, relations, and workspace identity | Domain `Issue.fetch()` + `Issue.get_comments()` + `Issue.get_attachments()` + `Issue.get_links()` plus local workspace/label helpers | Partially covered | v1.1.0 closes the per-issue comment and relation gaps, but workspace identity and labels still need local helpers. |
| Comment rendering and `ticket_ref` scan | Fetch full comments for one issue, including reply bodies and thread topology | `Issue.get_comments()` / `await issue.comments`, then traverse `Comment.children` | Covered by domain layer | v1.1.0 returns root-thread projection rather than a flat list; the gateway must flatten that projection into `CommentData` plus `ThreadData`. |
| Attachment rendering | Fetch attachment metadata for one issue | `Issue.get_attachments()` / `await issue.attachments` | Covered by domain layer | Sufficient for the current metadata-only attachment contract. |
| Traversal and rendered relations | Read visible issue relations for traversal and persisted frontmatter | `Issue.get_links()` / `await issue.links` | Covered by domain layer | `get_ticket_relations(issue_ids)` remains a gateway helper because traversal wants a batch-shaped mapping, but its approved implementation path is domain-layer fan-out over `Issue.get_links()`, not local raw GraphQL. |
| Refresh issue cursor | Batch-read issue identity plus `updated_at` for the tracked reachable set | None in the inspected packaged surface | Missing | `get_refresh_issue_metadata(issue_ids)` remains a raw helper. |
| Refresh comment cursor | Batch-read comment/thread metadata for `comments_signature` across the tracked reachable set | Per-issue `Comment.updated_at`, `resolved_at`, `parent`, and `children` now exist, but no batch-by-issue-set surface exists | Partially covered | Per-issue fetches move to the domain layer; the batched refresh path still needs `get_refresh_comment_metadata(issue_ids)`. |
| Refresh relation cursor | Batch-read relation metadata for `relations_signature` across the tracked reachable set | Per-issue `Issue.get_links()` now exists, but no batch-by-issue-set surface exists | Partially covered | The batched refresh path still needs `get_refresh_relation_metadata(issue_ids)`. |

## 2. Boundary Decision

`context-sync` should keep the domain layer as the default integration path for all ordinary single-ticket reads that `linear-client` v1.1.0 now covers. That means issue resolution and scalar issue fetches, full comment-body reads plus thread topology, attachment metadata, and per-issue relation reads all stay on packaged surfaces. The raw-GraphQL escape hatch remains narrow, but it is narrower than the v1.0.0 audit: raw GraphQL is no longer the approved default for single-issue relation reads or for per-issue comment metadata.

The real gateway should therefore follow these rules:

- `fetch_issue(issue_id_or_key)` resolves the issue through the domain layer, reads comments through `Issue.get_comments()` and `Comment.children`, reads attachments through `Issue.get_attachments()`, reads per-issue relations through `Issue.get_links()`, and fills the remaining bundle fields through the dedicated workspace-identity and label helpers.
- `get_ticket_relations(issue_ids)` remains a gateway helper because traversal wants a mapping keyed by issue UUID, but its approved implementation path is domain-layer fan-out over `Issue.get_links()`. The gateway implementation should deduplicate input ids, own bounded concurrency internally, and return normalized `RelationData` values to callers.
- The composite refresh pass keeps its batched metadata helpers because the packaged surface still does not expose by-id-set issue/comment/relation metadata reads.

Raw `linear.gql.*` usage is approved only for these five helper categories:

- `get_issue_workspace_identity(issue_id)` — stable workspace UUID plus slug for manifest validation
- `get_issue_labels(issue_id)` — normalized label strings for `IssueData.labels`
- `get_refresh_issue_metadata(issue_ids)` — batched issue `updated_at` plus visibility
- `get_refresh_comment_metadata(issue_ids)` — batched comment/thread metadata for `comments_signature`
- `get_refresh_relation_metadata(issue_ids)` — batched relation metadata for `relations_signature`

All raw helpers are read-only helpers inside the real gateway. They must use `query(...)` or `paginate_connection(...)` as appropriate, own pagination internally, return fully materialized results, and never call `gql(...)` or `mutate(...)`. If later implementation work shows that traversal relation fan-out is materially too expensive and truly needs a batched raw relation-read helper, treat that as a separate plan amendment rather than silently widening this boundary.

## 3. Type-Mapping Table

The gateway boundary should use one `NewType` identity per domain concept across `context-sync` and `linear-client`. The preferred reconciliation strategy is to re-export overlapping upstream aliases from [src/context_sync/_types.py](../../src/context_sync/_types.py) so existing import sites continue to work while the underlying type identity is shared.

### 3.1 Values That Cross The Current Boundary

| Boundary position | Boundary type | Source | Decision / rationale |
| --- | --- | --- | --- |
| `LinearGateway.fetch_issue(issue_id_or_key)` input | `str` | bare `str` | Keep this as the single polymorphic entry point where callers legitimately do not know whether they hold an issue UUID or an issue key. |
| `get_workspace_identity(issue_id)` input and all batch-helper `issue_ids` inputs | `IssueId` | upstream `linear_client.types.IssueId`, re-exported from `context_sync._types` | Use one shared `NewType` identity across the dependency boundary. |
| `WorkspaceIdentity.workspace_id` | `WorkspaceId` | context-sync-only alias | No upstream workspace identifier alias exists. |
| `WorkspaceIdentity.workspace_slug` | `WorkspaceSlug` | context-sync-only alias | No upstream workspace slug alias exists. |
| All issue id / key outputs in `IssueData`, `RelationData`, and `RefreshIssueMeta` | `IssueId` / `IssueKey` | upstream re-exports | Exact semantic duplicates of upstream aliases; do not keep parallel local definitions. |
| All comment id outputs in `CommentData`, `ThreadData`, `RefreshCommentMeta`, and `RefreshThreadMeta` | `CommentId` | upstream re-export | Exact semantic duplicate of the upstream alias. |
| `AttachmentData.attachment_id` | `AttachmentId` | upstream re-export | Exact semantic duplicate of the upstream alias. |
| All gateway timestamp fields | `Timestamp` aliased to upstream `IsoTimestamp` | local public name over upstream alias | Keep the existing `Timestamp` name for context-sync ergonomics, but make it an alias/re-export so the underlying `NewType` identity is shared with `linear-client`. |
| `AttachmentData.url` | `AssetUrl` | upstream alias | Stronger than bare `str` and already matches the dependency's public vocabulary. |
| `RelationData.relation_type` | `IssueLinkType` | upstream alias | Matches the typed relation vocabulary returned by `IssueLink` and `IssueLinkModel`. |
| Display text fields (`IssueData.title`, `status`, `assignee`, `creator`, `description`; `CommentData.body`, `author`; `AttachmentData.title`, `creator`; `IssueData.labels`; `RelationData.dimension`) | `str` | bare `str` | These are display-oriented values or context-sync-specific local vocabulary, not reusable upstream identifier concepts. |
| `IssueData.priority` | `int | None` | primitive | Upstream exposes priority numerically; an additional alias would not add useful type safety. |
| Boolean freshness / thread flags (`ThreadData.resolved`, `RefreshIssueMeta.visible`, `RefreshCommentMeta.deleted`, `RefreshThreadMeta.resolved`) | `bool` / `bool | None` | primitive | The field names already carry the domain meaning. |

### 3.2 Upstream Aliases Intentionally Outside The Current Boundary

| Upstream alias | Current disposition | Reason |
| --- | --- | --- |
| `UserId` | Not part of the current boundary | The current ticket-file contract persists assignee and creator display names only. If a later amendment adds persisted user identifiers or delegate metadata, use the upstream alias directly instead of inventing a local one. |
| `TeamId` / `TeamKey` | Not part of the current boundary | The current ticket-file contract does not persist team context even though the issue surface now exposes it. |
| `StatusId` / `StatusCategory` | Not part of the current boundary | The current v1 contract persists workflow status display name only. Category enrichment would widen the persisted ticket contract and diff surface. |
| `LabelId` | Not part of the current boundary | The label helper should return already-normalized display strings for `IssueData.labels`; label IDs are not persisted today. |
| `IssueLinkId` | Not part of the current boundary | Relation identity is not part of the current frontmatter or refresh signatures; only relation type and target identity affect the current contract. |

## 4. Additional v1.1.0 Capabilities Deliberately Kept Out Of The Current Boundary

| Capability | Available surface | Current v1 disposition | Reason |
| --- | --- | --- | --- |
| Workflow status category | `Status.category`, `IssueModel.status_category` | Do not add to the current ticket frontmatter | The current contract persists status display name only. Adding workflow-category output would change the user-facing snapshot contract and the diff surface. |
| Team context | `Issue.team`, `IssueModel.team_key` | Do not add to the current ticket frontmatter | The snapshot is already workspace-scoped for correctness; team metadata would be optional enrichment, not a current correctness dependency. |
| Delegate / app-actor context | `Issue.delegate`, `IssueModel.delegate_id`, `User.app` | Do not add to the current ticket frontmatter | The current contract persists assignee and creator display names only. Delegate or actor-type output would be a new user-facing surface that needs explicit acceptance rather than silent inclusion during gateway implementation. |

The richer history surfaces added in v1.1.0 remain outside the current boundary as well. The current v1 snapshot still excludes persisted issue history, so those capabilities continue to align with the existing future-work deferrals rather than with this gateway boundary.

## 5. Recorded Missing Upstream Capabilities

The inspected `linear-client` v1.1.0 package is still missing several read capabilities that the current `context-sync` v1 contract requires:

- a packaged workspace-identity surface that exposes stable workspace UUID plus workspace slug on the fetched-issue path
- a packaged issue-label read surface suitable for current ticket rendering
- a packaged batch issue-metadata read for an arbitrary tracked issue-id set
- a packaged batch comment/thread metadata read for an arbitrary tracked issue-id set
- a packaged batch relation-metadata read for an arbitrary tracked issue-id set

The important difference from the v1.0.0 audit is that per-issue comment metadata and per-issue relation reads are no longer part of this missing-capability list. Those are now packaged domain-layer surfaces and should not be treated as local raw-GraphQL obligations for ordinary ticket fetches.

## 6. Risks And Explicit Deferrals

- The installed package proves the absence of packaged workspace-identity and issue-label read surfaces, but this audit does not prove the exact raw GraphQL query shape or pagination behavior needed for those helpers. The real gateway work must verify the live schema shape while staying inside the helper categories recorded here.
- Keeping `get_ticket_relations(issue_ids)` on domain-layer fan-out keeps the boundary narrow and more faithful to the packaged surface, but it may cost more upstream round trips than a future batched raw helper. Do not widen the raw boundary pre-emptively; if maintained measurements later show material cost, represent that as a separate accepted amendment.
- Team metadata, delegate metadata, workflow category, and actor-type output remain outside the current v1 ticket-file contract. If the repository later wants them in rendered output, add them through a future plan change rather than as opportunistic expansion during gateway implementation.
- Issue labels are now an explicit required package-surface gap, not a polish item. The real gateway must fill them within the audited helper set or the current ADR / top-level-design frontmatter contract would remain unimplemented.
