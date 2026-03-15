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
        max_tickets: int = 200,
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

    async def refresh(self) -> SyncResult: ...

    async def diff(self) -> DiffResult: ...

# Initial sync: dump the root ticket plus its reachable neighborhood
result = await syncer.sync(root_ticket_id="ACP-123", max_tickets=200)

# Delta refresh: update stale files in place
result = await syncer.refresh()

# Expand with a newly discovered ticket by issue key or Linear URL,
# then run whole-snapshot refresh semantics across all roots
result = await syncer.add(ticket_ref="ACP-999")

# Remove a root, then run whole-snapshot refresh semantics across all roots
result = await syncer.remove_root(ticket_ref="ACP-999")

# Compare local files to Linear without modifying anything
result = await syncer.diff()
```

Caller-facing inputs continue to use familiar issue keys or Linear issue URLs for ergonomics. Internally, once a ticket is resolved, the stable Linear UUID becomes the authoritative identity used for deduplication, root membership, and issue-key-change handling.

Traversal semantics and interface rationale live in [docs/adr.md](<../adr.md>).

---

## 2. CLI Interface

For human use and shell invocation:

```bash
# Initial sync
context-sync sync ACP-123 --max-tickets 200 --context-dir linear-context \
  --depth-blocks 3 --depth-is-blocked-by 2 --depth-parent 2 \
  --depth-child 2 --depth-relates-to 1 --depth-ticket-ref 1

# Delta refresh all
context-sync refresh --context-dir linear-context

# Expand with a newly discovered root, then refresh the whole snapshot
context-sync add ACP-999 --context-dir linear-context

# Remove a root, then refresh the whole snapshot
context-sync remove-root ACP-999 --context-dir linear-context

# Diff against Linear's live state
context-sync diff --context-dir linear-context --json
```

The CLI is a thin wrapper over the async library API, using `asyncio.run()` as the entry point. All logic lives in the library layer.

Each invocation operates on exactly one `context_dir`. Running the tool against multiple directories is supported only by making separate invocations; the tool does not route work across directories on the caller's behalf.

Parallel invocations against different context directories are allowed. They may still contend on shared upstream Linear rate limits, but the first release does not add any cross-process coordination layer on top of `linear-client`.

Each `context_dir` is scoped to one Linear workspace. Tickets from multiple teams in that workspace may coexist in the same snapshot. Roots from a different workspace are rejected before any mutation occurs.

### 2.1 Context Directory Contents

For the first release, a context directory contains:

- ticket snapshot files such as `ACP-123.md`;
- `.context-sync.yml`, a small manifest file;
- `.context-sync.lock`, a transient writer-lock file that exists only while a mutating operation is active.

The manifest is the authoritative directory-level metadata file. It stores:

- the context format version;
- the bound Linear workspace identity, including stable workspace ID and workspace slug;
- the current root-ticket set, keyed by stable ticket UUID;
- a ticket lookup table that maps stable ticket UUIDs to current issue keys and current file paths;
- a key-alias table that maps locally known current and previous issue keys back to stable ticket UUIDs;
- snapshot-pass metadata, including the last completed snapshot mode and timestamps for the most recent completed pass.

This design keeps v1 simple. We do not introduce a separate general-purpose index file beyond the manifest. The manifest already answers the important directory-level questions quickly: which workspace does this snapshot belong to, which tickets are roots, and which locally tracked ticket does a current or previously observed issue key refer to?

Because the manifest is authoritative for roots, deleting a ticket file by hand is not a supported way to remove a root. If the ticket remains in the manifest root set, a later refresh may recreate the file.

Ticket files remain named by the current human-facing issue key for readability. The stable Linear UUID is the authoritative identity used for deduplication, root membership, and issue-key-change handling. When the tool observes that a tracked ticket's current issue key changed, it renames the local file and preserves the previous key in the manifest alias table so local agents can still resolve old references offline. The concrete documented reason for this today is that a Linear issue can move to another team in the same workspace and receive a new issue ID. More generally, the implementation should treat any upstream reassignment of the human-facing issue key the same way.

That offline alias support is intentionally bounded in v1. The tool can preserve issue-key-change history only from the point it starts tracking a ticket unless the API itself exposes older aliases; importing such historical aliases is deferred to [FW-4](<../future-work.md#fw-4-historical-ticket-alias-import>).

### 2.2 Ticket File Rendering

Ticket files are rendered deterministically. YAML mapping keys are emitted in lexicographic order at each nesting level, optional empty values are omitted, and timestamps are normalized to UTC RFC3339 with `Z`. List element order follows the specific normalization rules for that collection type.

Labels are rendered as a single display string. If a label group exists, the stored string is `<group> / <label>`; otherwise it is just `<label>`. Labels are sorted lexicographically by that full rendered string.

The body has a fixed section order:

1. description
2. comments

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
    removed: list[str]       # current issue keys of derived files pruned
    errors: list[SyncError]  # tickets that could not be fetched

@dataclass
class SyncError:
    ticket_id: str           # current issue key for reporting
    error_type: str          # e.g., "not_found", "permission_denied", "api_error"
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
| Existing manifest root is not available during `refresh` | Raise immediately; do not auto-remove the root from the manifest |
| Linked ticket fetch fails unexpectedly while the broader run is still healthy | Write all successful tickets; include failed ticket in `errors` |
| Systemic remote failure (workspace access lost, invalid auth, lost network access, retry-exhausted `5xx`) | Abort immediately and stop further edits; a partial snapshot may remain if the failure happens mid-run |
| Linear API rate limit | Let `linear-client` perform retry/backoff; if retries are exhausted, treat it as a systemic remote failure |
| Context directory does not exist | Create it |
| Context directory already locked by a writer | Fail fast with a clear error; do not wait indefinitely |
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
- **CLI mode**: Reads the same environment variables as `linear-client` (`LINEAR_CLIENT_ID`, `LINEAR_CLIENT_SECRET`, etc.) and constructs its own client.

---

## 6. Internal Data Flow

### 6.1 Sync Flow

```
sync(root_ticket_id, max_tickets, dimensions)
  │
  ├─ Acquire exclusive writer lock for context_dir
  ├─ Load or initialize `.context-sync.yml`
  ├─ Fetch root ticket from Linear
  ├─ Verify that the root ticket belongs to the configured workspace
  ├─ Add root UUID to the manifest root set if needed
  ├─ Load the full root set from the manifest
  ├─ Recompute the reachable graph from all roots
  │
  ├─ BFS loop:
  │   ├─ Dequeue ticket at depth N
  │   ├─ For each outgoing edge (relation, parent/child, ticket_ref):
  │   │   ├─ Determine edge dimension
  │   │   ├─ If dimension depth > N and target not visited and cap not reached:
  │   │   │   ├─ Enqueue target at depth N+1
  │   │   │   └─ Fetch target ticket (TaskGroup + semaphore-limited worker)
  │   │   └─ Else: skip
  │   └─ Continue until queue empty or cap reached
  │
  ├─ For each fetched ticket:
  │   ├─ Update manifest UUID/current-key/path mappings
  │   ├─ Preserve any superseded issue key as a manifest alias
  │   ├─ Rename the local file if the current issue key changed
  │   └─ Rewrite the ticket file regardless of local freshness
  │
  ├─ Prune derived tickets no longer reachable
  ├─ Update completed snapshot metadata in `.context-sync.yml`
  │
  ├─ Release writer lock
  │
  └─ Return SyncResult
```

### 6.2 Refresh Flow

```
refresh()
  │
  ├─ Acquire exclusive writer lock for context_dir
  ├─ Load and validate `.context-sync.yml`
  ├─ Read frontmatter from all tracked files in context_dir
  ├─ Load the full root set from the manifest
  ├─ Verify that every manifest root is available in the current visible view
  │   before rewriting local files; fail immediately if any root is unavailable
  ├─ Recompute the reachable graph from all roots
  ├─ Batch-query Linear for per-ticket updated_at values via `linear-client`
  ├─ Treat issue-level updated_at as the freshness cursor for the v1
  │   base ticket snapshot (metadata, description, comments)
  ├─ Before treating this design as correct, validate that issue-level
  │   updated_at advances when any of those v1-persisted fields change,
  │   especially when comments are added or edited
  │
  ├─ For each reachable ticket where updated_at > last_synced_at
  │   │  or where no local file exists:
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

Adding a new root to an existing context directory should use this same whole-snapshot refresh flow after recording the new root. The design intentionally avoids root-local refresh because overlapping root graphs would otherwise produce mixed-time snapshots.

The first release does not treat a richer activity or history timeline as part of this base refresh contract. If that data is added later, it may need its own persistence shape and freshness semantics as described in [FW-5](<../future-work.md#fw-5-ticket-history-and-sectioned-ticket-artifacts>).

### 6.3 Add Flow

```
add(ticket_ref)
  │
  ├─ Acquire exclusive writer lock for context_dir
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
  ├─ Check for active writer lock on context_dir
  ├─ If a writer is active: fail fast with a clear message
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

### 6.5 Remove-Root Flow

```
remove_root(ticket_ref)
  │
  ├─ Acquire exclusive writer lock for context_dir
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
