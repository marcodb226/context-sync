# Tool Design: Linear Context Sync — Implementation Design

> **Status**: Draft
> **Date**: 2026-03-13
> **Context**: Forked from the agent-control-plane repo

---

## 1. Library API

The primary interface is an async Python class that receives an authenticated `Linear` client and a target directory:

```python
from context_sync import ContextSyncer

syncer = ContextSyncer(
    linear=linear_client_instance,  # reuse the caller's authenticated client
    context_dir=Path("/work/repo/linear-context"),
    dimensions={
        "blocks": 3,
        "is_blocked_by": 2,
        "parent": 2,
        "child": 2,
        "relates_to": 1,
        "ticket_ref": 1,
    },
)

class ContextSyncer:
    async def sync(
        self,
        root_ticket_id: str,
        max_tickets_per_root: int = 200,
        dimensions: dict[str, int] | None = None,
    ) -> SyncResult: ...

    async def add(
        self,
        ticket_ref: str,
    ) -> SyncResult: ...

    async def remove_root(
        self,
        ticket_ref: str,
    ) -> SyncResult: ...

    async def refresh(
        self,
        missing_root_policy: Literal["quarantine", "remove"] = "quarantine",
    ) -> SyncResult: ...

    async def diff(self) -> DiffResult: ...

# Initial sync: dump the root ticket plus its reachable neighborhood
result = await syncer.sync(root_ticket_id="ACP-123", max_tickets_per_root=200)

# Delta refresh: update stale files in place, quarantining unavailable roots
result = await syncer.refresh()

# Delta refresh with explicit forced removal of unavailable tracked roots
result = await syncer.refresh(missing_root_policy="remove")

# Expand with a newly discovered ticket by issue key or Linear URL,
# then run whole-snapshot refresh semantics across all roots
result = await syncer.add(ticket_ref="ACP-999")

# Remove a root, then run whole-snapshot refresh semantics across all roots
result = await syncer.remove_root(ticket_ref="ACP-999")

# Compare local files to Linear without modifying anything
result = await syncer.diff()
```

Caller-facing inputs continue to use familiar issue keys or Linear issue URLs for ergonomics. Internally, once a ticket is resolved, the stable Linear UUID becomes the authoritative identity used for deduplication, root membership, and issue-key-change handling.

Traversal configuration consists of the per-dimension depths plus `max_tickets_per_root`. The cap applies independently to each root's reachable set rather than once globally across the whole context directory, and the final snapshot is the union of those per-root reachable sets.

Traversal semantics and interface rationale live in [docs/adr.md](<../adr.md>).

### 1.1 Linear Dependency Boundary

`ContextSyncer` assumes the caller already has `linear-client` installed and
can provide an authenticated `Linear` instance. The dependency is a private
GitHub repository documented in
[docs/design/linear-client.md](<linear-client.md>), so agent sessions must not
treat installation as self-serve bootstrap work. If the project virtualenv
does not already contain `linear-client`, ask a human to install it before
running imports, CLI commands, or validations that depend on the library.
The repo keeps the local credential bootstrap template at
[`scripts/.linear_env.sh.sample`](../../scripts/.linear_env.sh.sample); create
the ignored `scripts/.linear_env.sh` from that sample and source it in the
same shell session before running Linear-dependent commands.

Within `context-sync`, prefer the `linear-client` domain layer. Reach for
`linear.gql.*` only when the domain layer does not yet expose a required
operation, and keep that fallback behind a narrow adapter boundary so the rest
of the tool does not grow direct GraphQL dependencies. Whenever such a gap is
encountered, record the missing domain capability in an authoritative project
artifact so maintainers can extend the upstream `linear-client` roadmap. If
the gap is deferred rather than addressed immediately, track that follow-up in
[docs/future-work.md](<../future-work.md>).

---

## 2. CLI Interface

For human use and shell invocation:

```bash
# Initial sync
context-sync sync ACP-123 --max-tickets-per-root 200 --context-dir linear-context \
  --depth-blocks 3 --depth-is-blocked-by 2 --depth-parent 2 \
  --depth-child 2 --depth-relates-to 1 --depth-ticket-ref 1

# Delta refresh all
context-sync refresh --context-dir linear-context

# Delta refresh, forcing immediate removal of unavailable tracked roots
context-sync refresh --context-dir linear-context --missing-root-policy remove

# Expand with a newly discovered root, then refresh the whole snapshot
context-sync add ACP-999 --context-dir linear-context

# Remove a root, then refresh the whole snapshot
context-sync remove-root ACP-999 --context-dir linear-context

# Diff against Linear's live state
context-sync diff --context-dir linear-context --json
```

The CLI is a thin wrapper over the async library API, using `asyncio.run()` as the entry point. All logic lives in the library layer.

If `diff` detects a lock record that is not demonstrably stale, the CLI should fail with a clear non-interactive message. That message should explain that the refusal is intentional: running `diff` now would compete with the mutating run for rate-limited Linear API calls and could delay the write. The output should recommend retrying after the lock clears or after an operator resolves the lock.

Each invocation operates on exactly one `context_dir`. Running the tool against multiple directories is supported only by making separate invocations; the tool does not route work across directories on the caller's behalf.

Parallel invocations against different context directories are allowed. They may still contend on shared upstream Linear rate limits, but the first release does not add any cross-process coordination layer on top of `linear-client`.

Each `context_dir` is scoped to one Linear workspace. Tickets from multiple teams in that workspace may coexist in the same snapshot. Roots from a different workspace are rejected before any mutation occurs.

### 2.1 Context Directory Contents

For the first release, a context directory contains:

- ticket snapshot files such as `ACP-123.md`;
- `.context-sync.yml`, a small manifest file;
- `.context-sync.lock`, a small structured writer-lock file that normally exists only while a mutating operation owns the directory, though an interrupted writer may leave behind a stale lock record.

The manifest is the authoritative directory-level metadata file. It stores:

- the context format version;
- the bound Linear workspace identity, including stable workspace ID and workspace slug;
- the active traversal configuration, including per-dimension depths and `max_tickets_per_root`;
- the current root-ticket set, keyed by stable ticket UUID, including per-root state such as `active` or `quarantined`;
- a ticket lookup table that maps stable ticket UUIDs to current issue keys and current file paths;
- a key-alias table that maps locally known current and previous issue keys back to stable ticket UUIDs;
- snapshot-pass metadata, including the last completed snapshot mode and timestamps for the most recent completed pass.

This design keeps v1 simple. We do not introduce a separate general-purpose index file beyond the manifest. The manifest already answers the important directory-level questions quickly: which workspace does this snapshot belong to, which tickets are roots, and which locally tracked ticket does a current or previously observed issue key refer to?

Because the manifest is authoritative for roots, deleting a ticket file by hand is not a supported way to remove a root. If the ticket remains in the manifest root set, a later refresh may recreate the file.

The ticket file should still mirror root state for single-file readers. For root tickets, frontmatter includes `root_state: "active"` or `root_state: "quarantined"`. When a root is quarantined, frontmatter also includes a machine-readable reason such as `quarantined_reason: "not_available_in_visible_view"`. If file state and manifest state ever diverge during recovery from an interrupted run, the manifest remains authoritative.

Ticket files remain named by the current human-facing issue key for readability. The stable Linear UUID is the authoritative identity used for deduplication, root membership, and issue-key-change handling. When the tool observes that a tracked ticket's current issue key changed, it renames the local file and preserves the previous key in the manifest alias table so local agents can still resolve old references offline. The concrete documented reason for this today is that a Linear issue can move to another team in the same workspace and receive a new issue ID. More generally, the implementation should treat any upstream reassignment of the human-facing issue key the same way.

That offline alias support is intentionally bounded in v1. The tool can preserve issue-key-change history only from the point it starts tracking a ticket unless the API itself exposes older aliases; importing such historical aliases is deferred to [FW-4](<../future-work.md#fw-4-historical-ticket-alias-import>).

The lock file is not just a sentinel. For the first release it should store enough metadata for safe contention handling and operator diagnosis:

- `writer_id`: a unique ID for the owning invocation;
- `host`: the machine or worker host identity;
- `pid`: the owning process ID when available;
- `acquired_at`: the timestamp when the lock was taken;
- `mode`: the mutating operation (`sync`, `refresh`, `add`, or `remove-root`).

The lock must be acquired with an atomic create-or-fail step. If a lock record already exists, the tool inspects its metadata before deciding what to do next.

For v1, a lock is **demonstrably stale** only when the tool can prove the recorded writer is gone, for example because the lock names the current host and a PID that no longer exists. `acquired_at` is still important for diagnostics, but timestamp age alone is not sufficient to authorize preemption in v1.

`diff` never acquires, clears, or preempts the lock record. It may inspect lock metadata to decide whether it can safely proceed, but it remains read-only with respect to both ticket files and lock state. If the lock is not demonstrably stale, `diff` fails fast rather than competing with the mutating run for rate-limited Linear API capacity.

### 2.2 Ticket File Rendering

Ticket files are rendered deterministically. YAML mapping keys are emitted in lexicographic order at each nesting level, optional empty values are omitted, and timestamps are normalized to UTC RFC3339 with `Z`. List element order follows the specific normalization rules for that collection type.

Labels are rendered as a single display string. If a label group exists, the stored string is `<group> / <label>`; otherwise it is just `<label>`. Labels are sorted lexicographically by that full rendered string.

The body has a fixed section order:

1. description
2. comments

When `root_state == "quarantined"`, the serializer also emits a short warning preamble before the normal description section. That warning is local snapshot metadata explaining that the tracked root was unavailable during the last refresh and that the content below may be stale. It is not fetched Linear content and should be clearly distinguishable from the ticket description itself.

The comments section is rendered as threads, not as a flat chronological list. Top-level threads are ordered newest-first by thread activity. Within each thread, the parent comment is rendered first and replies are nested directly under that parent. Replies within a sibling set are rendered in chronological order so the local conversation reads naturally. The thread-level `resolved` flag belongs with the rendered thread metadata and with the machine-readable thread marker.

Machine-readable boundaries use namespaced HTML comment markers, while human-readable headings remain in the Markdown for direct browsing. A representative shape is:

```markdown
<!-- context-sync:section id=description-<ticket_uuid> start -->
## Description
...description markdown...
<!-- context-sync:section id=description-<ticket_uuid> end -->

<!-- context-sync:section id=comments-<ticket_uuid> start -->
## Comments
<!-- context-sync:thread id=<root_comment_id> resolved=false start -->
### Thread by Alice at 2026-03-13T09:15:00Z
...root comment markdown...
<!-- context-sync:comment id=<reply_comment_id> parent=<root_comment_id> start -->
...reply markdown...
<!-- context-sync:comment id=<reply_comment_id> end -->
<!-- context-sync:thread id=<root_comment_id> end -->
<!-- context-sync:section id=comments-<ticket_uuid> end -->
```

Parsers should recognize only exact `context-sync:` markers emitted by the serializer. The Markdown inside those boundaries is opaque content and must not be recursively parsed for additional structure.

---

## 3. Return Contracts

### 3.1 SyncResult

```python
@dataclass
class SyncResult:
    created: list[str]       # current issue keys of newly created files
    updated: list[str]       # current issue keys of files that were refreshed
    unchanged: list[str]     # current issue keys of files that were fresh (skipped)
    removed: list[str]       # current issue keys removed from the snapshot, including derived files pruned and roots removed by policy
    errors: list[SyncError]  # tickets that could not be fetched

@dataclass
class SyncError:
    ticket_id: str           # current issue key for reporting
    error_type: str          # e.g., "not_found", "permission_denied", "api_error", "root_quarantined"
    message: str
    retriable: bool
```

### 3.2 DiffResult

```python
@dataclass
class DiffEntry:
    ticket_id: str            # current issue key for reporting
    status: str               # "current", "stale", "missing_locally", "missing_remotely"
    changed_fields: list[str]  # e.g., ["status", "comments"] — empty if current

@dataclass
class DiffResult:
    entries: list[DiffEntry]
    errors: list[SyncError]
```

---

## 4. Error Handling

Errors are not all treated the same. Systemic remote failures abort the run immediately, while isolated linked-ticket failures are reported in `SyncResult` when the broader run can still proceed safely.

| Scenario | Tool behavior |
|---|---|
| Root ticket fetch fails | Raise immediately — no meaningful partial result without the root |
| Existing manifest root is not available during `refresh` and `missing_root_policy=\"quarantine\"` | Mark the root quarantined in the manifest, rewrite the local ticket file so `root_state` and the warning preamble reflect quarantine, skip traversing from it during this pass, and include the condition in `errors` |
| Existing manifest root is not available during `refresh` and `missing_root_policy=\"remove\"` | Remove the root from the manifest root set, delete its local file immediately, and continue the refresh pass |
| Linked ticket fetch fails unexpectedly while the broader run is still healthy | Write all successful tickets; include failed ticket in `errors` |
| Systemic remote failure (workspace access lost, invalid auth, lost network access, retry-exhausted `5xx`) | Abort immediately and stop further edits; a partial snapshot may remain if the failure happens mid-run |
| Linear API rate limit | Let `linear-client` perform retry/backoff; if retries are exhausted, treat it as a systemic remote failure |
| Context directory does not exist | Create it |
| Mutating operation sees a context directory lock that belongs to an active writer | Fail fast with a clear error; do not wait indefinitely |
| Mutating operation sees a demonstrably stale context directory lock | Preempt the stale lock, log that decision, and continue |
| Mutating operation sees a context directory lock whose staleness cannot be established safely | Fail with an explicit stale-lock error; do not guess |
| `diff` sees a lock record that is not demonstrably stale | Fail fast with a clear error explaining that `diff` would otherwise compete with the mutating run for rate-limited Linear API calls |
| Root ticket belongs to a different workspace than the current snapshot | Raise before mutating the context directory |
| `add` is given a Linear URL whose workspace slug clearly mismatches the manifest | Fail fast before the full refresh flow |
| `remove-root` targets a ticket that is not in the manifest root set | Fail fast with a clear error |
| Previously local derived ticket is no longer reachable from the recomputed visible graph | Prune it normally; do not keep a tombstone file |
| Process interrupted mid-run | No partial file writes, but the directory may still contain a partially applied snapshot update |
| File write permission error | Raise exception |

The caller (agent loop or human) decides how to handle the `SyncResult`:
- Root failure → abort context reconstruction
- Systemic remote failure → abort the run; if the directory is git-managed, the caller may choose to revert partial local edits
- Linked ticket failure → proceed with partial context or retry

---

## 5. Authentication

The tool does **not** manage its own Linear authentication.

- **Library mode**: Receives the caller's authenticated `Linear` client instance. The caller controls authentication, connection pooling, and lifecycle.
- **CLI mode**: Requires `linear-client` to already be installed in the active
  environment, reads the same environment variables as `linear-client`
  (`LINEAR_CLIENT_ID`, `LINEAR_CLIENT_SECRET`, etc.), and constructs its own
  client.

---

## 6. Internal Data Flow

### 6.1 Sync Flow

```
sync(root_ticket_id, max_tickets_per_root, dimensions)
  │
  ├─ Attempt atomic writer-lock acquisition for context_dir
  ├─ If a lock record already exists: inspect lock metadata
  ├─ If the recorded writer is active: fail fast
  ├─ If the lock is demonstrably stale: preempt it and continue
  ├─ Else: fail with an explicit stale-lock error
  ├─ Load or initialize `.context-sync.yml`
  ├─ Fetch root ticket from Linear
  ├─ Verify that the root ticket belongs to the configured workspace
  ├─ Add root UUID to the manifest root set if needed
  ├─ Load the full root set from the manifest
  ├─ Recompute the reachable graph from all roots using one bounded reachable set per root
  │
  ├─ Tiered BFS loop:
  │   ├─ For each active root, process one depth frontier at a time
  │   ├─ For frontier tickets at depth N for that root, examine outgoing edges
  │   ├─ Determine edge dimension for each outgoing edge
  │   ├─ Discard edges whose dimension depth is not greater than N
  │   ├─ Bucket remaining edges into traversal tiers:
  │   │   ├─ Tier 1: blocks, is_blocked_by, parent, child
  │   │   ├─ Tier 2: relates_to
  │   │   └─ Tier 3: ticket_ref
  │   ├─ Process tiers in order within that root's depth N frontier
  │   ├─ Within a tier, preserve normal breadth-first frontier order;
  │   │   do not assign an absolute per-relation ranking
  │   ├─ For each target not yet counted for that root and while that root's cap is not reached:
  │   │   ├─ Enqueue target for that root at depth N+1
  │   │   ├─ Record that the root can reach the target
  │   │   └─ Fetch target ticket once globally if it has not already been fetched
  │   └─ Stop expanding a root when its cap is reached; continue other roots
  │
  ├─ For each fetched ticket:
  │   ├─ Update manifest UUID/current-key/path mappings
  │   ├─ Preserve any superseded issue key as a manifest alias
  │   ├─ Rename the local file if the current issue key changed
  │   ├─ Compute and persist the current `refresh_cursor`
  │   └─ Rewrite the ticket file regardless of local freshness
  │
  ├─ Prune derived tickets no longer reachable
  ├─ Update completed snapshot metadata in `.context-sync.yml`
  │
  ├─ Release writer lock
  │
  └─ Return SyncResult
```

This same tiered breadth-first ordering applies whenever `refresh`, `add`, or `remove-root` recomputes reachability from the root set. Cap enforcement is per root, not global across the whole directory. The priority decision happens only at the tier level. Within a single tier, the design intentionally keeps ordinary breadth-first processing of the current frontier rather than assigning an absolute ranking to every individual relation. If one root hits its cap, lower-priority tiers at the current depth and deeper levels may be omitted for that root, while other roots continue traversing under their own budgets.

### 6.2 Refresh Flow

```
refresh()
  │
  ├─ Attempt atomic writer-lock acquisition for context_dir
  ├─ If a lock record already exists: inspect lock metadata
  ├─ If the recorded writer is active: fail fast
  ├─ If the lock is demonstrably stale: preempt it and continue
  ├─ Else: fail with an explicit stale-lock error
  ├─ Load and validate `.context-sync.yml`
  ├─ Read frontmatter from all tracked files in context_dir
  ├─ Load the full root set from the manifest
  ├─ For each manifest root not available in the current visible view:
  │   ├─ If missing_root_policy == "quarantine":
  │   │   ├─ Mark the root quarantined in the manifest
  │   │   ├─ Rewrite the local ticket file so root_state and the
  │   │   │   warning preamble reflect quarantine
  │   │   └─ Record a root_quarantined entry in SyncResult.errors
  │   ├─ Else if missing_root_policy == "remove":
  │   │   ├─ Remove the root from the manifest root set
  │   │   └─ Delete its local file immediately
  │   └─ Continue
  ├─ For each quarantined root visible again during refresh:
  │   ├─ Clear the quarantined state and treat it as active again
  │   └─ Rewrite the local ticket file so the quarantine markers are removed
  ├─ Recompute the reachable graph from active non-quarantined roots
  ├─ Batch-query Linear for the remote composite refresh cursor of each
  │   tracked reachable ticket via `linear-client`
  ├─ Load the local `refresh_cursor` metadata from each tracked reachable
  │   ticket file
  ├─ Treat a tracked reachable ticket as stale when no local file exists, when
  │   the local file's `format_version` predates the accepted
  │   `refresh_cursor` contract, when the local `refresh_cursor` is missing,
  │   partial, or otherwise invalid, or when any composite-cursor component
  │   differs exactly:
  │   ├─ `issue_updated_at`
  │   ├─ `comments_signature`
  │   └─ `relations_signature`
  ├─ Do not treat attachment-only metadata drift as part of the v1 selective
  │   refresh cursor
  │
  ├─ For each stale or newly discovered reachable ticket:
  │   ├─ Re-fetch full ticket data
  │   ├─ Update manifest UUID/current-key/path mappings
  │   ├─ Preserve any superseded issue key as a manifest alias
  │   ├─ Rename the local file if the current issue key changed
  │   └─ Rewrite file
  │
  ├─ Prune derived tickets no longer reachable
  ├─ Update completed snapshot metadata in `.context-sync.yml`
  │
  ├─ Release writer lock
  │
  └─ Return SyncResult
```

The live validation outcome recorded in
[docs/design/refresh-freshness-validation.md](refresh-freshness-validation.md)
invalidated the earlier single-cursor design: issue-level `updated_at` is not
enough to keep persisted comments fresh. The first-release `refresh` contract
therefore uses a per-ticket composite cursor rather than comparing remote
issue timestamps against local `last_synced_at`.

The v1 composite cursor has three components:

- `issue_updated_at`: the issue-level timestamp used for native issue fields
  rendered in the ticket file, including description and other persisted
  issue metadata.
- `comments_signature`: a deterministic digest computed locally from the
  visible comment/thread metadata that can change the rendered comments
  section. The design does not assume Linear returns this digest directly. For
  v1, this signature is SHA-256 over canonical UTF-8 records encoded as
  lower-case hexadecimal with a mandatory `v1:` prefix. The canonical input has
  two record types:
  `thread|<root_comment_id>|resolved=<bool>` for each visible thread and
  `comment|<comment_id>|root=<root_comment_id>|parent=<parent_or_none>|updated_at=<timestamp>|deleted=<bool_or_unknown>`
  for each visible comment. Sort thread records lexicographically by stable
  root-comment ID and sort comment records lexicographically by stable comment
  ID before hashing. If the remote metadata exposes deleted or tombstoned
  comments, include that deletion state in the canonical input as well. If no
  reliable deletion signal exists, deletion detection is best effort through
  visible-set changes and disappearing stable IDs.
- `relations_signature`: a deterministic digest over the visible persisted
  issue relations used by the snapshot and traversal logic. The canonical
  input must include the relation dimension, relation type, and target
  identity. For v1, this signature uses the same SHA-256 / UTF-8 /
  lower-case-hex / mandatory-`v1:` format as `comments_signature`; canonical
  relation records are sorted lexicographically by relation dimension, relation
  type, stable target UUID when available, and then rendered target key. The
  current human-readable target key must still be included in the canonical
  record because that value is rendered locally.

Each ticket file stores the last accepted remote cursor in frontmatter under a
machine-readable `refresh_cursor` mapping. `refresh` compares the remote and
local composite cursors by exact equality. A mismatch in any component marks
the ticket stale and forces a full re-fetch. `last_synced_at` remains useful
for humans and logs, but it is no longer the correctness check for deciding
whether a tracked ticket is fresh.

The `v1:` prefix is normative. It versions the signature-canonicalization
contract independently from file `format_version`, so a future release may
change the digest input rules without overloading the broader on-disk file
schema version. Any mutating flow that writes a ticket file must persist the
current `refresh_cursor` for that file. If a tracked file's `refresh_cursor` is
missing, partial, invalid, or from a file format too old to satisfy the
accepted cursor contract, `refresh` must treat that file as not fresh and
re-fetch it rather than trying to prove freshness from incomplete local data.
Only unrecoverable file corruption that prevents resolving the tracked ticket
identity should be treated as a validation error instead of a stale-file case.

This amendment intentionally does **not** assume that relation changes advance
the parent issue `updated_at`. No additional live relation probe was run as
part of this ticket, so the first release takes the conservative path:
relations get their own cursor component and must be compared explicitly.

Attachment metadata stays persisted in the main ticket file, but attachment-
only drift is not part of the v1 selective-refresh correctness contract. A
ticket re-fetch caused by another cursor component will still refresh
attachments opportunistically, while richer attachment freshness handling
remains deferred to [FW-2](<../future-work.md#fw-2-attachment-content-handling>).

The resulting remote-data requirement for
[M1-D2](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary)
is explicit. The refresh adapter must be able to obtain, in one logical
batched metadata pass across the tracked reachable set:

- issue identity plus issue `updated_at` for native-field freshness
- comment/thread metadata sufficient to build `comments_signature` without
  downloading full comment bodies during the freshness pass
- relation metadata sufficient to build `relations_signature`

That batched metadata pass may be implemented as one composite operation or as
a small fixed set of batched subqueries behind one narrow adapter boundary, but
it must not degrade into one full ticket fetch per tracked issue just to decide
freshness.

If
[M1-D2](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary)
finds that the available Linear surface cannot provide metadata-only comment
freshness inputs, it should record that explicitly as an adapter or design risk
rather than silently widening the freshness pass into full comment downloads.

Adding a new root to an existing context directory should use this same
whole-snapshot refresh flow after recording the new root. The design
intentionally avoids root-local refresh because overlapping root graphs would
otherwise produce mixed-time snapshots. The `missing_root_policy` knob applies
only to already-tracked roots during `refresh`; it does not weaken the strict
behavior of `sync` or `add` for explicitly requested roots.

The first release does not treat a richer activity or history timeline as part of this base refresh contract. If that data is added later, it may need its own persistence shape and freshness semantics as described in [FW-5](<../future-work.md#fw-5-ticket-history-and-sectioned-ticket-artifacts>).

### 6.3 Add Flow

```
add(ticket_ref)
  │
  ├─ Attempt atomic writer-lock acquisition for context_dir
  ├─ If a lock record already exists: inspect lock metadata
  ├─ If the recorded writer is active: fail fast
  ├─ If the lock is demonstrably stale: preempt it and continue
  ├─ Else: fail with an explicit stale-lock error
  ├─ Load or initialize `.context-sync.yml`
  ├─ Normalize ticket_ref (issue key or Linear issue URL)
  ├─ Attempt local resolution through the manifest alias table
  ├─ If ticket_ref is a URL and its workspace slug mismatches the manifest:
  │   └─ fail fast
  ├─ Fetch the referenced ticket from Linear if local alias lookup is insufficient
  ├─ Verify that the ticket workspace matches the manifest workspace
  ├─ Add the ticket UUID to the manifest root set
  ├─ Execute the whole-snapshot refresh steps under the same writer lock
  ├─ Release writer lock
  │
  └─ Return SyncResult
```

### 6.4 Diff Flow

```
diff()
  │
  ├─ Check for writer lock on context_dir
  ├─ If a lock record exists: inspect lock metadata
  ├─ If the lock is not demonstrably stale:
  │   └─ Fail fast with a clear lock-contention error
  ├─ Else: continue without modifying the lock
  ├─ Load and validate `.context-sync.yml`
  ├─ Read frontmatter from all tracked files in context_dir
  ├─ Fetch current state from Linear for each tracked ticket
  │
  ├─ For each ticket:
  │   ├─ Compare local fields vs remote fields
  │   ├─ Classify as current / stale / missing_locally / missing_remotely
  │   │   where missing_remotely means not available in the current visible view
  │   │   without distinguishing deletion from permission loss
  │   └─ Record changed fields if stale
  │
  └─ Return DiffResult (no files modified)
```

`diff` never changes manifest root state. If a tracked root is unavailable, `diff` reports it as `missing_remotely` just like any other unavailable tracked ticket. Whether that root should later be quarantined or removed is a separate `refresh` decision controlled by `missing_root_policy`.

### 6.5 Remove-Root Flow

```
remove_root(ticket_ref)
  │
  ├─ Attempt atomic writer-lock acquisition for context_dir
  ├─ If a lock record already exists: inspect lock metadata
  ├─ If the recorded writer is active: fail fast
  ├─ If the lock is demonstrably stale: preempt it and continue
  ├─ Else: fail with an explicit stale-lock error
  ├─ Load and validate `.context-sync.yml`
  ├─ Normalize ticket_ref (issue key or Linear issue URL)
  ├─ Resolve the referenced ticket UUID through the manifest alias table
  ├─ Verify that the ticket UUID is currently in the manifest root set
  ├─ Remove the ticket UUID from the manifest root set
  ├─ Execute the whole-snapshot refresh steps under the same writer lock
  ├─ Release writer lock
  │
  └─ Return SyncResult
```

The first release does not guarantee whole-directory atomic commit for these flows. If a process is interrupted mid-run, the directory may contain a mix of files from the previous snapshot and the current in-progress pass, even though no individual file is left partially written.

---

## 7. Risks and Mitigations (Tool-Specific)

### R1: Silent Bad Context

**Risk**: A bug in the Markdown serializer produces incorrect or incomplete ticket data. The agent acts on bad context without knowing it.

**Mitigation**:
- The tool includes a lightweight **verification step**: after writing each file, re-parse it and verify critical fields plus required `context-sync:` structural markers against the in-memory rendered data. Treat verification mismatch as a write failure.
- Format versioning (`format_version: 1` in frontmatter) enables detection of old-format files and automatic re-sync.
- Human review: anyone can checkout the branch and read the files. Bad context is visible, not hidden in an API call trace.

### R2: Partial Sync Leaves Inconsistent State

**Risk**: The tool fetches 8 of 10 tickets successfully, then fails on 2. The context directory has an incomplete graph.

**Mitigation**:
- `SyncResult` reports errors explicitly. The caller decides whether to proceed or abort.
- File writes are atomic (write to temp file, rename) so a crash mid-write does not leave a corrupted file.
- Missing tickets are identifiable: the root ticket's frontmatter lists its relations, and a validation step can check whether all referenced tickets have corresponding files.
