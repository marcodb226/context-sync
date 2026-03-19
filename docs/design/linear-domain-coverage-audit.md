# Linear Domain-Coverage Audit and Adapter Boundary

> **Status**: Completed design artifact for [M1-D2](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary)
> **Inspected package**: `linear-client` 1.0.0 from the repo-local `.venv`
> **Inputs**:
> [docs/implementation-plan.md](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary),
> [docs/adr.md](../adr.md#31-foundation),
> [docs/design/0-top-level-design.md](0-top-level-design.md#11-linear-dependency-boundary),
> [docs/design/0-top-level-design.md](0-top-level-design.md#62-refresh-flow),
> [docs/design/linear-client.md](linear-client.md),
> and [M1-D3](../execution/M1-D3.md)

This audit records which v1 `context-sync` read operations are already covered
by the installed `linear-client` package and which ones still require a narrow
local fallback boundary. The conclusion is intentionally asymmetric:
`context-sync` should keep the domain layer as the default path for ordinary
single-ticket reads, but it must reserve a small raw-GraphQL boundary for
relation reads and for the composite refresh-cursor metadata pass adopted by
[M1-D3](../implementation-plan.md#m1-d3---refresh-composite-freshness-contract-amendment).

## 1. Coverage Matrix

| Area | Required operation | Current best surface | Coverage | Notes |
| --- | --- | --- | --- | --- |
| Root and ticket resolution | Fetch one issue by `issue_id` or `issue_key`, including scalar issue metadata and `updated_at` | `linear.issue(...).fetch()` or `linear.gql.issues.get(...)` | Covered by domain layer | This is sufficient for explicit root resolution, single-ticket fallback fetches, and ordinary scalar issue reads. |
| Team-scoped discovery | Search issues within one team by documented filters | `team.search_issues(...)` | Covered by domain layer | Useful for discovery or team-scoped lookups, but not a substitute for arbitrary tracked-id refresh reads. |
| Full ticket fetch | Assemble one renderable ticket bundle for v1 persisted fields | `Issue.fetch()` + `await issue.comments` + `await issue.attachments` | Partially covered | Scalar issue fields, comment bodies, and attachment metadata are available. Relations are not. A full render bundle therefore still needs a separate relation-read step. |
| Comment rendering and `ticket_ref` scan | Fetch full comments for one issue, including body text | `await issue.comments` | Covered by domain layer | The current package already implements this with internal raw GraphQL and returns comment `id`, `body`, `createdAt`, and author. That is enough for rendering and URL extraction, but not for `comments_signature`. |
| Attachment rendering | Fetch attachment metadata for one issue | `await issue.attachments` | Covered by domain layer | The current package already implements this with internal raw GraphQL and returns attachment `id`, `title`, `url`, `createdAt`, and creator. This is enough for the v1 metadata-only attachment contract. |
| Traversal and rendered relations | Read issue relations for one or many issues | None in the audited surface | Missing | `Issue.link(...)` creates relations, but no audited domain getter, repository method, or typed GraphQL service currently lists or fetches issue relations for read-only traversal/render use. |
| Refresh issue cursor | Batch-read issue identity plus `updated_at` for the tracked reachable set | None in the audited surface | Missing | The installed surfaces expose single-issue `get(...)` and filtered search, but not the by-id batch metadata read needed by [docs/design/0-top-level-design.md](0-top-level-design.md#62-refresh-flow). |
| Refresh comment cursor | Batch-read comment and thread metadata for `comments_signature` | None in the audited surface | Missing | The installed comment surfaces omit comment `updatedAt`, parent/root topology, thread `resolved`, and deletion or tombstone state. The metadata-only refresh path therefore needs a new raw-GraphQL helper if the accepted v1 contract is kept intact. |
| Refresh relation cursor | Batch-read relation metadata for `relations_signature` | None in the audited surface | Missing | The same relation-read gap that blocks traversal also blocks refresh, and refresh needs it in batched metadata form across the tracked reachable set. |

## 2. Boundary Decision

`context-sync` should keep the domain layer as the default integration path for
all ordinary single-ticket reads that the audited package already supports.
That means later implementation tickets should keep using domain objects for:

- issue resolution and scalar issue fetches
- full comment-body fetches used for rendering and `ticket_ref` URL scanning
- attachment metadata fetches
- team issue search when a ticket genuinely needs a team-scoped discovery path

Raw `linear.gql.*` usage is allowed only inside one narrow local adapter
module, and only for the following read helpers unless a later accepted design
ticket widens the boundary:

- `get_ticket_relations(issue_ids)` for traversal and rendered `relations`
- `get_refresh_issue_metadata(issue_ids)` for batched `issue_updated_at` and
  visibility checks across the tracked reachable set
- `get_refresh_comment_metadata(issue_ids)` for the metadata-only
  `comments_signature` path
- `get_refresh_relation_metadata(issue_ids)` for `relations_signature`

Later traversal, refresh, serializer, and CLI orchestration code should call
those adapter helpers rather than calling `linear.gql.query(...)` directly.
This keeps the local GraphQL escape hatch explicit, reviewable, and replaceable
if upstream `linear-client` grows the missing domain features later.

## 3. Recorded Missing Upstream Capabilities

The inspected `linear-client` package is missing several read capabilities that
`context-sync` v1 needs:

- a read-only issue-relation listing API at either the domain layer or the
  typed GraphQL-service layer
- a typed comment and thread metadata surface that exposes the fields required
  by `comments_signature`, especially comment `updated_at`, parent/root
  topology, thread `resolved`, and any deletion or tombstone signal
- a batched issue-metadata read API for an arbitrary tracked-id set rather than
  only single-issue fetches and team-scoped search

These gaps should remain visible as upstream `linear-client` follow-up targets
even if `context-sync` ships a narrow local raw-GraphQL fallback first.

## 4. Risks and Unresolved Points

- The accepted metadata-only comment freshness path is not yet proven to be
  operationally cheap. The installed package has no packaged batched
  comment-metadata helper, so the local fallback may still need to page
  through comment rows in a way that scales with comment volume. If later
  implementation confirms that this path is materially more expensive than
  intended, record that as a design or adapter risk rather than silently
  weakening the default v1 refresh contract.
- This audit could not confirm from the installed package whether
  comment-level `updatedAt` both exists in the available raw GraphQL shape and
  advances on comment edit. The installed domain and repository surfaces expose
  only `createdAt` for comments. Before [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery)
  hardcodes `comments_signature` around comment `updated_at`, implementation
  work must either validate that signal live or record the accepted fallback
  input explicitly.
- The audited package surface does not clearly expose workspace identity
  metadata such as workspace id or slug on the issue/team/user paths inspected
  for this ticket. If later tickets need an authoritative fetched-workspace
  identity to satisfy the manifest contract, that check will require either a
  narrow raw-GraphQL helper or an accepted design clarification that team-level
  identity is sufficient for v1.
