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

Traversal semantics and interface rationale live in [adr.md](<adr.md>).

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

Ticket files remain named by the current human-facing issue key for readability. The stable Linear UUID is the authoritative identity used for deduplication, root membership, and issue-key-change handling. When the tool observes that a tracked ticket's current issue key changed, it renames the local file and preserves the previous key in the manifest alias table so local agents can still resolve old references offline. That includes the documented case where a Linear issue is moved to another team in the same workspace and receives a new issue ID.

That offline alias support is intentionally bounded in v1. The tool can preserve issue-key-change history only from the point it starts tracking a ticket unless the API itself exposes older aliases; importing such historical aliases is deferred to [FW-4](<future-work.md#fw-4-historical-ticket-alias-import>).

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

Errors are handled per-ticket. The tool never raises for a single linked-ticket failure; it completes the sync and reports errors in `SyncResult`.

| Scenario | Tool behavior |
|---|---|
| Root ticket fetch fails | Raise immediately — no meaningful partial result without the root |
| Linked ticket fetch fails | Write all successful tickets; include failed ticket in `errors` |
| Linear API rate limit | Let `linear-client` perform retry/backoff; surface the slowdown clearly in logs/results |
| Context directory does not exist | Create it |
| Context directory already locked by a writer | Fail fast with a clear error; do not wait indefinitely |
| Root ticket belongs to a different workspace than the current snapshot | Raise before mutating the context directory |
| `add` is given a Linear URL whose workspace slug clearly mismatches the manifest | Fail fast before the full refresh flow |
| `remove-root` targets a ticket that is not in the manifest root set | Fail fast with a clear error |
| Process interrupted mid-run | No partial file writes, but the directory may still contain a partially applied snapshot update |
| File write permission error | Raise exception |

The caller (agent loop or human) decides how to handle the `SyncResult`:
- Root failure → abort context reconstruction
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
  ├─ Recompute the reachable graph from all roots
  ├─ Batch-query Linear for per-ticket updated_at values via `linear-client`
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
- The tool includes a **verification step**: after writing each file, re-parse it and compare key fields against the API response. Log discrepancies.
- Format versioning (`format_version: 1` in frontmatter) enables detection of old-format files and automatic re-sync.
- Human review: anyone can checkout the branch and read the files. Bad context is visible, not hidden in an API call trace.

### R2: Partial Sync Leaves Inconsistent State

**Risk**: The tool fetches 8 of 10 tickets successfully, then fails on 2. The context directory has an incomplete graph.

**Mitigation**:
- `SyncResult` reports errors explicitly. The caller decides whether to proceed or abort.
- File writes are atomic (write to temp file, rename) so a crash mid-write does not leave a corrupted file.
- Missing tickets are identifiable: the root ticket's frontmatter lists its relations, and a validation step can check whether all referenced tickets have corresponding files.
