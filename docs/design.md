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
    linear=linear_client_instance,   # reuse the caller's authenticated client
    context_dir=Path("/work/repo/linear-context"),
)

# Initial sync: dump ticket + graph neighborhood
result = await syncer.sync(
    root_ticket_id="ACP-123",
    depth=3,
    max_tickets=200,
)
# result: SyncResult(created=["ACP-123", "ACP-120", ...], updated=[], unchanged=[], errors=[])

# Delta refresh: update stale files
result = await syncer.refresh()
# Checks all files in context_dir, updates those where updated_at > last_synced_at

# Targeted refresh: refresh specific ticket(s) before a write operation
result = await syncer.refresh(tickets=["ACP-123"])

# Expand: add new tickets discovered during execution
result = await syncer.sync(
    root_ticket_id="ACP-999",
    depth=2,
    max_tickets=50,
)
# Skips tickets already present and fresh
```

See [cr-tool-problem-statement.md](cr-tool-problem-statement.md) F6 for the full method signatures and dimension configuration.

---

## 2. CLI Interface

For human use and shell invocation:

```bash
# Initial sync
linear-context-sync sync ACP-123 --depth 3 --max-tickets 200 --context-dir linear-context

# Delta refresh all
linear-context-sync refresh --context-dir linear-context

# Targeted refresh
linear-context-sync refresh --tickets ACP-123,ACP-120 --context-dir linear-context

# Expand with new root
linear-context-sync sync ACP-999 --depth 2 --context-dir linear-context

# Dry run (show what would change)
linear-context-sync sync ACP-123 --depth 3 --dry-run

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
  ├─ Mark root at depth 0
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
  │   ├─ If file exists and fresh (updated_at <= last_synced_at): skip
  │   ├─ If file exists and stale: rewrite
  │   └─ If no file: write new
  │
  ├─ Prune derived tickets no longer reachable
  │
  └─ Return SyncResult
```

### 6.2 Refresh Flow

```
refresh(tickets=None)
  │
  ├─ If tickets specified: scope = those tickets
  │  Else: scope = all files in context_dir
  │
  ├─ Read frontmatter from each file in scope
  ├─ Batch-query Linear for updated_at values (single GraphQL call, see TQ-1 in tool-adr.md)
  │
  ├─ For each ticket where updated_at > last_synced_at:
  │   ├─ Re-fetch full ticket data
  │   └─ Rewrite file
  │
  ├─ Recompute reachable graph from all roots
  ├─ Prune derived tickets no longer reachable
  │
  └─ Return SyncResult
```

### 6.3 Diff Flow

```
diff(tickets=None)
  │
  ├─ If tickets specified: scope = those tickets
  │  Else: scope = all files in context_dir
  │
  ├─ Read frontmatter from each file in scope
  ├─ Fetch current state from Linear for each ticket
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
