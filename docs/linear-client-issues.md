# linear-client issues and gaps

Bugs and missing capabilities in
[linear-client](../../linear-client/) discovered during context-sync
development. Items are recorded as they surface; fixed items are updated
in place.

## Summary

| ID | Status | Summary |
| --- | --- | --- |
| [LC-1](#lc-1---attachmentrepolist_for_issue-uses-unsupported-filter-field) | Open | `AttachmentRepo.list_for_issue` uses unsupported `AttachmentFilter.issue` field — blocks all attachment reads |
| [LC-2](#lc-2---no-environment-variable-control-for-auth_mode) | Won't do | No env-var control for `auth_mode` — callers should select mode explicitly |
| [LC-3](#lc-3---no-packaged-workspace-identity-surface) | Open | No packaged workspace-identity surface — requires raw GQL |
| [LC-4](#lc-4---no-packaged-issue-label-read-surface) | Open | No packaged issue-label read surface — requires raw GQL |
| [LC-5](#lc-5---no-packaged-batch-metadata-reads) | Open | No packaged batch metadata reads — three refresh patterns need raw GQL |
| [LC-6](#lc-6---newtype-identity-mismatch-across-the-boundary) | Won't do | Duplicate `NewType` aliases in context-sync — context-sync must adopt the library types |

---

## Bugs

<a id="lc-1---attachmentrepolist_for_issue-uses-unsupported-filter-field"></a>

### LC-1 - `AttachmentRepo.list_for_issue` uses unsupported filter field

**Status:** Open

**Severity:** Blocking (prevents any `Issue.get_attachments()` call from
succeeding against the current Linear API)

**Discovered:** M5-2 Phase C live smoke validation (2026-04-10)

**Description:**
[linear-client `attachment_repo.py:140`](../../linear-client/src/linear_client/domain/repos/attachment_repo.py#L140)
uses `filter: { issue: { id: { eq: $issueId } } }` in the
`ATTACHMENTS_BY_ISSUE_QUERY` GraphQL query. The Linear API's
`AttachmentFilter` type does not have an `issue` field. Every call to
`Issue.get_attachments()` fails with:

```
HTTP 400: Field "issue" is not defined by type "AttachmentFilter"
```

**Impact on context-sync:** `RealLinearGateway.fetch_issue()` calls
`issue.get_attachments()` as part of the concurrent detail fetch. The
failure is correctly surfaced as `SystemicRemoteError`, but it blocks the
entire `sync` path for any issue — not just issues with attachments.

**Workaround:** None available without patching the upstream library. The
query filter needs to use a supported `AttachmentFilter` field (for
example a top-level `issueId` variable with `attachments(issueId:
$issueId, ...)` if the API supports it, or a different query structure).

---

## Missing capabilities

<a id="lc-2---no-environment-variable-control-for-auth_mode"></a>

### LC-2 - No environment-variable control for `auth_mode`

**Status:** Won't do

**Rationale:** The library is a generic client, not a servant of any
particular downstream tool. Auth-mode selection is the caller's
responsibility. The `Linear()` constructor already accepts `auth_mode` as
a parameter — callers that want environment-driven selection should
implement that in their own CLI layer. See
[M5-3](implementation-plan.md#m5-3---cli-auth-mode-selection).

**Severity:** N/A

**Discovered:** M5-2 Phase C (2026-04-10)

**Description:** The `Linear()` constructor accepts `auth_mode` as a
parameter (`"oauth"`, `"client_credentials"`, or `"api_key"`) but
defaults to `"oauth"`. There is no environment variable to control the
auth mode without code changes. This is by design — the library exposes
the mechanism; the calling tool selects the policy.

<a id="lc-3---no-packaged-workspace-identity-surface"></a>

### LC-3 - No packaged workspace-identity surface

**Status:** Open

**Severity:** Low (workaround exists)

**Discovered:** M5-D1 domain-coverage audit (2026-04-08)

**Description:** There is no domain-layer method to read the stable
workspace UUID and slug from a fetched issue. The workspace identity must
be extracted via a raw GraphQL query through `issue → team →
organization`.

**Impact on context-sync:** `RealLinearGateway` uses a raw-GQL helper
(`_WORKSPACE_IDENTITY_QUERY`) for this. A packaged surface would
eliminate one of the five raw-GQL helper categories.

<a id="lc-4---no-packaged-issue-label-read-surface"></a>

### LC-4 - No packaged issue-label read surface

**Status:** Open

**Severity:** Low (workaround exists)

**Discovered:** M5-D1 domain-coverage audit (2026-04-08)

**Description:** There is no domain-layer method to read issue labels
(including parent group names for hierarchical label rendering). Labels
must be fetched via a supplementary raw GraphQL query.

**Impact on context-sync:** `RealLinearGateway` uses the supplementary
issue query to fetch labels alongside priority and parent issue. A
packaged surface would simplify the gateway and eliminate label-related
raw-GQL usage.

<a id="lc-5---no-packaged-batch-metadata-reads"></a>

### LC-5 - No packaged batch metadata reads

**Status:** Open

**Severity:** Low (workaround exists)

**Discovered:** M5-D1 domain-coverage audit (2026-04-08)

**Description:** Three batch metadata read patterns required by
context-sync's incremental refresh have no packaged domain-layer
equivalent:

- Batch issue metadata (id, key, updated_at, visibility) for an
  arbitrary set of tracked issue IDs.
- Batch comment/thread metadata (comment id, parent chain, resolution
  status) per issue for an arbitrary set of tracked issue IDs.
- Batch relation metadata (forward + inverse links) per issue for an
  arbitrary set of tracked issue IDs.

**Impact on context-sync:** `RealLinearGateway` implements all three as
raw-GQL helpers. Packaged equivalents would eliminate three of the five
raw-GQL helper categories, leaving only workspace identity and labels.

<a id="lc-6---newtype-identity-mismatch-across-the-boundary"></a>

### LC-6 - NewType identity mismatch across the boundary

**Status:** Won't do

**Rationale:** The authoritative types are those from `linear-client`.
The duplicate `NewType` aliases in `context_sync._types` (`IssueId`,
`IssueKey`, `CommentId`, `AttachmentId`) must be eliminated in favor of
the library's types in `linear_client.types`. This is a context-sync
cleanup task, not a linear-client issue. See
[M5-4](implementation-plan.md#m5-4---adopt-linear-client-newtypes).

**Severity:** N/A

**Discovered:** M5-1 Phase A (2026-04-09)

**Description:** `linear-client` defines `NewType` aliases for `IssueId`,
`IssueKey`, `CommentId`, `AttachmentId` in `linear_client.types`.
`context-sync` independently defines the same aliases in
`context_sync._types`. These are distinct types to Pyright. The fix is
to make `context-sync` re-export the library types and drop the
duplicates. `WriterId`, `Timestamp`, `WorkspaceId`, and `WorkspaceSlug`
are context-sync-only concepts and can stay.
