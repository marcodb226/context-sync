# linear-client issues and gaps

Bugs and missing capabilities in
[linear-client](../../linear-client/) discovered during context-sync
development. Items are recorded as they surface; fixed items are updated
in place.

---

## Bugs

### 1. `AttachmentRepo.list_for_issue` uses unsupported filter field

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

### 2. No environment-variable control for `auth_mode`

**Severity:** Medium

**Discovered:** M5-2 Phase C (2026-04-10)

**Description:** The `Linear()` constructor accepts `auth_mode` as a
parameter (`"oauth"`, `"client_credentials"`, or `"api_key"`) but
defaults to `"oauth"`. There is no environment variable (e.g.
`LINEAR_AUTH_MODE`) to control the auth mode without code changes.

**Impact on context-sync:** The context-sync CLI calls `Linear()` with no
arguments, so it always defaults to `oauth` mode. Operators using
`client_credentials` or `api_key` auth cannot switch modes without
modifying the context-sync source or adding their own wrapper. The
context-sync CLI would need to either:
- pass a `--auth-mode` flag to `_create_linear_client()`, or
- have `linear-client` read `LINEAR_AUTH_MODE` from the environment
  automatically.

The second option is preferable — it keeps auth configuration in the
environment alongside the existing credential variables and doesn't
require every downstream CLI to add auth-mode flags.

### 3. No packaged workspace-identity surface

**Severity:** Low (workaround exists)

**Discovered:** M5-D1 domain-coverage audit (2026-04-08)

**Description:** There is no domain-layer method to read the stable
workspace UUID and slug from a fetched issue. The workspace identity must
be extracted via a raw GraphQL query through `issue → team →
organization`.

**Impact on context-sync:** `RealLinearGateway` uses a raw-GQL helper
(`_WORKSPACE_IDENTITY_QUERY`) for this. A packaged surface would
eliminate one of the five raw-GQL helper categories.

### 4. No packaged issue-label read surface

**Severity:** Low (workaround exists)

**Discovered:** M5-D1 domain-coverage audit (2026-04-08)

**Description:** There is no domain-layer method to read issue labels
(including parent group names for hierarchical label rendering). Labels
must be fetched via a supplementary raw GraphQL query.

**Impact on context-sync:** `RealLinearGateway` uses the supplementary
issue query to fetch labels alongside priority and parent issue. A
packaged surface would simplify the gateway and eliminate label-related
raw-GQL usage.

### 5. No packaged batch metadata reads

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

### 6. NewType identity mismatch across the boundary

**Severity:** Low (workaround exists)

**Discovered:** M5-1 Phase A (2026-04-09)

**Description:** `linear-client` defines `NewType` aliases for `IssueId`,
`IssueKey`, `CommentId`, etc. in `linear_client.types`. `context-sync`
defines its own independent `NewType` aliases in
`context_sync._types`. These are distinct types to Pyright, so passing a
`context_sync.IssueId` where `linear_client.IssueId` is expected (or
vice versa) requires explicit casting or a bridge import.

**Impact on context-sync:** The gateway uses `UpstreamIssueId` imports at
the boundary to satisfy Pyright. Full type unification would require
either adding `linear-client` as a formal dependency or re-exporting
shared types from a common location. The current workaround is
functional but adds friction at every boundary crossing.
