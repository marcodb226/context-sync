"""
ContextSync — the primary async entry point for context-sync operations.

This module exposes the ``ContextSync`` class whose constructor and method
signatures match the public API defined in the top-level design (§1).  The
``sync`` method implements the full-snapshot rebuild flow (M2-3); the
remaining async methods are stubs awaiting later tickets (M3-1 through M3-3).

Design notes
------------
* The ``sync`` flow acquires the writer lock before any mutation and holds it
  across manifest bootstrap, traversal, writes, and pruning so the context
  directory never has two active writers.

* All reachable ticket files are rewritten regardless of local freshness
  markers.  Incremental refresh behavior belongs to M3-1.

* Derived tickets that are no longer reachable from the recomputed root set
  are pruned.  Root tickets are never pruned automatically.

* Per-call ``dimensions`` and ``max_tickets_per_root`` overrides are merged
  with the instance defaults and stored in the manifest so the snapshot
  records the exact configuration used.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from context_sync._config import (
    DEFAULT_CONCURRENCY_LIMIT,
    DEFAULT_MAX_TICKETS_PER_ROOT,
    resolve_dimensions,
)
from context_sync._errors import ContextSyncError, WorkspaceMismatchError
from context_sync._lock import acquire_lock, release_lock
from context_sync._manifest import (
    MANIFEST_FILENAME,
    ManifestRootEntry,
    ManifestSnapshot,
    initialize_manifest,
    load_manifest,
    save_manifest,
)
from context_sync._models import DiffResult, SyncError, SyncResult
from context_sync._pipeline import (
    fetch_tickets,
    make_ticket_ref_provider,
    write_ticket,
)
from context_sync._traversal import build_reachable_graph

if TYPE_CHECKING:
    from context_sync._gateway import LinearGateway

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    """Return the current UTC time as an RFC 3339 string with ``Z`` suffix."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class ContextSync:
    """
    Deterministic Linear ticket-neighborhood snapshot manager.

    The caller provides an authenticated ``linear-client`` ``Linear`` instance
    (or, for testing, a ``LinearGateway`` via ``_gateway_override``), a target
    directory, and optional traversal configuration.  All mutating and
    read-only operations are async methods.

    Parameters
    ----------
    linear:
        An authenticated ``linear_client.Linear`` instance.  Ignored when
        *_gateway_override* is provided.
    context_dir:
        Path to the context directory that will hold ticket files, the
        manifest, and the lock record.
    dimensions:
        Per-dimension traversal depths.  ``None`` uses the built-in defaults.
        Unknown dimension names and negative depths are rejected.
    max_tickets_per_root:
        Per-root ticket cap for traversal (ADR §1.1).
    concurrency_limit:
        ``asyncio.Semaphore`` limit for concurrent ticket fetches within a
        single invocation (ADR §3.1).  This is a per-process control; the
        tool does not attempt cross-process coordination.
    _gateway_override:
        **Testing hook.**  When provided, this gateway is used directly
        instead of wrapping *linear*.  Production callers should never set
        this parameter.

    Raises
    ------
    ContextSyncError
        If neither *linear* nor *_gateway_override* is provided.
    ValueError
        If *dimensions* contains unknown names or negative depths, or if
        *max_tickets_per_root* or *concurrency_limit* is not positive.
    """

    def __init__(
        self,
        linear: Any = None,
        context_dir: Path | str = ".",
        dimensions: dict[str, int] | None = None,
        *,
        max_tickets_per_root: int = DEFAULT_MAX_TICKETS_PER_ROOT,
        concurrency_limit: int = DEFAULT_CONCURRENCY_LIMIT,
        _gateway_override: LinearGateway | None = None,
    ) -> None:
        if _gateway_override is not None:
            self._gateway: LinearGateway = _gateway_override
        elif linear is not None:
            # The real gateway wrapping linear-client will be created by a
            # later implementation ticket.  For now, store the raw reference.
            self._linear = linear
            self._gateway = None  # type: ignore[assignment]
        else:
            raise ContextSyncError("Either 'linear' or '_gateway_override' must be provided.")

        self._context_dir = Path(context_dir)
        self._dimensions = resolve_dimensions(dimensions)

        if max_tickets_per_root < 1:
            raise ValueError(f"max_tickets_per_root must be positive, got {max_tickets_per_root}")
        self._max_tickets_per_root = max_tickets_per_root

        if concurrency_limit < 1:
            raise ValueError(f"concurrency_limit must be positive, got {concurrency_limit}")
        self._concurrency_limit = concurrency_limit
        self._semaphore = asyncio.Semaphore(concurrency_limit)

    # -- Public properties --------------------------------------------------

    @property
    def context_dir(self) -> Path:
        """The context directory this syncer operates on."""
        return self._context_dir

    @property
    def dimensions(self) -> dict[str, int]:
        """Active traversal-depth configuration (dimension → max hops)."""
        return dict(self._dimensions)

    @property
    def max_tickets_per_root(self) -> int:
        """Per-root ticket cap."""
        return self._max_tickets_per_root

    @property
    def concurrency_limit(self) -> int:
        """Semaphore limit for concurrent ticket fetches."""
        return self._concurrency_limit

    # -- Async entry points -------------------------------------------------
    #
    # Stub implementations for flows not yet owned by this ticket:
    #   refresh     → M3-1
    #   add         → M3-2
    #   remove_root → M3-2
    #   diff        → M3-3

    async def sync(
        self,
        root_ticket_id: str,
        max_tickets_per_root: int | None = None,
        dimensions: dict[str, int] | None = None,
    ) -> SyncResult:
        """
        Full-snapshot rebuild from *root_ticket_id* and all existing roots.

        Acquires the writer lock, fetches the requested root, validates its
        workspace against the context directory, adds the root to the manifest,
        recomputes the reachable graph from all active roots, rewrites every
        reachable ticket file, prunes derived tickets that are no longer
        reachable, and releases the lock.

        Parameters
        ----------
        root_ticket_id:
            Issue key or Linear issue URL of the root to add/refresh.
        max_tickets_per_root:
            Override the instance-level per-root cap for this call.
        dimensions:
            Override the instance-level dimension depths for this call.

        Returns
        -------
        SyncResult
            Created, updated, unchanged, removed, and errored ticket sets.

        Raises
        ------
        RootNotFoundError
            If the requested root ticket is not available.
        WorkspaceMismatchError
            If the root ticket belongs to a different workspace than the
            context directory.
        ActiveLockError
            If a non-stale writer lock is already held.
        StaleLockError
            If lock staleness cannot be determined safely.
        SystemicRemoteError
            If a systemic remote failure aborts the run.
        WriteError
            If a local file write or post-write verification fails.
        """
        effective_dims = (
            resolve_dimensions(dimensions) if dimensions is not None else dict(self._dimensions)
        )
        effective_cap = (
            max_tickets_per_root if max_tickets_per_root is not None else self._max_tickets_per_root
        )
        context_dir = self._context_dir
        gateway = self._gateway
        semaphore = self._semaphore

        started_at = _utc_now()
        mono_start = time.monotonic()
        lock = acquire_lock(context_dir, "sync", acquired_at=started_at)

        try:
            return await self._sync_under_lock(
                root_ticket_id=root_ticket_id,
                effective_dims=effective_dims,
                effective_cap=effective_cap,
                context_dir=context_dir,
                gateway=gateway,
                semaphore=semaphore,
                started_at=started_at,
                mono_start=mono_start,
            )
        finally:
            release_lock(context_dir, lock.writer_id)

    async def _sync_under_lock(
        self,
        *,
        root_ticket_id: str,
        effective_dims: dict[str, int],
        effective_cap: int,
        context_dir: Path,
        gateway: LinearGateway,
        semaphore: asyncio.Semaphore,
        started_at: str,
        mono_start: float,
    ) -> SyncResult:
        """
        Core sync logic executed while the writer lock is held.

        Separated from :meth:`sync` so the ``try/finally`` release-lock
        wrapper remains concise.  All parameters are pre-resolved by the
        caller; this method does not read instance state directly.

        Returns
        -------
        SyncResult
        """
        # -- Fetch the requested root ticket ----------------------------------
        root_bundle = await gateway.fetch_issue(root_ticket_id)
        root_uuid = root_bundle.issue.issue_id

        # -- Load or initialize manifest --------------------------------------
        manifest_path = context_dir / MANIFEST_FILENAME
        if manifest_path.is_file():
            manifest = load_manifest(context_dir)
            if manifest.workspace_id != root_bundle.workspace.workspace_id:
                raise WorkspaceMismatchError(
                    f"Root ticket {root_bundle.issue.issue_key} belongs to "
                    f"workspace {root_bundle.workspace.workspace_slug!r} "
                    f"({root_bundle.workspace.workspace_id}), but the context "
                    f"directory is bound to workspace "
                    f"{manifest.workspace_slug!r} ({manifest.workspace_id})"
                )
        else:
            manifest = initialize_manifest(
                root_bundle.workspace,
                effective_dims,
                effective_cap,
            )

        # -- Update manifest configuration -----------------------------------
        manifest.dimensions = dict(effective_dims)
        manifest.max_tickets_per_root = effective_cap

        # -- Record in-progress snapshot metadata -----------------------------
        manifest.snapshot = ManifestSnapshot(
            mode="sync",
            started_at=started_at,
            completed_successfully=False,
        )

        # -- Add the requested root to the manifest root set ------------------
        manifest.roots[root_uuid] = ManifestRootEntry(state="active")

        # -- Pre-fetch all active root bundles --------------------------------
        # The requested root is already fetched.  Other active roots are
        # fetched now so that the Tier 3 ticket_ref provider can scan their
        # content at depth 0.
        fetched = {root_uuid: root_bundle}
        other_active_roots = [
            uid
            for uid, entry in manifest.roots.items()
            if uid != root_uuid and entry.state == "active"
        ]
        if other_active_roots:
            more = await fetch_tickets(
                other_active_roots,
                gateway=gateway,
                semaphore=semaphore,
            )
            fetched.update(more)

        # -- Build traversal roots dict {uuid: current_key} -------------------
        roots_for_traversal: dict[str, str] = {}
        for uid, entry in manifest.roots.items():
            if entry.state != "active":
                continue
            if uid in fetched:
                roots_for_traversal[uid] = fetched[uid].issue.issue_key
            elif uid in manifest.tickets:
                roots_for_traversal[uid] = manifest.tickets[uid].current_key

        logger.info(
            "sync: started — root_count=%d, max_tickets_per_root=%d",
            len(roots_for_traversal),
            effective_cap,
        )

        # -- Build Tier 3 ticket_ref provider ---------------------------------
        provider = make_ticket_ref_provider(
            fetched,
            gateway=gateway,
            semaphore=semaphore,
            aliases=dict(manifest.aliases) if manifest.aliases else None,
        )

        # -- Build reachable graph from all active roots ----------------------
        graph = await build_reachable_graph(
            roots=roots_for_traversal,
            dimensions=effective_dims,
            max_tickets_per_root=effective_cap,
            gateway=gateway,
            ticket_ref_fn=provider,
        )

        # -- Fetch remaining reachable tickets --------------------------------
        missing_ids = [uid for uid in graph.tickets if uid not in fetched]
        if missing_ids:
            more = await fetch_tickets(
                missing_ids,
                gateway=gateway,
                semaphore=semaphore,
            )
            fetched.update(more)

        # -- Write all reachable tickets --------------------------------------
        created: list[str] = []
        updated: list[str] = []
        errors: list[SyncError] = []
        last_synced_at = _utc_now()

        for uid in graph.tickets:
            bundle = fetched.get(uid)
            if bundle is None:
                ticket_info = graph.tickets[uid]
                errors.append(
                    SyncError(
                        ticket_id=ticket_info.issue_key,
                        error_type="fetch_failed",
                        message=f"Could not fetch ticket {ticket_info.issue_key}",
                        retriable=True,
                    )
                )
                continue

            is_new = uid not in manifest.tickets
            root_state = "active" if uid in manifest.roots else None

            write_ticket(
                bundle,
                root_state=root_state,
                last_synced_at=last_synced_at,
                context_dir=context_dir,
                manifest=manifest,
            )

            if is_new:
                created.append(bundle.issue.issue_key)
            else:
                updated.append(bundle.issue.issue_key)

        # -- Prune derived tickets no longer reachable ------------------------
        removed: list[str] = []
        reachable_uuids = set(graph.tickets.keys())
        for uid in list(manifest.tickets.keys()):
            if uid not in reachable_uuids and uid not in manifest.roots:
                entry = manifest.tickets[uid]
                file_path = context_dir / entry.current_path
                if file_path.is_file():
                    file_path.unlink()
                    logger.debug("Pruned derived ticket: %s", entry.current_key)
                removed.append(entry.current_key)
                del manifest.tickets[uid]

        # -- Finalize snapshot metadata and persist manifest ------------------
        completed_at = _utc_now()
        manifest.snapshot = ManifestSnapshot(
            mode="sync",
            started_at=started_at,
            completed_at=completed_at,
            completed_successfully=True,
        )
        save_manifest(manifest, context_dir)

        duration = time.monotonic() - mono_start
        logger.info(
            "sync: completed — reachable=%d, created=%d, updated=%d, "
            "removed=%d, errors=%d, roots_at_cap=%d, duration=%.1fs",
            len(graph.tickets),
            len(created),
            len(updated),
            len(removed),
            len(errors),
            len(graph.roots_at_cap),
            duration,
        )

        return SyncResult(
            created=created,
            updated=updated,
            removed=removed,
            errors=errors,
        )

    async def refresh(
        self,
        missing_root_policy: Literal["quarantine", "remove"] = "quarantine",
    ) -> SyncResult:
        """
        Incremental whole-snapshot update from all existing roots.

        Parameters
        ----------
        missing_root_policy:
            How to handle existing manifest roots that are no longer visible.
            ``"quarantine"`` (default) marks them quarantined; ``"remove"``
            deletes them immediately.

        Returns
        -------
        SyncResult
        """
        raise NotImplementedError("refresh will be implemented by M3-1")

    async def add(self, ticket_ref: str) -> SyncResult:
        """
        Add a new root and run whole-snapshot refresh.

        Parameters
        ----------
        ticket_ref:
            Issue key or Linear issue URL of the ticket to add as a root.

        Returns
        -------
        SyncResult
        """
        raise NotImplementedError("add will be implemented by M3-2")

    async def remove_root(self, ticket_ref: str) -> SyncResult:
        """
        Remove a root and run whole-snapshot refresh.

        Parameters
        ----------
        ticket_ref:
            Issue key or Linear issue URL of the root to remove.

        Returns
        -------
        SyncResult
        """
        raise NotImplementedError("remove_root will be implemented by M3-2")

    async def diff(self) -> DiffResult:
        """
        Compare local snapshot to live Linear state without modifying files.

        Returns
        -------
        DiffResult
        """
        raise NotImplementedError("diff will be implemented by M3-3")
