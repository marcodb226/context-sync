# Problem Statement: Linear Context Sync Tool

> **Status**: Draft
> **Date**: 2026-03-13
> **Prerequisites**: [cr-adr.md](cr-adr.md), [cr-design.md](cr-design.md)

---

## 1. Problem

Agents in the control plane need to understand the Linear ticket graph surrounding the ticket they are working on. Today, this understanding is built at runtime through a sequence of Linear API calls — fetch the ticket, fetch its relations, fetch each related ticket — orchestrated by the agent loop. This approach has several problems:

1. **Token cost**: Each API call is a tool invocation that consumes agent tokens (input and output) for the call scaffolding, even though the work is entirely deterministic and does not benefit from model reasoning.

2. **Consistency**: Tickets are fetched sequentially. The state of ticket A at fetch time may not be consistent with the state of ticket B fetched 30 seconds later. There is no transactional snapshot.

3. **Shallow traversal**: The agent loop currently traverses only one hop from the claimed ticket. Deeper context (what blocks my blockers? what are my parent's other children?) requires additional API calls that compound problems 1 and 2.

4. **No persistence**: The assembled context is in-memory. On restart, everything is discarded and reconstructed from scratch — the same API calls, the same token cost, the same consistency gaps.

5. **Opacity**: No human can inspect what the agent knows about its ticket graph without adding debugging instrumentation. The context is a runtime object, not an artifact.

6. **No reuse across invocations**: If the agent loop restarts, resumes a ticket, or wants to expand its understanding, it starts from zero. There is no cache, no delta, no incremental update.

---

## 2. Desired Outcome

A tool that materializes Linear ticket data as files on disk, so that:

- Agents read ticket context from local files instead of making runtime API calls.
- The ticket graph is traversed to a configurable depth in a single, bounded operation.
- Files include enough metadata to support incremental updates (only re-fetch tickets that changed).
- The same tool can be used by humans to inspect, validate, or debug the agent's ticket context.
- The tool is reusable across projects and contexts — it is not coupled to the agent control plane's internal architecture.

---

## 3. Scope

### In Scope

- Fetch a Linear ticket and its relation graph to a configurable depth.
- Write each ticket as a Markdown file with structured frontmatter and human-readable body.
- Support incremental updates: compare file metadata against Linear's `updated_at` to determine which files need refreshing.
- Deduplicate: never download a ticket that is already present and fresh.
- Expose an async Python library API for programmatic use.
- Expose a CLI for human use and shell invocation.
- Handle partial failures gracefully: report which tickets succeeded and which failed.
- Authenticate via `linear-client` (reuse existing OAuth infrastructure).

### Out of Scope

- Writing to Linear (status transitions, comments, ticket creation). This tool is read-only.
- Fetching attachment content (images, PDFs). The tool records attachment URLs and metadata; content retrieval is a future extension.
- GitHub integration. This tool operates on Linear data only.
- Agent loop integration details (git commits, pre-PR cleanup, read-only enforcement). Those are the agent control plane's responsibility.
- Webhook-driven real-time sync. This tool is invoked on demand, not event-driven.

---

## 4. Users

### 4.1 Agent Loop (Primary)

The agent control plane's execution loop invokes the tool as a Python library to materialize and refresh ticket context during context reconstruction and execution. The loop provides an authenticated `Linear` client instance; the tool uses it for all API calls.

**Usage patterns**:
- Initial sync at claim time (root ticket + depth 3).
- Delta refresh on restart/resume.
- Targeted refresh before write operations.
- On-demand expansion when the agent discovers references to tickets outside the initial graph.

### 4.2 Human Operator (Secondary)

A human (developer, project owner, debugger) runs the CLI to:
- Inspect the ticket graph for a given ticket without opening Linear's UI.
- Validate what an agent would see for a given ticket.
- Pre-populate a context directory for manual development work.
- Debug agent behavior by comparing the context directory contents against Linear's current state.

### 4.3 CI / Automation (Tertiary)

Scripts or CI steps that need ticket metadata (e.g., a PR bot that annotates PRs with ticket context, a reporting tool that aggregates ticket state).

---

## 5. Functional Requirements

### F1: Per-Dimension Graph Traversal

The tool treats each relationship type as a **graph dimension** with its own configurable traversal depth. Given a root ticket identifier and a dimension depth configuration:

1. Fetch the root ticket's full data from Linear. The root is at depth 0.
2. Identify all tickets related to the root and classify each relation into its dimension (`blocks`, `is_blocked_by`, `parent`, `child`, `relates_to`).
3. Additionally, scan the root ticket's description and comments for Linear ticket URLs. Tickets discovered this way belong to the `ticket_ref` dimension.
4. For each discovered ticket at depth N, the edge is followed only if the edge's dimension has a configured depth > N.
5. Traverse in **breadth-first order** from all roots simultaneously. Depth-1 tickets are processed before depth-2, etc.
6. If a ticket is reachable from multiple roots or via multiple paths, its effective depth is the **shortest distance from any root**.
7. Stop traversal when all dimensions are exhausted at all depth levels, or the maximum ticket count cap is reached, whichever comes first.
8. Return the set of fetched tickets and any errors encountered.

**Dimension depth configuration** (proposed defaults):

| Dimension | Default depth | Description |
|---|---|---|
| `blocks` | 3 | Tickets that block the current ticket (most operationally critical) |
| `is_blocked_by` | 2 | Tickets that the current ticket blocks |
| `parent` | 2 | Parent ticket |
| `child` | 2 | Child tickets |
| `relates_to` | 1 | Informational relations |
| `ticket_ref` | 1 | Ticket URLs found in comments or description |

Dimensions can be disabled by setting depth to 0. Defaults are overridable via configuration (library constructor or CLI flags).

**Custom dimensions**: The built-in dimension set covers Linear's current relation types and ticket-level URL scanning. The dimension model should be extensible — adding a new dimension should require only configuration, not changes to the traversal engine. The `DimensionConfig` should accept arbitrary dimension names with integer depths rather than being a fixed set of hardcoded fields. Custom dimension support is deferred to a later release; the first version ships with the built-in set. See cr-adr.md D1 for the full rationale.

**`ticket_ref` scope**: The `ticket_ref` dimension covers ticket URLs found **within other tickets** (descriptions and comment bodies). It does not cover ticket URLs found in repository documents. When the agent discovers a ticket URL in a repo file (code comment, Markdown doc, etc.), the correct action is to call `add` with that ticket ID, making it a root. A future `doc_ref` dimension could automate repository file scanning, but that is a separate capability requiring a different input surface (file paths rather than Linear API responses).

**Depth model — total hops from root**: The tool counts total hops from the nearest root, regardless of edge type. A ticket at depth N can have its outgoing edges followed only for dimensions whose configured depth is greater than N. This means the depth number for a dimension answers: "how many total hops from root am I willing to cross this type of edge?" See cr-adr.md D1 for a worked example and the rationale for choosing total-hops over per-dimension counting.

**Traversal order and ticket cap**: BFS from all roots simultaneously. Depth-1 tickets are visited before depth-2 before depth-3. If the cap is reached mid-traversal, the tool stops with what it has. This ensures the nearest, most diverse neighborhood is covered first — close tickets across all dimensions before distant tickets along only high-depth dimensions. The cap is a safety bound; users adjust dimension depths for fine-grained control.

**`ticket_ref` detection**: The tool scans Markdown text (ticket description + comment bodies) for patterns matching Linear ticket URLs (e.g., `https://linear.app/<workspace>/issue/<ID>`). Discovered references are treated as `ticket_ref` dimension edges, subject to the same total-hops depth rules as any other dimension.

**Explicit addition**: The tool supports adding a specific ticket by ID with a specified traversal depth, independent of graph discovery. This covers tickets the agent finds while navigating repository documentation, code, or other non-Linear sources. Explicitly-added tickets are marked as **root** tickets (see below).

**Root vs. derived tickets**: Every ticket in the context directory is classified as either **root** or **derived**:

- **Root tickets** (`root: true` in frontmatter) are tickets that were explicitly requested — the initial ticket passed to `sync`, or any ticket added via `add`. Root tickets are pinned and never auto-removed by the tool.
- **Derived tickets** (`root: false`) entered the context directory because they were discovered during graph traversal from a root. They exist because they are reachable from at least one root within the configured dimension depths.

This distinction is essential for correct depth counting: traversal depth is always measured as total hops from the nearest root. A ticket's effective depth is the shortest distance from any root. Outgoing edges are gated by whether the edge's dimension depth exceeds the ticket's effective depth.

**File lifecycle**: On a full sync or delta refresh, the tool recomputes the reachable graph from all current root tickets using the active dimension configuration. After recomputation:

- Root tickets are never removed. They are refreshed if stale.
- Derived tickets that are still reachable from at least one root are kept and refreshed if stale.
- Derived tickets that are no longer reachable from any root are removed from the context directory.

This means dimension depth reductions *can* cause derived ticket files to disappear, but root tickets are always safe. The `SyncResult` reports removed tickets explicitly.

**Traversal provenance (optional)**: By default, frontmatter records only the `root` flag. When a debug/verbose mode is enabled, the tool additionally records provenance metadata for derived tickets: which root they were reached from, via which dimension, at what depth. This is useful for debugging traversal behavior but is not required for correct operation.

**Cycle safety**: Tickets already visited within a single sync invocation are not re-fetched, regardless of which dimension reaches them.

### F2: File Output

For each fetched ticket, write a Markdown file:
- **Filename**: `<ticket-identifier>.md` (e.g., `ACP-123.md`).
- **Frontmatter** (YAML): Structured metadata including ticket ID, title, status, assignee, creator, labels, priority, timestamps (`created_at`, `updated_at`, `last_synced_at`), format version, `root` flag (true for pinned/explicitly-requested tickets, false for graph-derived tickets), parent ticket, relations list (with dimension annotations), and attachment metadata.
- **Body**: Ticket description in Markdown.
- **Comments section**: All comments in chronological order, each with author, timestamp, and body.

The file must be self-contained: reading it provides all the information the tool fetched for that ticket, without needing to cross-reference other files (though relation fields reference other ticket IDs that may have their own files).

### F3: Incremental Update (Delta Sync)

When invoked against a context directory that already contains ticket files:
1. Identify all root tickets in the context directory (files with `root: true`).
2. Recompute the reachable graph from all roots using the active dimension configuration.
3. For each existing file, read `last_synced_at` from frontmatter.
4. Query Linear for the ticket's current `updated_at`.
5. If `updated_at > last_synced_at`, re-fetch the ticket and rewrite the file.
6. If `updated_at <= last_synced_at`, skip the file.
7. For tickets discovered in the relation graph that have no corresponding file, fetch and write them.
8. **Prune**: Remove derived tickets (`root: false`) that are no longer reachable from any root within current dimension depths.
9. Report what was created, updated, unchanged, removed, and errored.

The delta check must be efficient: ideally a single batched query for `updated_at` values rather than individual fetches per ticket. Root tickets are never removed during pruning.

### F4: Targeted Refresh

Refresh a specific subset of tickets (by identifier) without touching others. Used by the agent loop before write operations to ensure it is acting on current state.

### F5: Diff Mode

Compare the current context directory against Linear's live state without modifying any files. For each tracked ticket, report whether its local file is current, stale, or missing from Linear. For stale tickets, show which fields changed (status, assignee, description, new comments, etc.).

This mode serves two purposes:
- **Human debugging**: A human inspecting an agent's working branch can run `diff` to see exactly where the agent's snapshot diverges from Linear's current state, without triggering a sync.
- **Pre-sync validation**: The agent loop (or a human) can check what *would* change before committing to a refresh, supporting a dry-run workflow.

Output contract:

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

For CLI output, diff results are printed in a human-readable format (ticket ID, status, changed fields). A `--json` flag provides machine-readable output.

### F6: Async Library API

The primary interface is an async Python API:

```python
# Built-in defaults; additional dimensions can be added by name.
# DimensionConfig is a dict[str, int] (dimension name → depth), not a fixed dataclass,
# to support future custom dimensions without code changes to the traversal engine.
DIMENSION_DEFAULTS: dict[str, int] = {
    "blocks": 3,
    "is_blocked_by": 2,
    "parent": 2,
    "child": 2,
    "relates_to": 1,
    "ticket_ref": 1,
}

class ContextSyncer:
    def __init__(
        self,
        linear: Linear,
        context_dir: Path,
        dimensions: dict[str, int] | None = None,  # None = use DIMENSION_DEFAULTS
    ): ...

    async def sync(
        self,
        root_ticket_id: str,
        max_tickets: int = 200,
        dimensions: dict[str, int] | None = None,  # override instance defaults for this call
    ) -> SyncResult: ...

    async def add(
        self,
        ticket_id: str,
        depth: int = 1,           # traversal depth from this ticket
    ) -> SyncResult: ...

    async def refresh(
        self,
        tickets: list[str] | None = None,  # None = refresh all files in context_dir
    ) -> SyncResult: ...

    async def diff(
        self,
        tickets: list[str] | None = None,  # None = diff all files in context_dir
    ) -> DiffResult: ...
```

The `Linear` client is injected, not constructed internally. This allows the caller to control authentication, connection pooling, and lifecycle.

The `add` method supports agent-initiated expansion: the agent discovers a ticket reference while reading documentation or code and asks the tool to bring it into the context directory. Unlike `sync`, `add` does not require a full dimension configuration — it takes a simple depth parameter and traverses all dimensions uniformly from the added ticket. The ticket is recorded with `source.type: "explicit_add"` in frontmatter.

### F7: CLI

A command-line interface wrapping the library API:

```
linear-context-sync sync <ticket-id> [--max-tickets N] [--context-dir PATH] \
    [--depth-blocks N] [--depth-is-blocked-by N] [--depth-parent N] \
    [--depth-child N] [--depth-relates-to N] [--depth-ticket-ref N]
linear-context-sync add <ticket-id> [--depth N] [--context-dir PATH]
linear-context-sync refresh [--tickets ID,...] [--context-dir PATH]
linear-context-sync status [--context-dir PATH]     # show summary of current context state
linear-context-sync diff [--tickets ID,...] [--context-dir PATH] [--json]  # show what changed vs Linear
```

The CLI handles its own authentication (reads environment variables, constructs a `Linear` client) and calls `asyncio.run()` to bridge to the async library.

### F8: Error Reporting

Errors are reported per-ticket, not as a single pass/fail:

```python
@dataclass
class SyncError:
    ticket_id: str
    error_type: str       # "not_found", "permission_denied", "api_error", "parse_error"
    message: str
    retriable: bool
```

The tool never raises an exception for a single-ticket failure. It completes the sync for all reachable tickets and returns a `SyncResult` with the error list. The caller decides whether to proceed with partial context or abort.

Exception: If the **root ticket** of a `sync` call fails to fetch, the tool raises immediately — there is no meaningful partial result without the root.

### F9: Format Versioning

Each file includes `format_version: 1` in frontmatter. When the format changes (fields added/removed, structure changed), the version is incremented. The tool can detect old-format files and either:
- Re-sync them (preferred — simplest).
- Migrate them in place (if re-sync is expensive or undesirable).

---

## 6. Non-Functional Requirements

### NF1: Performance

- Initial sync of a 100-ticket graph should complete in under 60 seconds on a typical network connection.
- Delta refresh of a 100-ticket context directory with 5 changed tickets should complete in under 10 seconds.
- The tool should use concurrent API calls where possible (e.g., fetch multiple tickets in parallel, respecting Linear's rate limits).

### NF2: Rate Limit Compliance

- Respect Linear API rate limits. Use `linear-client`'s built-in retry and backoff mechanisms.
- Do not implement independent rate limiting — defer to the client library.

### NF3: Atomicity

- File writes must be atomic: write to a temporary file in the same directory, then rename. A crash mid-write must not leave a corrupted or partial file.
- The context directory is never left in a state where a file exists but is incomplete.

### NF4: Idempotency

- Running the same `sync` command twice with no intervening Linear changes produces no file modifications (all files report as `unchanged`).
- Running `refresh` immediately after `sync` produces no file modifications.

### NF5: No Side Effects

- The tool never modifies Linear state. It is strictly read-only.
- The tool never modifies files outside the specified context directory.
- The tool never makes git commits. That responsibility belongs to the caller.

---

## 7. Project Structure

### 7.1 Repository

A separate repository from both `linear-client` and `agent-control-plane`. Proposed name: `linear-context-sync`.

**Rationale**:
- **Not in `linear-client`**: The client library is a general-purpose Linear API client. The context sync tool is a domain-specific application of that client. Coupling them would force `linear-client` consumers who don't need context sync to carry the dependency, and would mix library-level concerns (API abstraction) with application-level concerns (file I/O, graph traversal strategy, Markdown formatting).
- **Not in `agent-control-plane`**: The tool is useful independently of the control plane (human use, CI scripts, other projects). Embedding it in the control plane would make it inaccessible without importing the entire framework.

### 7.2 Dependencies

| Dependency | Purpose |
|---|---|
| `linear-client` | Linear API access (domain layer + authentication) |
| `pyyaml` or equivalent | YAML frontmatter serialization/deserialization |
| `click` or `typer` | CLI framework |
| Standard library | `asyncio`, `pathlib`, `dataclasses`, `tempfile` |

No other runtime dependencies. The tool should be lightweight and fast to install.

### 7.3 Package Layout (Proposed)

```
linear-context-sync/
  pyproject.toml
  src/
    linear_context_sync/
      __init__.py              # public API re-exports
      syncer.py                # ContextSyncer class (core logic)
      graph.py                 # per-dimension graph traversal / BFS with depth budgets
      serializer.py            # ticket → Markdown file conversion
      parser.py                # Markdown file → ticket metadata (for delta checks)
      models.py                # SyncResult, SyncError, DiffResult, dimension defaults, etc.
      cli.py                   # CLI entry point
  tests/
    ...
```

### 7.4 Distribution

Published as a private wheel (same distribution mechanism as `linear-client` — see [linear-client.md](../../design/linear-client.md) Installation section). Installed into the agent control plane's virtualenv and into the user's environment.

---

## 8. Open Design Questions

### DQ-1: Batch `updated_at` Query

For delta sync, the tool needs to check whether each existing file's ticket has changed. Fetching each ticket individually to read `updated_at` is O(N) API calls, which defeats the purpose of delta sync for large context directories.

**Options**:
- (a) Use a single GraphQL query with an `id: { in: [...] }` filter to fetch `updated_at` for all tracked tickets in one call. This requires the query to return only the `updated_at` field (lightweight).
- (b) Use the Linear `issues` connection with a `updatedAt: { gte: <oldest_last_synced_at> }` filter to find all tickets updated since the oldest sync time, then intersect with the tracked set.
- (c) Accept O(N) calls for now; optimize in a later version.

**Recommendation**: Option (a) is the best balance of efficiency and simplicity. It requires one GraphQL call per delta check, regardless of how many tickets changed. This may need to go through `linear-client`'s GraphQL services layer if the domain layer doesn't support batch ID lookups.

### DQ-2: Comment Handling for Large Threads

Some tickets accumulate many comments (50+). Including all comments in every sync could make files very large and slow to parse.

**Options**:
- (a) Always include all comments. Simplest; files are self-contained.
- (b) Include only comments since the last sync (delta comments). Requires maintaining a comment watermark.
- (c) Include a configurable maximum number of comments (e.g., last 50). Older comments are truncated with a "N earlier comments omitted" note.
- (d) Store comments in a separate file per ticket (e.g., `ACP-123.comments.md`).

**Recommendation**: Option (a) for the first version. Most tickets in a well-managed project have fewer than 20 comments. If large threads become a practical problem, option (c) is the least-disruptive optimization.

### DQ-3: ~~Relation Type Semantics in Frontmatter~~ (Resolved)

Resolved by the per-dimension traversal model in F1. Relations are normalized to the canonical dimension set (`blocks`, `is_blocked_by`, `parent`, `child`, `relates_to`, `ticket_ref`). Each relation in frontmatter includes its dimension. The normalization logic builds on the agent loop's existing `extract_blockers` function (see [linear-integration.md Section 2.5](../../design/linear-integration.md)) and extends it to cover all dimension types.

### DQ-4: Tool Name

Proposed: `linear-context-sync`. Alternatives:
- `linear-ticket-dump`
- `linear-context-materializer`
- `lcs` (short alias)

The name should be concise, descriptive, and available as a package name.

### DQ-5: Python Version

The tool should target the same Python version as the agent control plane (3.13+) to avoid compatibility issues. However, if standalone human use on older Python is desired, a lower floor (3.11+) could be considered.

**Recommendation**: Python 3.13+ to match the ecosystem. The tool is installed in the same virtualenv as the control plane; version divergence adds no value.

### DQ-6: Concurrent Fetch Strategy

When traversing a graph of 100+ tickets, sequential fetching is slow. The tool should fetch tickets concurrently, but must respect Linear's rate limits.

**Options**:
- (a) Use `asyncio.gather` with a semaphore to limit concurrency (e.g., 10 concurrent fetches).
- (b) Use `asyncio.TaskGroup` (Python 3.11+) with the same semaphore pattern.
- (c) Rely on `linear-client`'s internal rate limiting and issue all fetches concurrently.

**Recommendation**: Option (b) with a configurable concurrency limit (default: 10). `TaskGroup` provides better error handling than `gather`. The semaphore prevents overwhelming the API even if `linear-client`'s rate limiting is permissive.
