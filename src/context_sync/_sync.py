"""
ContextSync — the primary async entry point for context-sync operations.

This module exposes the ``ContextSync`` class whose constructor and method
signatures match the public API defined in the top-level design (§1).  The
``sync`` method implements the full-snapshot rebuild flow (M2-3); the
``refresh`` method implements incremental whole-snapshot update with
quarantine/recovery (M3-1); the remaining async methods are stubs awaiting
later tickets (M3-2 through M3-3).

Design notes
------------
* The ``sync`` flow acquires the writer lock before any mutation and holds it
  across manifest bootstrap, traversal, writes, and pruning so the context
  directory never has two active writers.

* Reachable ticket files are rewritten only when their upstream content or
  role has changed (ADR §8 idempotency guarantee).  Files whose refresh
  cursor and root_state match the on-disk state are skipped and classified
  as ``unchanged``.  Incremental refresh behavior belongs to M3-1.

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
    FORMAT_VERSION,
    resolve_dimensions,
)
from context_sync._errors import ContextSyncError, RootNotFoundError, WorkspaceMismatchError
from context_sync._lock import acquire_lock, release_lock
from context_sync._manifest import (
    MANIFEST_FILENAME,
    ManifestRootEntry,
    ManifestSnapshot,
    ManifestTicketEntry,
    initialize_manifest,
    load_manifest,
    save_manifest,
)
from context_sync._models import DiffResult, SyncError, SyncResult
from context_sync._pipeline import (
    compute_refresh_cursor,
    make_ticket_ref_provider,
    write_ticket,
)
from context_sync._signatures import compute_comments_signature, compute_relations_signature
from context_sync._traversal import build_reachable_graph
from context_sync._yaml import extract_body, parse_frontmatter, serialize_frontmatter

if TYPE_CHECKING:
    from context_sync._gateway import LinearGateway, TicketBundle

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    """Return the current UTC time as an RFC 3339 string with ``Z`` suffix."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_existing_ticket_state(
    context_dir: Path,
    manifest_entry: ManifestTicketEntry | None,
) -> tuple[dict[str, str] | None, str | None, int | None]:
    """
    Read the refresh cursor, root_state, and format_version from a ticket file.

    Returns ``(refresh_cursor, root_state, format_version)`` or
    ``(None, None, None)`` if the file does not exist or its frontmatter
    cannot be parsed.
    """
    if manifest_entry is None:
        return None, None, None
    file_path = context_dir / manifest_entry.current_path
    if not file_path.is_file():
        return None, None, None
    try:
        text = file_path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        fv = fm.get("format_version")
        return fm.get("refresh_cursor"), fm.get("root_state"), fv if isinstance(fv, int) else None
    except Exception:
        return None, None, None


_QUARANTINE_WARNING = (
    "> **Warning:** This root ticket was not available during the last "
    "refresh.\n"
    "> The content below may be stale or no longer visible to the current "
    "caller.\n"
)


def _rewrite_quarantined_ticket(
    *,
    uid: str,
    context_dir: Path,
    manifest: object,
    last_synced_at: str,
) -> None:
    """
    Rewrite an existing ticket file to reflect quarantine state.

    Reads the existing file, updates frontmatter to add ``root_state`` and
    ``quarantined_reason``, inserts the quarantine warning preamble before
    the first ``<!-- context-sync:section`` marker if not already present,
    and writes the file back.

    This is used when a root ticket is no longer visible and cannot be
    re-fetched.  The existing content is preserved but marked as potentially
    stale.
    """
    # Avoid circular import and keep the function signature simple — manifest
    # is duck-typed here for the tickets dict lookup.
    from context_sync._manifest import Manifest

    assert isinstance(manifest, Manifest)
    ticket_entry = manifest.tickets.get(uid)
    if ticket_entry is None:
        return

    file_path = context_dir / ticket_entry.current_path
    if not file_path.is_file():
        return

    text = file_path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    body = extract_body(text)

    # Update frontmatter fields for quarantine.
    fm["root_state"] = "quarantined"
    fm["quarantined_reason"] = "not_available_in_visible_view"
    fm["last_synced_at"] = last_synced_at

    # Insert quarantine warning if not already present.
    if _QUARANTINE_WARNING not in body:
        # Insert before the first section marker or at the start of the body.
        marker = "<!-- context-sync:section"
        marker_pos = body.find(marker)
        if marker_pos > 0:
            body = body[:marker_pos] + _QUARANTINE_WARNING + "\n" + body[marker_pos:]
        else:
            body = _QUARANTINE_WARNING + "\n" + body

    new_content = serialize_frontmatter(fm) + body
    file_path.write_text(new_content, encoding="utf-8")


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
        if self._gateway is None:
            raise ContextSyncError(
                "No gateway available. The real Linear gateway wrapper is not "
                "yet implemented. Use _gateway_override with a LinearGateway "
                "instance."
            )

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
        # content at depth 0.  Per-ticket errors are caught so a single
        # unavailable existing root does not abort the entire run.
        fetched = {root_uuid: root_bundle}
        other_active_roots = [
            uid
            for uid, entry in manifest.roots.items()
            if uid != root_uuid and entry.state == "active"
        ]
        prefetch_failed: set[str] = set()
        if other_active_roots:

            async def _fetch_existing_root(issue_id: str) -> None:
                async with semaphore:
                    try:
                        bundle = await gateway.fetch_issue(issue_id)
                        fetched[bundle.issue.issue_id] = bundle
                    except RootNotFoundError:
                        prefetch_failed.add(issue_id)
                        logger.warning(
                            "Existing root %s unavailable during pre-fetch; "
                            "excluding from traversal",
                            issue_id,
                        )

            async with asyncio.TaskGroup() as tg:
                for uid in other_active_roots:
                    tg.create_task(_fetch_existing_root(uid))

        # -- Build traversal roots dict {uuid: current_key} -------------------
        roots_for_traversal: dict[str, str] = {}
        for uid, entry in manifest.roots.items():
            if entry.state != "active":
                continue
            if uid in prefetch_failed:
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
        # Per-ticket error handling so a single unreachable linked ticket
        # does not abort the entire run (R1).
        created: list[str] = []
        updated: list[str] = []
        unchanged: list[str] = []
        errors: list[SyncError] = []

        missing_ids = [uid for uid in graph.tickets if uid not in fetched]
        if missing_ids:
            fetch_errors: list[tuple[str, str]] = []

            async def _fetch_linked(issue_id: str) -> None:
                async with semaphore:
                    try:
                        bundle = await gateway.fetch_issue(issue_id)
                        fetched[bundle.issue.issue_id] = bundle
                    except RootNotFoundError:
                        ticket_info = graph.tickets[issue_id]
                        fetch_errors.append((ticket_info.issue_key, issue_id))

            async with asyncio.TaskGroup() as tg:
                for uid in missing_ids:
                    tg.create_task(_fetch_linked(uid))

            for issue_key, _uid in fetch_errors:
                errors.append(
                    SyncError(
                        ticket_id=issue_key,
                        error_type="fetch_failed",
                        message=f"Could not fetch linked ticket {issue_key}",
                        retriable=True,
                    )
                )

        # -- Write all reachable tickets --------------------------------------
        last_synced_at = _utc_now()

        for uid in graph.tickets:
            bundle = fetched.get(uid)
            if bundle is None:
                continue  # Error already recorded during fetch

            is_new = uid not in manifest.tickets
            root_state = "active" if uid in manifest.roots else None

            # Skip write when upstream content and role are unchanged (ADR §8).
            if not is_new:
                existing_entry = manifest.tickets.get(uid)
                if (
                    existing_entry is not None
                    and existing_entry.current_key == bundle.issue.issue_key
                ):
                    new_cursor = compute_refresh_cursor(bundle)
                    existing_cursor, existing_root_state, _ = _read_existing_ticket_state(
                        context_dir,
                        existing_entry,
                    )
                    if existing_cursor == new_cursor and existing_root_state == root_state:
                        unchanged.append(bundle.issue.issue_key)
                        continue

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
            unchanged=unchanged,
            removed=removed,
            errors=errors,
        )

    async def refresh(
        self,
        missing_root_policy: Literal["quarantine", "remove"] = "quarantine",
    ) -> SyncResult:
        """
        Incremental whole-snapshot update from all existing roots.

        Acquires the writer lock, loads the existing manifest, checks root
        visibility, applies the missing-root policy (quarantine or remove),
        recovers previously quarantined roots that are now visible, recomputes
        the reachable graph from active roots, batch-checks freshness via the
        composite refresh cursor, re-fetches only stale or newly discovered
        tickets, prunes derived tickets no longer reachable, and releases the
        lock.

        Parameters
        ----------
        missing_root_policy:
            How to handle existing manifest roots that are no longer visible.
            ``"quarantine"`` (default) marks them quarantined; ``"remove"``
            deletes them immediately.

        Returns
        -------
        SyncResult
            Created, updated, unchanged, removed, and errored ticket sets.

        Raises
        ------
        ManifestError
            If the manifest does not exist or is invalid.
        ActiveLockError
            If a non-stale writer lock is already held.
        StaleLockError
            If lock staleness cannot be determined safely.
        SystemicRemoteError
            If a systemic remote failure aborts the run.
        WriteError
            If a local file write or post-write verification fails.
        """
        if self._gateway is None:
            raise ContextSyncError(
                "No gateway available. The real Linear gateway wrapper is not "
                "yet implemented. Use _gateway_override with a LinearGateway "
                "instance."
            )

        context_dir = self._context_dir
        gateway = self._gateway
        semaphore = self._semaphore

        started_at = _utc_now()
        mono_start = time.monotonic()
        lock = acquire_lock(context_dir, "refresh", acquired_at=started_at)

        try:
            return await self._refresh_under_lock(
                missing_root_policy=missing_root_policy,
                context_dir=context_dir,
                gateway=gateway,
                semaphore=semaphore,
                started_at=started_at,
                mono_start=mono_start,
            )
        finally:
            release_lock(context_dir, lock.writer_id)

    async def _refresh_under_lock(
        self,
        *,
        missing_root_policy: Literal["quarantine", "remove"],
        context_dir: Path,
        gateway: LinearGateway,
        semaphore: asyncio.Semaphore,
        started_at: str,
        mono_start: float,
    ) -> SyncResult:
        """
        Core refresh logic executed while the writer lock is held.

        Returns
        -------
        SyncResult
        """
        # -- Load existing manifest (must exist for refresh) -------------------
        manifest = load_manifest(context_dir)

        effective_dims = dict(self._dimensions)
        effective_cap = self._max_tickets_per_root

        # -- Record in-progress snapshot metadata -----------------------------
        manifest.snapshot = ManifestSnapshot(
            mode="refresh",
            started_at=started_at,
            completed_successfully=False,
        )

        errors: list[SyncError] = []
        removed_by_policy: list[str] = []

        # -- Batch-check root visibility --------------------------------------
        root_uuids = list(manifest.roots.keys())
        if not root_uuids:
            # No roots in manifest — nothing to refresh.
            completed_at = _utc_now()
            manifest.snapshot = ManifestSnapshot(
                mode="refresh",
                started_at=started_at,
                completed_at=completed_at,
                completed_successfully=True,
            )
            save_manifest(manifest, context_dir)
            return SyncResult()

        root_meta = await gateway.get_refresh_issue_metadata(root_uuids)

        # -- Apply missing-root policy and quarantine recovery ----------------
        for uid in root_uuids:
            entry = manifest.roots[uid]
            meta = root_meta.get(uid)
            is_visible = meta is not None and meta.visible

            if entry.state == "active" and not is_visible:
                # Root is no longer visible — apply policy.
                if missing_root_policy == "quarantine":
                    manifest.roots[uid] = ManifestRootEntry(
                        state="quarantined",
                        quarantined_reason="not_available_in_visible_view",
                    )
                    # Rewrite ticket file with quarantine markers if it exists.
                    ticket_entry = manifest.tickets.get(uid)
                    if ticket_entry is not None:
                        _rewrite_quarantined_ticket(
                            uid=uid,
                            context_dir=context_dir,
                            manifest=manifest,
                            last_synced_at=started_at,
                        )
                    errors.append(
                        SyncError(
                            ticket_id=(
                                meta.issue_key
                                if meta is not None
                                else manifest.tickets[uid].current_key
                                if uid in manifest.tickets
                                else uid
                            ),
                            error_type="root_quarantined",
                            message="Root ticket not available in the current visible view",
                            retriable=True,
                        )
                    )
                    logger.info("refresh: quarantined root %s", uid)
                else:
                    # missing_root_policy == "remove"
                    ticket_entry = manifest.tickets.get(uid)
                    removed_key = (
                        ticket_entry.current_key
                        if ticket_entry is not None
                        else meta.issue_key
                        if meta is not None
                        else uid
                    )
                    if ticket_entry is not None:
                        file_path = context_dir / ticket_entry.current_path
                        if file_path.is_file():
                            file_path.unlink()
                        del manifest.tickets[uid]
                    del manifest.roots[uid]
                    removed_by_policy.append(removed_key)
                    logger.info("refresh: removed unavailable root %s", uid)

            elif entry.state == "quarantined" and is_visible:
                # Previously quarantined root is visible again — recover.
                manifest.roots[uid] = ManifestRootEntry(state="active")
                logger.info("refresh: recovered quarantined root %s", uid)

        # -- Pre-fetch all active root bundles --------------------------------
        active_root_uuids = [
            uid for uid, entry in manifest.roots.items() if entry.state == "active"
        ]

        fetched: dict[str, TicketBundle] = {}
        prefetch_failed: set[str] = set()

        if active_root_uuids:

            async def _fetch_root(issue_id: str) -> None:
                async with semaphore:
                    try:
                        bundle = await gateway.fetch_issue(issue_id)
                        fetched[bundle.issue.issue_id] = bundle
                    except RootNotFoundError:
                        prefetch_failed.add(issue_id)
                        logger.warning(
                            "Existing root %s unavailable during pre-fetch; "
                            "excluding from traversal",
                            issue_id,
                        )

            async with asyncio.TaskGroup() as tg:
                for uid in active_root_uuids:
                    tg.create_task(_fetch_root(uid))

        # -- Build traversal roots dict {uuid: current_key} -------------------
        roots_for_traversal: dict[str, str] = {}
        for uid in active_root_uuids:
            if uid in prefetch_failed:
                continue
            if uid in fetched:
                roots_for_traversal[uid] = fetched[uid].issue.issue_key
            elif uid in manifest.tickets:
                roots_for_traversal[uid] = manifest.tickets[uid].current_key

        logger.info(
            "refresh: started — active_roots=%d, quarantined=%d",
            len(roots_for_traversal),
            sum(1 for e in manifest.roots.values() if e.state == "quarantined"),
        )

        # -- Build Tier 3 ticket_ref provider ---------------------------------
        provider = make_ticket_ref_provider(
            fetched,
            gateway=gateway,
            semaphore=semaphore,
            aliases=dict(manifest.aliases) if manifest.aliases else None,
        )

        # -- Build reachable graph from active roots --------------------------
        graph = await build_reachable_graph(
            roots=roots_for_traversal,
            dimensions=effective_dims,
            max_tickets_per_root=effective_cap,
            gateway=gateway,
            ticket_ref_fn=provider,
        )

        # -- Batch-check freshness for all tracked reachable tickets ----------
        reachable_uuids = list(graph.tickets.keys())
        stale_uuids: set[str] = set()
        newly_discovered: set[str] = set()

        # Identify newly discovered tickets (in graph but not in manifest).
        for uid in reachable_uuids:
            if uid not in manifest.tickets:
                newly_discovered.add(uid)

        # For tickets already in the manifest, batch-query remote cursors.
        tracked_reachable = [uid for uid in reachable_uuids if uid in manifest.tickets]

        if tracked_reachable:
            remote_issue_meta = await gateway.get_refresh_issue_metadata(tracked_reachable)
            remote_comment_meta = await gateway.get_refresh_comment_metadata(tracked_reachable)
            remote_relation_meta = await gateway.get_refresh_relation_metadata(tracked_reachable)

            for uid in tracked_reachable:
                # Build remote cursor from batch metadata.
                issue_meta = remote_issue_meta.get(uid)
                if issue_meta is None:
                    # Ticket not visible remotely — treat as stale so it can
                    # be handled during the fetch phase.
                    stale_uuids.add(uid)
                    continue

                remote_issue_updated_at = issue_meta.updated_at

                comment_data = remote_comment_meta.get(uid, ([], []))
                remote_comments_sig = compute_comments_signature(
                    comment_data[0],
                    comment_data[1],
                )

                relation_data = remote_relation_meta.get(uid, [])
                remote_relations_sig = compute_relations_signature(relation_data)

                remote_cursor = {
                    "issue_updated_at": remote_issue_updated_at,
                    "comments_signature": remote_comments_sig,
                    "relations_signature": remote_relations_sig,
                }

                # Load local cursor.
                local_cursor, _local_root_state, local_fv = _read_existing_ticket_state(
                    context_dir,
                    manifest.tickets.get(uid),
                )

                # Staleness rules: missing/partial/invalid/format-incompatible
                # local cursor, or any component differs.
                if local_fv is None or local_fv < FORMAT_VERSION:
                    stale_uuids.add(uid)
                elif local_cursor is None:
                    stale_uuids.add(uid)
                elif local_cursor != remote_cursor:
                    stale_uuids.add(uid)

        # -- Fetch stale and newly discovered tickets -------------------------
        created: list[str] = []
        updated: list[str] = []
        unchanged: list[str] = []

        fetch_targets = list(stale_uuids | newly_discovered)
        # Remove tickets already fetched during root pre-fetch.
        to_fetch = [uid for uid in fetch_targets if uid not in fetched]

        if to_fetch:
            fetch_errors: list[tuple[str, str]] = []

            async def _fetch_linked(issue_id: str) -> None:
                async with semaphore:
                    try:
                        bundle = await gateway.fetch_issue(issue_id)
                        fetched[bundle.issue.issue_id] = bundle
                    except RootNotFoundError:
                        ticket_info = graph.tickets.get(issue_id)
                        issue_key = ticket_info.issue_key if ticket_info else issue_id
                        fetch_errors.append((issue_key, issue_id))

            async with asyncio.TaskGroup() as tg:
                for uid in to_fetch:
                    tg.create_task(_fetch_linked(uid))

            for issue_key, _uid in fetch_errors:
                errors.append(
                    SyncError(
                        ticket_id=issue_key,
                        error_type="fetch_failed",
                        message=f"Could not fetch linked ticket {issue_key}",
                        retriable=True,
                    )
                )

        # -- Write stale/new tickets, classify unchanged ----------------------
        last_synced_at = _utc_now()

        for uid in reachable_uuids:
            if uid in stale_uuids or uid in newly_discovered:
                bundle = fetched.get(uid)
                if bundle is None:
                    continue  # Error already recorded during fetch

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
            else:
                # Ticket is fresh — check root_state consistency.
                bundle = fetched.get(uid)
                current_root_state = "active" if uid in manifest.roots else None
                _existing_cursor, existing_root_state, _ = _read_existing_ticket_state(
                    context_dir,
                    manifest.tickets.get(uid),
                )
                if bundle is not None and existing_root_state != current_root_state:
                    # Root state changed (e.g. recovered from quarantine) —
                    # rewrite even though content is fresh.
                    write_ticket(
                        bundle,
                        root_state=current_root_state,
                        last_synced_at=last_synced_at,
                        context_dir=context_dir,
                        manifest=manifest,
                    )
                    updated.append(bundle.issue.issue_key)
                else:
                    ticket_entry = manifest.tickets.get(uid)
                    if ticket_entry is not None:
                        unchanged.append(ticket_entry.current_key)

        # -- Prune derived tickets no longer reachable ------------------------
        removed: list[str] = list(removed_by_policy)
        reachable_set = set(graph.tickets.keys())
        for uid in list(manifest.tickets.keys()):
            if uid not in reachable_set and uid not in manifest.roots:
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
            mode="refresh",
            started_at=started_at,
            completed_at=completed_at,
            completed_successfully=True,
        )
        save_manifest(manifest, context_dir)

        duration = time.monotonic() - mono_start
        logger.info(
            "refresh: completed — reachable=%d, created=%d, updated=%d, "
            "unchanged=%d, removed=%d, errors=%d, duration=%.1fs",
            len(graph.tickets),
            len(created),
            len(updated),
            len(unchanged),
            len(removed),
            len(errors),
            duration,
        )

        return SyncResult(
            created=created,
            updated=updated,
            unchanged=unchanged,
            removed=removed,
            errors=errors,
        )

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
