# Tool ADR: Linear Context Sync — Architectural Decisions

> **Status**: Draft
> **Date**: 2026-03-13
> **Context**: Forked from the agent-control-plane repo

---

## Decision Summary

This ADR turns the needs described in [problem-statement.md](<problem-statement.md>) into architectural decisions. The design must:

- move deterministic Linear retrieval out of the model loop and into a bounded subsystem;
- produce a durable local snapshot that agents, humans, and automation can inspect directly;
- support bounded graph traversal beyond a single hop;
- allow the set of root tickets to grow over time instead of treating the initial root as the only durable anchor;
- support lightweight refresh behavior where unchanged tickets avoid a full re-fetch and only changed tickets incur full materialization work;
- distinguish clearly between full sync, incremental refresh, and diff-only inspection so callers know which operations mutate the snapshot and at what scope;
- remain reusable outside the agent control plane;
- remain read-only with respect to Linear.

The sections below record the decisions that satisfy those drivers and identify the remaining questions that must be answered before low-level design can begin confidently.

---

## 1. Traversal Model

### 1.1 Dimensions

Each relationship type is treated as a graph dimension with its own configurable traversal depth. The built-in dimensions are:

| Dimension | Source | Description | Default depth |
|---|---|---|---|
| `blocks` | Linear relation | Tickets that block the current ticket | 3 |
| `is_blocked_by` | Linear relation | Tickets that the current ticket blocks | 2 |
| `parent` | Linear relation | Parent ticket | 2 |
| `child` | Linear relation | Child tickets | 2 |
| `relates_to` | Linear relation | Informational relations | 1 |
| `ticket_ref` | URL scan | Ticket URLs discovered in other tickets' descriptions or comments | 1 |

Dimensions can be disabled by setting depth to 0. A maximum ticket-count cap, with a default of 200, acts as a separate safety bound.

Linear's current relation types are fixed, but the internal dimension representation should remain extensible. The first version ships with the built-in dimensions above, while leaving room for future dimensions without redesigning the traversal engine.

`ticket_ref` covers ticket URLs found inside fetched Linear content. It does not cover repository documents. If the caller finds a ticket ID elsewhere, the caller should add that ticket explicitly as a new root. A future `doc_ref` dimension can be introduced later if repository scanning becomes a tool responsibility.

### 1.2 Depth Model — Total Hops from Root

Depth is measured as total hops from the nearest root, regardless of edge type. For a ticket at depth `N`, an outgoing edge is followed only when that edge's dimension is configured for a depth greater than `N`.

This means a dimension depth answers the question: "How many total hops from a root am I willing to cross this type of edge?" The traversal does not reset a counter when the edge type changes.

Example with defaults (`blocks`: 3, `relates_to`: 1):

```text
Root (depth 0)
|- (blocks) -> A (depth 1)      allowed
|  |- (blocks) -> C (depth 2)   allowed
|  |  `- (blocks) -> E (depth 3) allowed
|  `- (relates_to) -> D (depth 2) skipped
`- (relates_to) -> B (depth 1)  allowed
   `- (blocks) -> F (depth 2)   allowed
```

Under this model, `D` is not fetched. Even though it is one `relates_to` hop away from `A`, it is still two total hops from the root and `relates_to` is configured for depth 1.

This total-hop model is preferred over per-dimension counters because it stays naturally bounded, is easier to reason about, and avoids creating long indirect paths whose effective depth is hard to predict.

When a ticket is reachable through multiple paths or from multiple roots, the tool uses the shortest total distance from any root as the ticket's effective depth.

### 1.3 Traversal Order and Ticket Cap

Traversal is breadth-first from all roots simultaneously. Depth-1 tickets are processed before depth-2 tickets, and so on. If the ticket cap is reached mid-traversal, the tool stops and returns the tickets already collected.

Breadth-first traversal is the right default when a safety cap exists because it prioritizes the nearest and usually most relevant neighborhood before exploring deep chains.

### 1.4 Root vs. Derived Tickets

Every ticket in the context directory is classified as either root or derived.

- Root tickets are explicitly requested, either by the initial sync or by an explicit add operation. They are pinned and are never removed automatically.
- Derived tickets enter the directory because they were discovered during traversal from at least one root.

The root set is intentionally mutable over the lifetime of a context directory. The tool must support expanding the pool of roots when a caller discovers an additional ticket that should remain part of the long-lived working set. Once added, that ticket participates in future traversal, refresh, and pruning decisions as a first-class root.

Root expansion must not be implemented as a partial rebuild of only the newly added root's local subgraph when a snapshot already exists. If a new root overlaps the graph of an existing root, rebuilding only the new root's neighborhood would refresh the overlap at time `T` while leaving non-overlapping portions of the old snapshot at time `T-1`, producing a mixed-time checkpoint. Root-set mutation therefore has to be paired with a whole-snapshot operation, not a root-local rebuild.

Traversal depth is always measured from a root. A derived ticket's effective depth is the shortest distance from any root. Whether its outgoing edges are followed depends on the configured depth of each edge's dimension relative to that effective depth.

On sync or refresh, the reachable graph is recomputed from all current roots using the active dimension configuration:

- root tickets are kept and refreshed when stale;
- derived tickets that remain reachable are kept and refreshed when stale;
- derived tickets that are no longer reachable are removed.

Dimension-depth reductions can therefore remove derived files, but they never remove roots.

By default, frontmatter records only whether a ticket is a root. An optional debug mode may also record provenance metadata such as which root reached the ticket, by which dimension, and at what depth.

Cycle safety is mandatory: once a ticket has been visited during a sync run, it is not re-fetched through another path in the same run.

---

## 2. Persistence Format

The tool writes one Markdown file per ticket, named `<ticket-identifier>.md`, with YAML frontmatter for structured metadata.

Markdown is the chosen persistence format because it is human-readable, agent-readable, and diff-friendly in git. The ticket identifier as the filename gives natural deduplication and constant-time lookup.

Minimum frontmatter includes:

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
root: false
parent_ticket: "ACP-100"
relations:
  - type: "is_blocked_by"
    dimension: "blocks"
    ticket: "ACP-120"
attachments:
  - name: "design-spec.pdf"
    url: "https://linear.app/..."
---
```

The body stores the ticket description in Markdown followed by a chronological comments section. Each ticket file should be self-contained enough that a human can understand what was fetched without reconstructing the API responses elsewhere.

Every file includes `format_version`. When the file format changes, the tool increments the version and re-syncs old files rather than depending on implicit compatibility.

---

## 3. Runtime Foundation and Interface Model

### 3.1 Foundation

The implementation is a Python 3.13+ project and is async-first.

This is a deliberate architectural choice, not just an implementation convenience:

- the primary consumers are already Python systems;
- the repository conventions are Python-first and async-first;
- the workload is dominated by I/O to Linear plus local file-system operations, which fits an async model well.

`linear-client` is the mandatory foundation for Linear integration. The context-sync tool builds on top of it for authentication, domain-level access to Linear data, connection management, and rate-limit/backoff behavior. The tool should not create a parallel Linear integration stack unless a missing capability in `linear-client` forces a narrowly scoped extension.

All library entry points that can trigger remote or file I/O should be async functions, and the implementation should avoid introducing blocking I/O in the core sync path. The CLI may bridge into that async API with `asyncio.run()`, but synchronous wrappers are not the primary design center.

### 3.2 Interface Model

The tool exposes two interfaces:

- an async Python library API for the agent loop and other programmatic callers;
- a thin CLI wrapper for humans and shell-based automation.

The library API is the primary integration surface. It supports full sync, explicit addition of new roots, refresh of existing local context, and diffing the local snapshot against Linear without writing files.

The library receives an authenticated `Linear` client instance from the caller instead of constructing one internally. This keeps authentication, connection reuse, and lifecycle management with the embedding application.

The CLI is a convenience layer over the library API. It is responsible for reading configuration and constructing its own authenticated client using the same environment and credential model used by [`docs/design/linear-client.md`](<design/linear-client.md>).

Detailed method signatures and return types belong in [design.md](<design.md>), not in the problem statement.

---

## 4. Packaging and Integration Boundary

The tool is a separate Python project from both `linear-client` and the agent control plane.

This separation keeps concerns clear:

- `linear-client` remains a reusable API client and authentication layer;
- the context-sync tool owns graph traversal, local persistence, and snapshot management;
- the agent control plane consumes the tool instead of embedding its materialization logic.

The tool should be distributed the same way as other private internal Python packages, as a private wheel that consumers can install into their own environments.

Package layout and implementation flow details belong in [design.md](<design.md>).

---

## 5. Operating Modes

The tool has three persisted operating modes: `sync`, `refresh`, and `diff`.

### 5.1 `sync`: Full-Snapshot Rebuild

`sync` is the full rebuild mode. It starts from the full current root set, bootstrapping that root set if needed, traverses the reachable graph, and performs a fresh pull for every reachable ticket.

In `sync` mode:

- the tool rewrites reachable ticket files regardless of whether local metadata suggests they were already fresh;
- the tool uses all currently tracked roots as starting points, not just the most recently added root;
- the tool prunes derived tickets that are no longer reachable from the recomputed root set.

`sync` exists for initial materialization, format migrations, explicit rebuild requests, and any situation where replacing the snapshot wholesale is preferable to incremental optimization.

### 5.2 `refresh`: Incremental Whole-Snapshot Update

`refresh` is the lightweight whole-snapshot mode. It also starts from the full current root set, but it uses snapshot metadata to avoid a full re-fetch when a ticket has not changed.

In `refresh` mode:

- the tool recomputes reachability from the full root set;
- it checks freshness across the whole tracked snapshot;
- it fully re-fetches only tickets that changed remotely or are newly discovered;
- it prunes derived tickets that are no longer reachable.

The first version should treat `refresh` as a whole-snapshot operation, not a root-local or ticket-local refresh mode. Partial refresh of only one root's neighborhood risks creating a mixed-time snapshot when roots overlap.

Adding a root to an existing context directory should therefore use `refresh` semantics by default: mutate the root set first, then run a whole-snapshot incremental update from all roots. Root addition is not a separate snapshot-construction mode.

### 5.3 `diff`: Non-Mutating Drift Inspection

`diff` compares the current local snapshot to live Linear state without modifying files. It exists to let humans and automation see what moved since the current checkpoint before deciding whether to run `refresh` or `sync`.

---

## 6. Refresh and Diff Strategy

Freshness is determined from information stored in the files themselves. Each ticket file carries `last_synced_at`, and the remote source of truth carries `updated_at`.

On refresh:

1. identify all root tickets in the context directory;
2. recompute the currently reachable graph from those roots;
3. compare local `last_synced_at` values against remote `updated_at` values;
4. re-fetch only stale or newly discovered tickets;
5. prune derived tickets that are no longer reachable.

This approach avoids a separate state store and supports efficient incremental refreshes. The steady-state goal is a lightweight refresh path that scales primarily with changed tickets rather than the full size of the context directory, aside from the bounded metadata work required to determine freshness. In other words, the common case should be "check many, fully re-fetch few."

The preferred implementation is a batched `updated_at` query rather than one remote call per ticket. That batching detail remains an open implementation question in [TQ-1](#tq-1-batch-updated_at-query).

The tool also supports a diff mode that compares the current context directory against live Linear data without modifying local files. Diff mode exists for both human debugging and pre-refresh validation.

---

## 7. Failure Model

Linked-ticket failures are reported per ticket rather than failing the entire run. The tool should return partial results whenever it can do so safely.

The important exception is root-ticket failure during an initial sync. If the root ticket cannot be fetched, the sync fails immediately because there is no meaningful graph to materialize.

This leads to the following behavior:

- root fetch failure is terminal for that sync request;
- linked-ticket fetch failure is recorded in the result while other reachable tickets continue;
- local write failures are terminal because they break the integrity of the local snapshot.

Result types should therefore carry explicit created, updated, unchanged, removed, and errored sets rather than reducing the run to a single success or failure bit.

---

## 8. Operating Guarantees

The tool makes the following guarantees:

- It is read-only with respect to Linear.
- It never writes outside the configured context directory.
- File writes are atomic so a crash does not leave a partially written ticket file behind.
- Re-running sync or refresh without upstream changes should not rewrite files.
- Traversal is always bounded by configured depths plus the ticket cap.
- Rate-limit handling is delegated to `linear-client`; the tool should not introduce a separate, conflicting rate limiter unless experience shows the library layer is insufficient.

These guarantees are part of the architecture because callers need them to trust the local snapshot as an operational input.

---

## 9. Open Questions

### TQ-1: Batch `updated_at` Query

Delta refresh needs an efficient way to check freshness for many tracked tickets.

Options:

- one GraphQL query using an `id in [...]` filter to fetch `updated_at` for all tracked tickets;
- a broader `updatedAt >= ...` query intersected with the tracked set;
- per-ticket lookups for the initial version, with optimization deferred.

Recommendation: prefer the batched ID-based query if it can be exposed cleanly through `linear-client`.

### TQ-2: Comment Handling for Large Threads

Some tickets accumulate long comment histories.

Options:

- always include all comments;
- persist only comment deltas;
- cap the stored comment count and note truncation;
- split comments into a separate file.

Recommendation: include all comments in the first version unless ticket size proves to be a real operational problem.

### TQ-3: Attachment Content Inlining

The first version stores attachment metadata and URLs but not attachment contents. Text attachments and images may justify richer handling later, but that should be treated as a separate capability.

### TQ-4: Tool Name

Proposed name: `linear-context-sync`.

### TQ-5: Concurrent Fetch Strategy

The tool needs bounded concurrency for ticket fetches.

Options:

- `asyncio.gather` with a semaphore;
- `asyncio.TaskGroup` with a semaphore;
- no explicit concurrency control beyond whatever `linear-client` already does internally.

Recommendation: prefer `TaskGroup` with a configurable semaphore limit.

### TQ-6: Root-Set Removal and Demotion Semantics

The ADR now decides that the root pool can expand over time, but it does not yet define how roots leave that pool.

Questions to answer:

- Should the tool support an explicit "remove root" or "demote root" operation?
- If so, is removal immediate, or only effective on the next refresh?
- How should the tool protect against accidentally removing a root that is still operationally important?

This matters before low-level design because root lifecycle affects frontmatter, CLI shape, pruning behavior, and result reporting.

### TQ-7: Snapshot Consistency Contract

The problem statement calls out inconsistency in the current runtime fetch model, but the ADR does not yet define the consistency guarantee of the new tool.

Questions to answer:

- Is the target guarantee best-effort freshness, a bounded-skew snapshot, or something stronger?
- Can Linear provide enough metadata to approximate a stable read boundary, or must the tool document that snapshots are assembled over time?
- How should the tool surface that guarantee to callers and humans reading the files?

This matters because it changes both refresh logic and user expectations about what "snapshot" means.

### TQ-8: Ticket Identity and Rename Semantics

The file format uses the human-facing ticket identifier in filenames, but the ADR does not yet resolve how identity behaves if that identifier changes.

Questions to answer:

- Should the filename be based on the stable Linear UUID, the human-facing issue key, or both?
- If the issue key changes, does the tool rename the file, create an alias, or keep the old filename?
- Which identifier is authoritative for deduplication and refresh?

This needs an answer before low-level design because it affects directory layout, parser behavior, and migration logic.

### TQ-9: Concurrency and Locking for the Context Directory

The ADR defines atomic writes but not multi-process behavior.

Questions to answer:

- Can more than one sync or refresh run against the same context directory at once?
- If not, what locking mechanism prevents overlapping writers?
- If yes, what is the conflict-resolution model for create, update, prune, and root-set changes?

This matters because local snapshot correctness is not just about single-file atomicity.

### TQ-10: Change Detection Granularity

The refresh strategy currently assumes `updated_at` is the right freshness cursor, but the ADR does not yet spell out which remote changes must be observable locally.

Questions to answer:

- Does Linear's `updated_at` advance for all changes we care about, including comment edits, relation changes, label changes, and attachment changes?
- If not, do we need additional per-ticket cursors or field-specific freshness checks?
- Which local fields count as materially changed for diff reporting?

This is a low-level-design blocker because it determines whether the lightweight refresh model is actually correct.

### TQ-11: File-Normalization and Diff-Stability Rules

The ADR chooses Markdown plus frontmatter, but it does not yet define normalization rules for stable output.

Questions to answer:

- What ordering rules apply to labels, relations, and attachments?
- How are timestamps formatted canonically?
- How are empty fields represented so repeated syncs do not churn files unnecessarily?

This matters because idempotency depends on deterministic serialization, not just correct data.

### TQ-12: Missing or Inaccessible Remote Tickets

The failure model covers linked-ticket fetch failures in general, but it does not yet distinguish between not found, permission loss, archival, and transient API errors.

Questions to answer:

- When a previously synced ticket becomes inaccessible, should the local file be kept, pruned, or replaced with a tombstone state?
- How should diff mode report that case?
- Are these cases retriable, user-actionable, or terminal?

This needs resolution before low-level design because it affects pruning, error types, and the human debugging story.

### TQ-13: Repository and Workspace Boundaries

The problem statement wants reuse across callers, but the ADR does not yet define how a context directory is scoped.

Questions to answer:

- Is one context directory tied to a single Linear workspace, team, or project namespace?
- What metadata is required to prevent collisions between workspaces that may reuse similar issue keys?
- Should mixed-workspace roots be allowed at all?

This matters before low-level design because directory metadata and validation rules depend on it.

### TQ-14: Observability and Verification Depth

The local snapshot is meant to be inspectable, but the ADR does not yet define the operational signals the tool emits while building it.

Questions to answer:

- What logs, counters, or summary metadata are required so humans can diagnose partial refreshes or pruning surprises?
- Should the tool verify written files by re-reading them, or is serializer determinism sufficient?
- What minimum provenance should be available outside debug mode?

This matters because debugging and trustworthiness are core reasons the tool exists.

### TQ-15: Do We Need a Separate Targeted Read Path?

The problem statement includes pre-write validation as an important workflow, but this ADR now leans toward making `refresh` a whole-snapshot operation in order to preserve checkpoint coherence.

Questions to answer:

- If a caller wants a very cheap "check just this one ticket before writing" operation, should that exist outside the persisted snapshot modes?
- If so, should it be exposed as a transient library helper rather than as `refresh`?
- How do we prevent callers from confusing a targeted transient read with a coherent snapshot update?

This matters because it affects both API shape and how strictly we preserve whole-snapshot semantics.
