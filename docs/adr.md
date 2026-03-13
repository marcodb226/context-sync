# Tool ADR: Linear Context Sync — Architectural Decisions

> **Status**: Draft
> **Date**: 2026-03-13
> **Context**: Forked from the agent-control-plane repo
---

## 1. Traversal Model

### 1.1 Dimensions

Each relationship type is a **graph dimension** with its own configurable traversal depth. The following are recognized as built-in dimensions:

| Dimension | Source | Description | Default depth |
|---|---|---|---|
| `blocks` | Linear relation | Tickets that block the current ticket | 3 |
| `is_blocked_by` | Linear relation | Tickets that the current ticket blocks | 2 |
| `parent` | Linear relation | Parent ticket | 2 |
| `child` | Linear relation | Child tickets | 2 |
| `relates_to` | Linear relation | Informational relations | 1 |
| `ticket_ref` | URL scan | Ticket URLs discovered in other tickets' descriptions or comments | 1 |

Depths are configurable. Dimensions can be disabled by setting depth to 0. A maximum ticket count cap (default: 200) acts as a safety bound independent of dimension depths.

Linear's current relation types (`blocks`, `is_blocked_by`, `related`) are fixed and not user-configurable. `parent` and `child` are structural. If Linear adds new relation types in the future, the tool maps them to an existing dimension or assigns a new built-in one.

**Custom dimensions**: The built-in set covers Linear's current relation types and within-ticket URL scanning. Future use cases may require additional dimensions (e.g., scanning repository documents for ticket URLs, or mapping a new Linear relation type). The tool's dimension model should be designed so that adding a new dimension requires only configuration, not code changes to the traversal engine. Custom dimension support is deferred to a later release; the first version ships with the built-in set. The internal representation (`dict[str, int]`) should not preclude extension.

**`ticket_ref` vs. `doc_ref`**: Ticket URLs can appear in two contexts:

- **`ticket_ref`**: A ticket URL found in another ticket's description or comments. The tool discovers it while processing a ticket it already fetched. Implemented in the first release.
- **`doc_ref`** (future): A ticket URL found in a repository document. Requires the tool to scan non-Linear content — a fundamentally different input surface. Deferred.

For the first release, when the caller discovers a ticket URL in a document, the correct action is to call `add` with that ticket ID, making it a root.

### 1.2 Depth Model — Total Hops from Root

The tool counts **total hops from the nearest root**, regardless of edge type. Each outgoing edge from a ticket at depth N is allowed if the edge's dimension has a configured depth greater than N.

The depth number for a dimension answers: "how many total hops from root am I willing to cross this type of edge?" At depth 1, all dimensions with depth ≥ 1 are explored. At depth 2, only dimensions with depth ≥ 2. At depth 3, only depth ≥ 3.

Example with defaults (`blocks`: 3, `relates_to`: 1):

```
Root (depth 0)
├── (blocks) → A (depth 1) ✓  blocks depth 3 ≥ 1
│   ├── (blocks) → C (depth 2) ✓  blocks depth 3 ≥ 2
│   │   └── (blocks) → E (depth 3) ✓  blocks depth 3 ≥ 3
│   └── (relates_to) → D (depth 2) ✗  relates_to depth 1 < 2
└── (relates_to) → B (depth 1) ✓  relates_to depth 1 ≥ 1
    └── (blocks) → F (depth 2) ✓  blocks depth 3 ≥ 2
```

D is *not* fetched — even though it's only one `relates_to` hop from A, it's two total hops from root, and `relates_to` is configured for depth 1. If that context is important, the user raises `relates_to` depth to 2.

**Why total hops, not per-dimension counting**: An alternative model would count hops per dimension independently — a `relates_to` edge at any distance from root would be allowed as long as it's within one `relates_to` hop of the previous ticket. This is more permissive but creates unbounded indirect paths: Root → (blocks) → A → (relates_to) → B → (blocks) → C → (relates_to) → D → ... traverses indefinitely because each dimension's counter resets after a hop of a different type. Preventing this requires a separate global depth cap, adding complexity with no benefit over total hops. Total hops is one counter, naturally bounded, and easy to reason about.

**Multi-dimension membership**: A ticket may be reachable via multiple paths of different lengths, or from different roots. The tool uses the **shortest total distance from any root** as the ticket's effective depth. A ticket at 1 hop from root A and 3 hops from root B is treated as depth 1.

### 1.3 Traversal Order and Ticket Cap

The tool traverses in **breadth-first order** from all roots simultaneously. Depth-1 tickets are visited before depth-2 before depth-3. If the ticket cap is reached mid-traversal, the tool stops and returns what it has.

BFS is the right priority for a cap: when budget runs out, the tool has covered the nearest, most diverse neighborhood — close tickets across all dimensions — rather than going deep along one chain. At each depth level, more dimensions are available (depth 1 allows all; depth 3 allows only high-depth dimensions), so the broadest exploration happens closest to root.

The cap is a safety bound, not a precision tool. Users adjust dimension depths for fine-grained control.

### 1.4 Root vs. Derived Tickets

Every ticket in the context directory is either **root** or **derived**:

- **Root tickets** (`root: true`) are explicitly requested — the initial ticket passed to `sync`, or any ticket added via `add`. Roots are pinned and never auto-removed.
- **Derived tickets** (`root: false`) entered via graph traversal from a root. They exist because they are reachable from at least one root within configured dimension depths.

Traversal depth is always measured from a root. A derived ticket's effective depth is the shortest distance from any root. Whether to follow its outgoing edges depends on whether any dimension's configured depth exceeds this effective depth.

**File lifecycle**: On sync or delta refresh, the tool recomputes the reachable graph from all roots using the active dimension configuration:

- Root tickets are never removed. Refreshed if stale.
- Derived tickets still reachable are kept. Refreshed if stale.
- Derived tickets no longer reachable are removed from the context directory.

Dimension depth reductions *can* cause derived files to disappear, but roots are always safe.

**Traversal provenance (optional debug metadata)**: By default, frontmatter records only the `root` flag. A debug/verbose flag enables provenance metadata for derived tickets (which root, which dimension, what depth). Useful for debugging; not required for correct operation.

---

## 2. File Format

One Markdown file per ticket, named `<ticket-identifier>.md` (e.g., `ACP-123.md`). Metadata is stored in YAML frontmatter.

**Rationale**: Markdown is human-readable, agent-readable, and diffs cleanly in git. YAML frontmatter is a standard convention for structured metadata in Markdown files. The ticket identifier as filename provides natural deduplication and O(1) lookup.

**Frontmatter fields** (minimum):

```yaml
---
ticket_id: "ACP-123"
title: "Implement polling loop"
status: "In Progress"
assignee: "developer-bot"
creator: "architect-bot"
labels:
  - "Type / Task"
priority: 2
created_at: "2026-03-10T14:30:00Z"
updated_at: "2026-03-13T09:15:00Z"
last_synced_at: "2026-03-13T10:00:00Z"
format_version: 1
root: false              # true = pinned (explicitly requested), false = derived (discovered via traversal)
parent_ticket: "ACP-100"
relations:
  - type: "is_blocked_by"
    dimension: "blocks"
    ticket: "ACP-120"
  - type: "blocks"
    dimension: "is_blocked_by"
    ticket: "ACP-130"
  - type: "relates_to"
    dimension: "relates_to"
    ticket: "ACP-125"
  - type: "ticket_ref"
    dimension: "ticket_ref"
    ticket: "ACP-456"
    context: "referenced in comment by architect-bot at 2026-03-12T08:00:00Z"
attachments:
  - name: "design-spec.pdf"
    url: "https://linear.app/..."
# Optional debug metadata (only present when provenance tracking is enabled):
# provenance:
#   reached_from: "ACP-100"
#   dimension: "blocks"
#   depth_from_root: 1
---
```

**Body**: The ticket description in Markdown, followed by a `## Comments` section with all comments in chronological order, each attributed to author and timestamp.

**Format versioning**: Each file includes `format_version: 1` in frontmatter. When the format changes, the version is incremented. The tool detects old-format files and re-syncs them.

---

## 3. Tool Architecture

The tool is a **separate Python project** from `linear-client` and from the agent control plane. It depends on `linear-client` as a library for all Linear API access. It exposes two interfaces: a CLI command (for human use and shell invocation) and an async Python API (for programmatic integration).

**Rationale**: Separation of concerns — `linear-client` is a general-purpose Linear API client; the tool is a domain-specific context materializer. Consumers (including the agent control plane) import it; they do not implement materialization logic. Dual interface supports both library callers (avoiding subprocess overhead, enabling richer error handling) and humans running it from the command line.

See [cr-tool-problem-statement.md](cr-tool-problem-statement.md) Section 7 for project structure, dependencies, and distribution details.

---

## 4. Delta Update Strategy

The tool uses `last_synced_at` (stored in each file's frontmatter) and the ticket's `updated_at` from the Linear API to determine whether a file needs refreshing. On a delta invocation:

1. Identify all root tickets in the context directory.
2. Recompute the reachable graph from all roots using the active dimension configuration.
3. For each existing file, compare `last_synced_at` with the ticket's current `updated_at` from Linear.
4. If `updated_at > last_synced_at`, re-fetch and rewrite the file.
5. If `updated_at <= last_synced_at`, skip the file.
6. New tickets discovered in the relation graph (not yet in the context directory) are fetched and written.
7. Derived tickets no longer reachable from any root are removed.

**Rationale**: `updated_at` changes on any Linear mutation, so this is a conservative but correct freshness check. The tool always knows which files are stale without maintaining a separate state store — the state is in the files themselves.

---

## 5. Diff Mode

Compare the current context directory against Linear's live state without modifying any files. For each tracked ticket, report whether its local file is current, stale, or missing from Linear. For stale tickets, show which fields changed.

This serves two purposes:
- **Human debugging**: Inspect an agent's working branch to see where the snapshot diverges from Linear's current state, without triggering a sync.
- **Pre-sync validation**: Check what *would* change before committing to a refresh.

See [cr-tool-problem-statement.md](cr-tool-problem-statement.md) F5 for the output contract (`DiffEntry`, `DiffResult`).

---

## 6. Open Questions (Tool-Specific)

### TQ-1: Batch `updated_at` Query

For delta sync, the tool needs to check whether each existing file's ticket has changed. Fetching each ticket individually is O(N) API calls.

**Options**:
- (a) Single GraphQL query with `id: { in: [...] }` filter to fetch `updated_at` for all tracked tickets in one call.
- (b) Use `updatedAt: { gte: <oldest_last_synced_at> }` filter, intersect with tracked set.
- (c) Accept O(N) calls for now; optimize later.

**Recommendation**: Option (a). One call per delta check regardless of how many tickets changed. May need `linear-client`'s GraphQL services layer if the domain layer doesn't support batch ID lookups.

### TQ-2: Comment Handling for Large Threads

Some tickets accumulate many comments (50+). Including all in every sync could make files very large.

**Options**:
- (a) Always include all comments. Simplest; files are self-contained.
- (b) Delta comments only (requires watermark).
- (c) Configurable max comments (e.g., last 50), older truncated with a note.
- (d) Separate comments file per ticket.

**Recommendation**: Option (a) for the first version. Most tickets have fewer than 20 comments. Option (c) is the least-disruptive optimization if needed.

### TQ-3: Attachment Content Inlining

Frontmatter includes clickable attachment URLs but not content. Text-based attachments could be fetched and inlined or stored as separate files. Image attachments could be described. Deferred to a future version but should be accounted for in directory structure design.

### TQ-4: Tool Name

Proposed: `linear-context-sync`. Alternatives: `linear-ticket-dump`, `linear-context-materializer`, `lcs`.

### TQ-5: Concurrent Fetch Strategy

**Options**:
- (a) `asyncio.gather` with semaphore (e.g., 10 concurrent fetches).
- (b) `asyncio.TaskGroup` (Python 3.11+) with semaphore.
- (c) Rely on `linear-client`'s internal rate limiting.

**Recommendation**: Option (b) with configurable concurrency limit (default: 10). `TaskGroup` provides better error handling. Semaphore prevents overwhelming the API.
