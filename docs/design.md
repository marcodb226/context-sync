# Tool Design: Linear Context Sync — Implementation Design

> **Status**: Draft
> **Date**: 2026-03-13
> **Context**: Forked from the agent-control-plane repo

---

## 1. Library API

The primary interface is an async Python class that receives an authenticated `Linear` client and a target directory:

```python
from linear_context_sync import ContextSyncer

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
        ticket_id: str,
    ) -> SyncResult: ...

    async def refresh(self) -> SyncResult: ...

    async def diff(self) -> DiffResult: ...

# Initial sync: dump the root ticket plus its reachable neighborhood
result = await syncer.sync(root_ticket_id="ACP-123", max_tickets=200)

# Delta refresh: update stale files in place
result = await syncer.refresh()

# Expand with a newly discovered ticket by adding it as a root,
# then run whole-snapshot refresh semantics across all roots
result = await syncer.add(ticket_id="ACP-999")

# Compare local files to Linear without modifying anything
result = await syncer.diff()
```

Traversal semantics and interface rationale live in [adr.md](<adr.md>).

---

## 2. CLI Interface

For human use and shell invocation:

```bash
# Initial sync
linear-context-sync sync ACP-123 --max-tickets 200 --context-dir linear-context \
  --depth-blocks 3 --depth-is-blocked-by 2 --depth-parent 2 \
  --depth-child 2 --depth-relates-to 1 --depth-ticket-ref 1

# Delta refresh all
linear-context-sync refresh --context-dir linear-context

# Expand with a newly discovered root, then refresh the whole snapshot
linear-context-sync add ACP-999 --context-dir linear-context

# Diff against Linear's live state
linear-context-sync diff --context-dir linear-context --json
```

The CLI is a thin wrapper over the async library API, using `asyncio.run()` as the entry point. All logic lives in the library layer.

---

## 3. Return Contracts

### 3.1 SyncResult

```python
@dataclass
class SyncResult:
    created: list[str]       # ticket IDs of newly created files
    updated: list[str]       # ticket IDs of files that were refreshed
    unchanged: list[str]     # ticket IDs of files that were fresh (skipped)
    removed: list[str]       # ticket IDs of derived files pruned (no longer reachable from any root)
    errors: list[SyncError]  # tickets that could not be fetched

@dataclass
class SyncError:
    ticket_id: str
    error_type: str          # e.g., "not_found", "permission_denied", "api_error"
    message: str
    retriable: bool
```

### 3.2 DiffResult

```python
@dataclass
class DiffEntry:
    ticket_id: str
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
| Linear API rate limit | Respect retry-after; back off; continue |
| Context directory does not exist | Create it |
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
  ├─ Fetch root ticket from Linear
  ├─ Add root to the tracked root set if needed
  ├─ Load any existing roots from the context directory
  ├─ Recompute the reachable graph from all roots
  │
  ├─ BFS loop:
  │   ├─ Dequeue ticket at depth N
  │   ├─ For each outgoing edge (relation, parent/child, ticket_ref):
  │   │   ├─ Determine edge dimension
  │   │   ├─ If dimension depth > N and target not visited and cap not reached:
  │   │   │   ├─ Enqueue target at depth N+1
  │   │   │   └─ Fetch target ticket (concurrent, semaphore-limited)
  │   │   └─ Else: skip
  │   └─ Continue until queue empty or cap reached
  │
  ├─ For each fetched ticket:
  │   └─ Rewrite the ticket file regardless of local freshness
  │
  ├─ Prune derived tickets no longer reachable
  │
  └─ Return SyncResult
```

### 6.2 Refresh Flow

```
refresh()
  │
  ├─ Read frontmatter from all tracked files in context_dir
  ├─ Load the full root set
  ├─ Recompute the reachable graph from all roots
  ├─ Batch-query Linear for per-ticket updated_at values via `linear-client`
  │
  ├─ For each reachable ticket where updated_at > last_synced_at
  │   │  or where no local file exists:
  │   ├─ Re-fetch full ticket data
  │   └─ Rewrite file
  │
  ├─ Prune derived tickets no longer reachable
  │
  └─ Return SyncResult
```

Adding a new root to an existing context directory should use this same whole-snapshot refresh flow after recording the new root. The design intentionally avoids root-local refresh because overlapping root graphs would otherwise produce mixed-time snapshots.

### 6.3 Diff Flow

```
diff()
  │
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
