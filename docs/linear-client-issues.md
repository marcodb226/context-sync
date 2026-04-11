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
| [LC-4](#lc-4---issue-labels-not-wired-in-fetch-query) | Open | `Issue.get_labels()` exists but always raises — labels not in the fetch GQL query |
| [LC-5](#lc-5---no-packaged-batch-metadata-reads) | Open | No packaged batch metadata reads — three refresh patterns need raw GQL |
| [LC-6](#lc-6---newtype-identity-mismatch-across-the-boundary) | Won't do | Duplicate `NewType` aliases in context-sync — context-sync must adopt the library types |
| [LC-7](#lc-7---issue-priority-not-in-domain-surface) | Open | Issue `priority` field not in the GQL selection set or domain object |
| [LC-8](#lc-8---issue-parent-not-in-domain-surface) | Open | Issue `parent` (id + key) not in the GQL selection set or domain object |
| [LC-9](#lc-9---environment-variable-prefixing-leaks-caller-policy-into-the-library) | Open | Environment-variable prefixing leaks caller policy into the library |

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
failure currently aborts the entire `asyncio.gather` and surfaces as
`SystemicRemoteError`. However, the first release only stores attachment
metadata (URLs and titles) in ticket files and does not download content
(see [FW-2](future-work.md#fw-2-attachment-content-handling)). The
context-sync fix is to catch the attachment fetch failure gracefully and
proceed with an empty attachment list rather than aborting the sync.

**Workaround:** None available without patching the upstream library. The
query filter needs to use a supported `AttachmentFilter` field (for
example a top-level `issueId` variable with `attachments(issueId:
$issueId, ...)` if the API supports it, or a different query structure).

**Upstream tracking:**
[linear-client FW-28](../../linear-client/docs/future-work.md#fw-28---add-missing-attachment-fields-from-linear-schema)
tracks adding missing attachment fields; this bug is a prerequisite —
the query must work before additional fields matter.

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

**Upstream tracking:**
[linear-client FW-13](../../linear-client/docs/future-work.md#fw-13---add-workspace-identity-read-support-for-issue-validation)
— backlog item that would deliver exactly this surface.

<a id="lc-4---issue-labels-not-wired-in-fetch-query"></a>

### LC-4 - Issue labels not wired in fetch query

**Status:** Open

**Severity:** Low (workaround exists)

**Discovered:** M5-D1 domain-coverage audit (2026-04-08), root cause
identified M5-2 Phase C (2026-04-11)

**Description:** `Issue.get_labels()` and `Issue.peek_labels()` exist on
the domain object, and `Label.peek_parent()` / `Label.get_parent()`
support hierarchical label rendering. However, the issue fetch GQL query
([issues.py:1419](../../linear-client/src/linear_client/gql/services/issues.py#L1419))
does not select `labels { nodes { ... } }`, so `get_labels()` always
raises `LinearConfigurationError("Issue labels are not available from
the current GraphQL issue payload")`. The domain surface is modeled but
not wired.

**Impact on context-sync:** `RealLinearGateway` fetches labels (with
parent group names) via a supplementary raw-GQL query. Once the fetch
query includes labels, the existing domain surface would work and the
raw-GQL workaround could be dropped.

**Upstream tracking:** No linear-client FW item exists for this.

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

**Upstream tracking:**
- [linear-client FW-15](../../linear-client/docs/future-work.md#fw-15---add-batched-issue-metadata-reads-for-tracked-issue-sets)
  — batched issue metadata reads (backlog).
- [linear-client FW-16](../../linear-client/docs/future-work.md#fw-16---finish-comment-freshness-metadata-support-for-refresh-workflows)
  — comment freshness metadata for refresh workflows (backlog).
- Batch relation metadata has no dedicated FW item. Per-issue relation
  reads were delivered in v1.1.0 via
  [linear-client FW-14](../../linear-client/docs/future-work.md#fw-14---add-read-only-issue-relation-surfaces-beyond-blocker-search-projection),
  but the batched multi-issue variant is not tracked separately.
  `RealLinearGateway.get_refresh_relation_metadata` currently fans out
  one raw-GQL query per issue (forward + inverse links), producing 2*N
  upstream queries for N tracked issues.

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

<a id="lc-7---issue-priority-not-in-domain-surface"></a>

### LC-7 - Issue priority not in domain surface

**Status:** Open

**Severity:** Low (workaround exists)

**Discovered:** M5-2 Phase C (2026-04-11)

**Description:** The `Issue` domain object has no `priority` field. The
issue fetch GQL query
([issues.py:1419](../../linear-client/src/linear_client/gql/services/issues.py#L1419))
does not select `priority`. Linear's `Issue` type exposes `priority` as
an integer (0 = no priority, 1 = urgent, 2 = high, 3 = medium,
4 = low).

**Impact on context-sync:** `RealLinearGateway` fetches priority via a
supplementary raw-GQL query (`_ISSUE_SUPPLEMENTARY_QUERY`) on every
issue fetch. A domain-layer accessor would eliminate one field from that
supplementary query.

**Upstream tracking:** No linear-client FW item exists for this.

<a id="lc-8---issue-parent-not-in-domain-surface"></a>

### LC-8 - Issue parent not in domain surface

**Status:** Open

**Severity:** Low (workaround exists)

**Discovered:** M5-2 Phase C (2026-04-11)

**Description:** The `Issue` domain object has no `parent` field. The
issue fetch GQL query does not select `parent { id identifier }`.
Linear's `Issue` type exposes `parent` as a nullable `Issue` reference.

**Impact on context-sync:** `RealLinearGateway` fetches the parent issue
id and key via the same supplementary raw-GQL query. A domain-layer
accessor (e.g. `peek_parent()` / `get_parent()` returning an `Issue`
handle or a lightweight id+key pair) would eliminate another field from
that query.

**Upstream tracking:** No linear-client FW item exists for this.

<a id="lc-9---environment-variable-prefixing-leaks-caller-policy-into-the-library"></a>

### LC-9 - Environment-variable prefixing leaks caller policy into the library

**Status:** Open

**Severity:** Low (design cleanup / downstream coupling)

**Discovered:** M5-3 Phase B review (2026-04-11)

**Description:** `linear-client` lets callers configure an environment
prefix through constructor `env_prefix` or `LINEAR_ENV_PREFIX`, then
resolves configuration from `<PREFIX>LINEAR_*` variables. That mixes
deployment/orchestration policy into a generic client library. A
downstream tool that wants to inspect auth inputs or define its own
stable CLI contract must either duplicate the prefix-resolution algorithm
or intentionally diverge from library behavior. Prefix selection belongs
in the caller or wrapper that owns the deployment environment, not in the
generic client.

**Impact on context-sync:** context-sync should not need to know about
`LINEAR_ENV_PREFIX` just to choose a default auth mode or document its CLI
contract. The prefix-compatibility concern recorded in
[M5-3-R2](execution/M5-3-review.md#m5-3-r2) exists only because the
library exposes prefix resolution as part of its public config behavior.

**Workaround:** Downstream tools can keep environment selection in their
own wrapper layer and pass explicit constructor arguments or explicit
`auth_mode` values into `Linear(...)` rather than mirroring the library's
prefix rules.

**Upstream tracking:** No linear-client future-work item currently tracks
deprecating or removing environment-prefix support.
