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

Traversal is breadth-first by total depth from all roots simultaneously. Depth-1 tickets are processed before depth-2 tickets, and so on.

Within a given depth, the first release uses fixed dimension-priority tiers:

- Tier 1: `blocks`, `is_blocked_by`, `parent`, `child`
- Tier 2: `relates_to`
- Tier 3: `ticket_ref`

If the ticket cap becomes relevant, higher-priority tiers at the current depth are processed before lower-priority tiers. This ensures structural dependency edges win over informational edges near the safety bound.

Within a tier, traversal remains ordinary breadth-first processing of the current depth frontier. The first release does **not** define an absolute global ranking among individual relations inside the same tier. In other words, tier selection is prioritized, but same-tier work still follows normal breadth-first order with deterministic relation ordering.

If the ticket cap is reached mid-traversal, the tool stops and returns the tickets already collected. This means lower-priority tiers at the current depth, and all deeper depths, may be omitted by design when the cap is hit.

Tiered breadth-first traversal is the right default when a safety cap exists because it still prioritizes the nearest neighborhood before deep chains, while avoiding the specific failure mode where informational edges crowd out structural dependencies.

### 1.4 Root vs. Derived Tickets

Every ticket in the context directory is classified as either root or derived.

- Root tickets are explicitly requested, either by the initial sync or by an explicit add operation. They are pinned and are never removed automatically.
- Derived tickets enter the directory because they were discovered during traversal from at least one root.

The root set is intentionally mutable over the lifetime of a context directory. The tool must support expanding the pool of roots when a caller discovers an additional ticket that should remain part of the long-lived working set. Once added, that ticket participates in future traversal, refresh, and pruning decisions as a first-class root.

Root expansion must not be implemented as a partial rebuild of only the newly added root's local subgraph when a snapshot already exists. If a new root overlaps the graph of an existing root, rebuilding only the new root's neighborhood would refresh the overlap at time `T` while leaving non-overlapping portions of the old snapshot at time `T-1`, producing a mixed-time checkpoint. Root-set mutation therefore has to be paired with a whole-snapshot operation, not a root-local rebuild.

Root removal is also supported explicitly. The first release supports a minimal `remove-root` operation that removes a ticket from the manifest root set and then immediately runs the normal whole-snapshot refresh flow under the same writer lock. If that ticket is still reachable from another root, it remains in the snapshot as a derived ticket. If it is no longer reachable, the next refresh prunes it naturally.

Deleting a ticket file by hand is not a supported way to remove a root. The manifest is the authoritative root-set source, so a manual file deletion alone does not remove the root from the tracked snapshot. A later refresh may simply recreate the file.

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

The tool writes one Markdown file per ticket, named `<current-ticket-key>.md`, with YAML frontmatter for structured metadata.

Markdown is the chosen persistence format because it is human-readable, agent-readable, and diff-friendly in git. The current ticket key as the filename keeps files easy for humans and agents to browse directly, while stable deduplication and issue-key-change handling rely on the ticket's immutable Linear UUID stored in frontmatter and in the context manifest.

Minimum frontmatter includes:

```yaml
---
assignee: "developer-bot"
attachments:
  - name: "design-spec.pdf"
    url: "https://linear.app/..."
created_at: "2026-03-10T14:30:00Z"
creator: "architect-bot"
format_version: 1
labels:
  - "Type / Task"
last_synced_at: "2026-03-13T10:00:00Z"
parent_ticket_key: "ACP-100"
priority: 2
relations:
  - dimension: "blocks"
    ticket_key: "ACP-120"
    type: "is_blocked_by"
root: false
status: "In Progress"
ticket_key: "ACP-123"
ticket_uuid: "9c9e3d7a-7e1c-4f22-9db4-2d640fb4bb20"
title: "Implement polling loop"
updated_at: "2026-03-13T09:15:00Z"
---
```

The body stores the ticket description in Markdown followed by a chronological comments section. Each ticket file should be self-contained enough that a human can understand what was fetched without reconstructing the API responses elsewhere.

For the first release, each ticket file includes the full comment history returned by Linear. This keeps the snapshot self-contained and keeps refresh logic simple. If comment volume later proves to be a material performance or file-size problem, follow-on optimizations are tracked in [FW-1](<future-work.md#fw-1-comment-storage-optimizations>).

The first release does not include a separate ticket activity or history timeline beyond the comments returned with the ticket. Richer history capture is deferred to [FW-5](<future-work.md#fw-5-ticket-history-and-sectioned-ticket-artifacts>). If that richer history is added later and proves too bulky for the main ticket file, it may be stored in adjacent section files rather than forcing every consumer to open one very large document.

For the first release, attachment handling is metadata-only. Ticket files include attachment metadata and URLs, but do not inline or download attachment contents. Richer handling for text attachments, images, and other file types is deferred and tracked in [FW-2](<future-work.md#fw-2-attachment-content-handling>).

Every file includes `format_version`. When the file format changes, the tool increments the version and re-syncs old files rather than depending on implicit compatibility.

Stable ticket identity is based on the immutable Linear issue UUID, not on the human-facing issue key. The current issue key remains part of the file format because it is what humans and surrounding docs naturally reference, but it is treated as a presentation alias rather than the authoritative identity.

If a tracked ticket's issue key changes, the tool renames the local file to the current key, updates the manifest's UUID-to-path mapping, and preserves the previous key as a locally known alias. The concrete documented reason for this today is that a Linear issue can move to another team in the same workspace and receive a new issue ID. More generally, the tool treats any upstream reassignment of the human-facing issue key the same way. Agents should therefore resolve ticket references through the manifest rather than by depending on Linear URL redirects or by scanning file contents.

This alias guarantee is intentionally bounded in the first release: offline resolution is guaranteed only for issue-key changes observed after the tool starts tracking a given ticket. If the Linear API later exposes authoritative historical aliases for a ticket, the tool should ingest them as well; that enhancement is deferred to [FW-4](<future-work.md#fw-4-historical-ticket-alias-import>).

### 2.1 Context Manifest and Non-Ticket Files

Each `context_dir` also contains a small manifest file, `.context-sync.yml`, that stores directory-level metadata that should not require opening ticket files to discover.

For the first release, the manifest is the authoritative source for:

- the workspace identity bound to the directory, including a stable workspace ID and a human-readable workspace slug;
- the current root-ticket set, keyed by stable ticket UUID;
- ticket identity lookup metadata, including UUID-to-current-key and path mappings plus known key aliases back to UUID;
- the context-level format version;
- snapshot-pass metadata, including the last completed snapshot mode and timestamps for when that pass started and completed.

This manifest is how the tool knows whether an `add` request belongs to the workspace already tracked by the directory. If the caller supplies a Linear URL, the tool may use the URL's workspace slug as an early preflight check, but the authoritative validation is still the fetched ticket's workspace identity compared against the manifest's workspace identity.

No separate secondary index file is introduced in the first release. The manifest already solves the directory-level lookup problems that matter most in v1: "which workspace is this?", "which tickets are roots?", and "which locally tracked ticket does this key or alias refer to?" Ticket files still retain their own `root` flag for local readability, but the manifest is the authoritative root-set and ticket-identity source for refresh, add, and remove-root flows.

The only other required non-ticket file is `.context-sync.lock`, a small structured lock record used to enforce the single-writer rule for mutating operations.

For the first release, the lock record should contain enough metadata for safe contention handling and human diagnosis: a unique writer ID, host identifier, process ID when available, acquisition timestamp, and the mutating mode that owns the lock. On lock contention, the tool should inspect this metadata rather than treating mere file existence as proof of an active writer.

### 2.2 Normalization and Rendered Body Structure

Deterministic serialization is part of the architectural contract. Re-running `sync` or `refresh` without upstream changes must not rewrite files merely because the serializer chose a different but equivalent ordering or empty-field representation.

For the first release, the normalization contract is:

- YAML mapping keys are emitted in lexicographic order at each nesting level; list element order is controlled separately by the collection-specific rules below;
- timestamps are serialized in canonical UTC RFC3339 form using `Z`, preserving fractional seconds only when the source value includes them;
- optional scalar fields are omitted when absent, and empty collections are omitted rather than emitted as empty lists;
- labels are always rendered as one deterministic display string: `<group> / <label>` when a label group is present, otherwise just `<label>`; labels are sorted lexicographically by that full rendered string;
- relations are sorted deterministically by dimension, relation type, and target identity; when a stable target UUID is available internally it should drive the sort, even though the file renders the current readable ticket key;
- attachments are sorted deterministically by stable URL, then by name as a tie-breaker.

The body is also normalized. The tool writes one description section and one comments section in a fixed order. The comments section is rendered as comment threads rather than as a flat list.

For comment rendering:

- top-level comment threads are ordered newest-first by thread activity;
- within a thread, the parent comment appears first and nested replies are embedded directly under that parent rather than flattened into the global order;
- replies within a sibling set are rendered in chronological order so the local conversation remains readable;
- the thread-level `resolved` flag is rendered with the thread metadata and is also available in the machine-readable thread marker.

Section and comment boundaries must be machine-identifiable without requiring the tool to parse arbitrary user Markdown. The rendered body therefore uses namespaced HTML comment markers around machine-owned sections and comment/thread blocks. Only exact `context-sync:` markers emitted by the serializer count as structure; enclosed Markdown content is treated as opaque payload and is not recursively parsed for more structure.

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

Within a single invocation, concurrent ticket fetches use `asyncio.TaskGroup` with a configurable semaphore limit. This gives the tool bounded parallelism without giving up structured concurrency. The concurrency limit is a per-process control, not a global scheduler.

The tool does not attempt cross-process rate-limit coordination. Separate invocations targeting different context directories may still contend on shared upstream Linear limits; that is acceptable in the first release. `linear-client` remains responsible for retry and backoff behavior, while `context-sync` is responsible only for its own per-process concurrency and for surfacing rate-limit effects clearly enough that operators can understand slowdowns.

### 3.2 Interface Model

The tool exposes two interfaces:

- an async Python library API for the agent loop and other programmatic callers;
- a thin CLI wrapper for humans and shell-based automation.

The library API is the primary integration surface. It supports full sync, explicit addition of new roots, refresh of existing local context, and diffing the local snapshot against Linear without writing files.

The library receives an authenticated `Linear` client instance from the caller instead of constructing one internally. This keeps authentication, connection reuse, and lifecycle management with the embedding application.

The CLI is a convenience layer over the library API. It is responsible for reading configuration and constructing its own authenticated client using the same environment and credential model used by [`docs/design/linear-client.md`](<design/linear-client.md>).

Detailed method signatures and return types belong in [`docs/design/0-top-level-design.md`](<design/0-top-level-design.md>), not in the problem statement.

---

## 4. Packaging and Integration Boundary

The tool is a separate Python project from both `linear-client` and the agent control plane.

This separation keeps concerns clear:

- `linear-client` remains a reusable API client and authentication layer;
- the context-sync tool owns graph traversal, local persistence, and snapshot management;
- the agent control plane consumes the tool instead of embedding its materialization logic.

The public tool name is `context-sync`. The name intentionally omits `linear` even though the first release is Linear-only, because the underlying snapshot/materialization pattern may later prove useful for adjacent artifact types such as pull requests. The neutral name leaves room for that evolution without changing the current scope of this ADR.

Each invocation operates on exactly one `context_dir`. The tool does not own routing across multiple context directories; higher-level callers decide which workspace snapshot lives in which directory and invoke the tool with the appropriate path.

A `context_dir` is scoped to exactly one Linear workspace in the first release. Tickets from multiple teams in that workspace are allowed in the same snapshot and the same run. Mixed-workspace roots are rejected. This boundary is intentionally set at the workspace level rather than the team level because ticket relationships may legitimately cross team boundaries within one workspace, and splitting by team would risk cutting across the real issue graph for little architectural benefit.

The tool should be distributed the same way as other private internal Python packages, as a private wheel that consumers can install into their own environments.

Package layout and implementation flow details belong in [`docs/design/0-top-level-design.md`](<design/0-top-level-design.md>).

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

`diff` does not acquire the writer lock. If it observes a lock record that is not demonstrably stale, it must fail fast with a clear message instead of proceeding. The reason is not local mutation risk alone: a live `diff` would still consume rate-limited Linear API capacity and could delay the mutating run that already owns the directory. The failure should recommend retrying after the lock clears or after an operator resolves the lock.

---

## 6. Refresh and Diff Strategy

### 6.1 Snapshot Consistency Contract

The first release guarantees a bounded-skew snapshot, not a transactional one.

That means:

- each `sync` or `refresh` run operates on one root set and one traversal configuration;
- all files written by that run come from the same rebuild or refresh pass;
- the snapshot may still reflect upstream changes that happened while the pass was in progress, because the tool does not have a true transactional read boundary from Linear.

The coherence boundary is therefore the local pass, not a single upstream instant in time. The tool should describe the result as a snapshot assembled during one pass, not as an exact capture of one global timestamp.

The manifest records snapshot-pass metadata so humans and callers can see when the current snapshot was assembled and by which mode.

Stronger whole-snapshot atomic commit semantics, where an interrupted run would not leave a partially applied directory update behind, are explicitly deferred to [FW-3](<future-work.md#fw-3-whole-snapshot-atomic-commit>).

Freshness is determined from information stored in the files themselves. Each ticket file carries `last_synced_at`, and the remote source of truth carries issue-level `updated_at`.

For the first release, the base ticket snapshot that `refresh` is responsible for keeping current consists of the persisted ticket metadata, description, and full comment history stored in the main ticket file. Richer activity or history timelines are outside that v1 refresh contract and remain deferred to [FW-5](<future-work.md#fw-5-ticket-history-and-sectioned-ticket-artifacts>).

On refresh:

1. identify all root tickets in the context directory;
2. recompute the currently reachable graph from those roots;
3. compare local `last_synced_at` values against remote `updated_at` values;
4. re-fetch only stale or newly discovered tickets;
5. prune derived tickets that are no longer reachable.

This approach avoids a separate state store and supports efficient incremental refreshes. The steady-state goal is a lightweight refresh path that scales primarily with changed tickets rather than the full size of the context directory, aside from the bounded metadata work required to determine freshness. In other words, the common case should be "check many, fully re-fetch few."

The refresh path uses a batched GraphQL freshness query via `linear-client` rather than one remote call per ticket. The query should include each tracked reachable ticket with its own `updated_at` value, so refresh can compare remote freshness markers against local `last_synced_at` values and then fully re-fetch only the changed or newly discovered tickets. This batch-by-ticket `updated_at` check is the default refresh mechanism, not an optional optimization.

This refresh decision carries one explicit validation requirement before implementation is considered correct: confirm that issue-level `updated_at` advances for every v1-persisted field the main ticket file depends on, especially when comments are added or edited. If that validation fails for any part of the v1 snapshot contract, the refresh design must be revised before low-level design proceeds; a plain issue-level `updated_at` check would not be sufficient.

This is a release-gating validation requirement, not post-release future work. Until it is resolved, `refresh` should be treated as provisionally designed rather than as a settled correctness contract.

The tool also supports a diff mode that compares the current context directory against live Linear data without modifying local files. Diff mode exists for both human debugging and pre-refresh validation.

The first release also defines a minimal observability and verification contract:

- the manifest records the last snapshot mode, started-at timestamp, completed-at timestamp, and whether the most recent mutating run completed successfully;
- `INFO`-level logs should cover run start, run end, mode, root count, reachable ticket count, created/updated/unchanged/removed/error counts, duration, and any catastrophic abort reason;
- `DEBUG`-level logs should cover per-ticket decisions such as "fresh", "stale", "pruned", "renamed due to key change", and alias-based reference resolution;
- lock-handling logs should make it clear whether the run acquired a clean lock, refused an active lock, or preempted a demonstrably stale lock;
- if `diff` refuses to run because a lock record exists that is not demonstrably stale, the user-facing output should make clear that the refusal avoids competing with an in-flight mutating run for rate-limited Linear API capacity;
- after writing a ticket file, the tool re-parses the generated file and verifies critical fields and required structural markers against the in-memory rendered data before considering that write successful.

This verification step is intentionally lightweight. It exists to catch serializer or parser drift early, not to prove full semantic equivalence of every Markdown body block against the upstream API response.

---

## 7. Failure Model

Remote failures are divided into two observable classes: systemic failures that affect the run as a whole, and ticket-scoped failures or absences observed while the broader run is otherwise healthy.

Systemic failures include whole-workspace access loss, invalid authentication, lost network access, and retry-exhausted upstream `5xx` failures reported by `linear-client`. These are catastrophic for a mutating run: the tool must stop immediately and perform no further edits. If such a failure occurs after some local files were already updated, the directory may be left partially updated at the snapshot level in the first release; stronger no-half-sync semantics remain deferred to [FW-3](<future-work.md#fw-3-whole-snapshot-atomic-commit>).

Ticket-scoped absence is modeled only in terms of what the current caller can observe. The tool does not attempt to distinguish "ticket was deleted" from "ticket is no longer visible to this identity" for an individual missing ticket. Both are treated as "not available in the current visible view."

The important exception is root-ticket unavailability. If a requested root during `sync` or `add`, or an already-recorded root during `refresh`, is not available in the current visible view, the run fails immediately because there is no meaningful way to satisfy the caller's explicit request. The tool must not silently remove that root from the manifest.

This leads to the following behavior:

- systemic remote failure is terminal for the run;
- root-ticket unavailability is terminal for that run;
- a previously local non-root ticket that is no longer reachable from the recomputed visible graph is pruned normally;
- an unexpected linked-ticket fetch failure that occurs while the broader run continues is recorded in the result;
- local write failures are terminal because they break the integrity of the local snapshot.

Result types should therefore carry explicit created, updated, unchanged, removed, and errored sets rather than reducing the run to a single success or failure bit.

---

## 8. Operating Guarantees

The tool makes the following guarantees:

- It is read-only with respect to Linear.
- It never writes outside the configured context directory.
- Mutating modes (`sync`, `refresh`, and root-set changes such as `add`) take an exclusive lock on the context directory. Two active writers are not allowed to operate on the same directory concurrently.
- For mutating modes, lock contention is handled explicitly. If the recorded writer is still active, the new run fails fast. If the lock is demonstrably stale, the new run may preempt it and continue. If the tool cannot establish staleness safely, it must fail with a clear stale-lock error rather than guessing.
- `diff` does not acquire the writer lock. It should inspect any existing lock record, and if the lock is not demonstrably stale it must fail fast rather than competing with an in-flight mutating run for rate-limited Linear API capacity. `diff` must not clear or preempt the lock record.
- File writes are atomic so a crash does not leave a partially written ticket file behind.
- A failed or interrupted run may still leave the directory partially updated at the snapshot level in the first release. The tool does not yet guarantee whole-directory atomic commit; stronger semantics are deferred to [FW-3](<future-work.md#fw-3-whole-snapshot-atomic-commit>).
- Re-running sync or refresh without upstream changes should not rewrite files.
- Traversal is always bounded by configured depths plus the ticket cap.
- Rate-limit handling is delegated to `linear-client`; the tool should not introduce a separate, conflicting rate limiter unless experience shows the library layer is insufficient.

These guarantees are part of the architecture because callers need them to trust the local snapshot as an operational input.

For many intended callers, the snapshot lives in git-managed files, which gives the caller a practical recovery path after an interrupted run by reverting to the previous committed state. That mitigation is useful, but it is not the correctness contract of the tool itself. `context-sync` may also be used outside a git repository, so stronger no-half-sync semantics remain architecturally relevant even if they are deferred.

---

## 9. Open Questions

- **OQ-1: Refresh freshness validation against live Linear behavior**

  The first-release `refresh` design assumes issue-level `updated_at` advances whenever any v1-persisted field changes, including comment creation, comment edits, relation changes reflected in the ticket snapshot, and any other field that can affect the rendered main ticket file.

  This assumption must be validated against live Linear behavior before `refresh` is considered implementation-complete. That validation does not require the full tool to exist first; a focused probe or spike against Linear behavior is sufficient.

  If the assumption holds, the current batch `updated_at` freshness design can proceed. If it does not hold, the refresh design must be revised before release, for example by using richer freshness cursors or by narrowing the supported v1 refresh contract.
