# Dependency Map

Navigation guide for agents and developers arriving at the `context-sync`
repository.

## Main Entry Points

| Entry point | Source | Purpose |
|---|---|---|
| `ContextSync` | [`src/context_sync/_sync.py`](../../src/context_sync/_sync.py) | Primary async class — `sync`, `refresh`, `remove`, `diff` methods |
| `main()` | [`src/context_sync/_cli.py`](../../src/context_sync/_cli.py) | CLI entry point registered as `context-sync` console script |
| `__init__.py` | [`src/context_sync/__init__.py`](../../src/context_sync/__init__.py) | Re-exports the full public API surface via `__all__` |

## Key Internal Modules

| Module | Responsibility |
|---|---|
| [`_sync.py`](../../src/context_sync/_sync.py) | Orchestrates all four public operations under the writer lock |
| [`_cli.py`](../../src/context_sync/_cli.py) | Argument parsing, log setup, dispatch to async handlers, exit-code mapping |
| [`_gateway.py`](../../src/context_sync/_gateway.py) | `LinearGateway` protocol and frozen data types for the adapter boundary |
| [`_traversal.py`](../../src/context_sync/_traversal.py) | Tiered BFS graph builder; computes the reachable ticket set from roots |
| [`_pipeline.py`](../../src/context_sync/_pipeline.py) | Ticket fetch, normalization, refresh-cursor computation, and file write |
| [`_renderer.py`](../../src/context_sync/_renderer.py) | Deterministic Markdown rendering of a `TicketBundle` into a ticket file |
| [`_manifest.py`](../../src/context_sync/_manifest.py) | Pydantic schema and I/O for `.context-sync.yml` (workspace, roots, tickets) |
| [`_lock.py`](../../src/context_sync/_lock.py) | Writer-lock lifecycle — acquire, release, inspect, stale-lock preemption |
| [`_signatures.py`](../../src/context_sync/_signatures.py) | Refresh-cursor digest computation (comments, relations) |
| [`_diff.py`](../../src/context_sync/_diff.py) | Non-mutating drift inspection (compares local frontmatter to remote metadata) |
| [`_models.py`](../../src/context_sync/_models.py) | Public result types: `SyncResult`, `DiffResult`, `SyncError`, `DiffEntry` |
| [`_errors.py`](../../src/context_sync/_errors.py) | Exception hierarchy (`ContextSyncError` base, specific subtypes) |
| [`_config.py`](../../src/context_sync/_config.py) | Traversal dimensions, tier definitions, default constants |
| [`_types.py`](../../src/context_sync/_types.py) | `NewType` aliases for domain concepts (`IssueId`, `IssueKey`, etc.) |
| [`_ticket_ref.py`](../../src/context_sync/_ticket_ref.py) | Ticket-reference parsing (issue keys, Linear URLs, UUIDs) |
| [`_io.py`](../../src/context_sync/_io.py) | Atomic file writes with post-write verification |
| [`_yaml.py`](../../src/context_sync/_yaml.py) | Deterministic YAML serialization and frontmatter round-tripping |
| [`_testing.py`](../../src/context_sync/_testing.py) | `FakeLinearGateway`, `make_issue`, `make_context_sync` test harness |
| [`version.py`](../../src/context_sync/version.py) | `__version__` and `__prog_name__` constants |

## Workflow-to-Code Map

### sync (full rebuild)

1. CLI dispatches to `ContextSync.sync` in [`_sync.py`](../../src/context_sync/_sync.py).
2. Writer lock acquired via [`_lock.py`](../../src/context_sync/_lock.py).
3. Root ticket fetched through `LinearGateway.fetch_issue` (protocol in [`_gateway.py`](../../src/context_sync/_gateway.py)).
4. Manifest bootstrapped or loaded via [`_manifest.py`](../../src/context_sync/_manifest.py).
5. Reachable graph built by `build_reachable_graph` in [`_traversal.py`](../../src/context_sync/_traversal.py).
6. Each reachable ticket fetched, normalized, and written by [`_pipeline.py`](../../src/context_sync/_pipeline.py) and [`_renderer.py`](../../src/context_sync/_renderer.py).
7. Unreachable derived tickets pruned; manifest saved; lock released.
8. Canonical test: [`tests/test_sync.py`](../../tests/test_sync.py), [`tests/test_e2e.py`](../../tests/test_e2e.py).

### refresh (incremental update)

1. CLI dispatches to `ContextSync.refresh` in [`_sync.py`](../../src/context_sync/_sync.py).
2. Writer lock acquired; manifest loaded.
3. Root visibility checked via `LinearGateway.get_refresh_issue_metadata`.
4. Missing roots quarantined or removed per policy; recovered roots restored.
5. Reachable graph recomputed from active roots.
6. Composite freshness cursor (issue `updated_at` + `comments_signature` + `relations_signature`) compared via [`_signatures.py`](../../src/context_sync/_signatures.py) and [`_pipeline.py`](../../src/context_sync/_pipeline.py).
7. Only stale or newly discovered tickets re-fetched and rewritten.
8. Canonical test: [`tests/test_refresh.py`](../../tests/test_refresh.py).

### remove (root removal)

1. CLI dispatches to `ContextSync.remove` in [`_sync.py`](../../src/context_sync/_sync.py).
2. Writer lock acquired; manifest loaded; key resolved to UUID.
3. Root removed from manifest; whole-snapshot refresh runs under the same lock.
4. Tickets no longer reachable from any remaining root are pruned.
5. Canonical test: [`tests/test_add_remove_root.py`](../../tests/test_add_remove_root.py).

### diff (drift inspection)

1. CLI dispatches to `ContextSync.diff` in [`_sync.py`](../../src/context_sync/_sync.py).
2. Lock inspected (not acquired); raises `DiffLockError` if a non-stale lock exists.
3. Diff logic in [`_diff.py`](../../src/context_sync/_diff.py) batch-fetches remote metadata and classifies each ticket.
4. Canonical test: [`tests/test_diff.py`](../../tests/test_diff.py).

## Anti-Patterns and Behavioral Constraints

### sync

- Calling `sync()` without a key requires an existing manifest; there is no
  implicit "sync nothing" behavior. Raises `ManifestError` if absent.
- `sync(key=...)` is idempotent for an already-tracked root but still triggers
  a full rebuild of the entire reachable graph, not just the named root.
- Traversal configuration overrides (`dimensions`, `max_tickets_per_root`) are
  persisted to the manifest. Passing them once changes all future runs, not
  just the current call.

### refresh

- `refresh` does not add or remove roots. Use `sync` to add and `remove` to
  delete.
- A root that becomes invisible is quarantined, not deleted, by default. Its
  local file is rewritten with a warning preamble but the content is preserved.
  Passing `missing_root_policy="remove"` (API) or `--missing-root-policy remove`
  (CLI) deletes immediately instead.

### remove

- Removing a root does not guarantee its ticket file is deleted. If the ticket
  is still reachable as a derived node from another root, it is kept.

### diff

- `diff` refuses to run while a non-stale writer lock exists to avoid
  competing for rate-limited Linear API capacity. This is by design, not a bug.

### General

- All mutating operations hold the writer lock for their entire duration. Two
  concurrent `sync` or `refresh` calls on the same directory will fail with
  `ActiveLockError`.
- The `_gateway_override` constructor parameter is a testing hook only. It
  bypasses the `linear-client` dependency entirely. Production callers must use
  the `linear=` parameter (available once M5-1 lands the real gateway).

## Async Ownership

`context-sync` is async-first. The async boundary sits at the `ContextSync`
public methods:

| Layer | Async? | Notes |
|---|---|---|
| CLI (`_cli.py`) | Sync outer / async inner | `main()` is sync; calls `asyncio.run(handler(...))` |
| `ContextSync` methods | Async | `sync`, `refresh`, `remove`, `diff` are all `async def` |
| Gateway protocol | Async | All `LinearGateway` methods are `async def` |
| Traversal engine | Async | `build_reachable_graph` is `async def`; ticket fetches use `asyncio.Semaphore` for concurrency control |
| Pipeline (`_pipeline.py`) | Async | `fetch_tickets` uses semaphore-gated concurrent awaits |
| Lock, manifest, I/O | Sync | File I/O is synchronous (fast local ops; no event-loop blocking risk) |
| Renderer, signatures | Sync | Pure computation, no I/O |

The sole `asyncio.run` call site is in `_cli.py`. Library callers must provide
their own event loop.

## Private Dependency Pointers

| Dependency | Install method | Pinned version | Main entry points | Library documentation |
|---|---|---|---|---|
| [`linear-client`](https://github.com/marcodb226/linear-client) | Editable install from sibling workspace clone (`pip install -e ../linear-client`) | `v1.1.0` | `linear_client.Linear` (authenticated async client) | [`__init__.py` module docstring](../../../linear-client/src/linear_client/__init__.py), [`docs/design/dependency-map.md`](../../../linear-client/docs/design/dependency-map.md), [`docs/pub/`](../../../linear-client/docs/pub/), [`examples/`](../../../linear-client/examples/) |

The multi-root workspace layout places `linear-client` as a sibling clone
alongside `context-sync` (see
[docs/workspace-setup.md](../workspace-setup.md)). The editable install gives
pyright and Pylance full type information across the dependency boundary. The
install command and workspace setup are documented in the
[README](../../README.md#installation).

`context-sync` interacts with `linear-client` exclusively through the
[`LinearGateway`](../../src/context_sync/_gateway.py) protocol boundary — no
direct `linear_client` imports appear outside the future `RealLinearGateway`
adapter (M5-1). The authoritative adapter-boundary definition is in
[docs/design/linear-domain-coverage-audit-v1.1.0.md](linear-domain-coverage-audit-v1.1.0.md).
