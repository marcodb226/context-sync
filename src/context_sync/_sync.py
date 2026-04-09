"""
ContextSync — the primary async entry point for context-sync operations.

This module exposes the ``ContextSync`` class whose constructor and method
signatures match the public API defined in the top-level design (§1).  The
``sync`` method implements the full-snapshot rebuild flow (M2-3); the
``refresh`` method implements incremental whole-snapshot update with
quarantine/recovery (M3-1); the ``remove`` method implements root removal
(M3-2); the ``diff`` method implements the non-mutating drift inspection flow
(M3-3).  All root-addition behavior (alias-based local resolution, early URL slug
validation, quarantine recovery) is consolidated in ``_sync_under_lock``.

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
from context_sync._diff import run_diff
from context_sync._errors import (
    ContextSyncError,
    ManifestError,
    RootNotFoundError,
    RootNotInManifestError,
    WorkspaceMismatchError,
)
from context_sync._io import atomic_write
from context_sync._lock import acquire_lock, release_lock
from context_sync._manifest import (
    MANIFEST_FILENAME,
    Manifest,
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
from context_sync._ticket_ref import _normalize_ticket_ref, _resolve_ref_to_uuid
from context_sync._traversal import TraversalResult, build_reachable_graph
from context_sync._types import IssueId, IssueKey
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
    except (ValueError, KeyError, ManifestError):
        # Frontmatter is corrupt or missing expected structure — treat the
        # ticket as stale so it will be re-fetched.
        logger.debug("Could not parse ticket state from %s; treating as stale", file_path)
        return None, None, None


_QUARANTINE_WARNING = (
    "> **Warning:** This root ticket was not available during the last "
    "refresh.\n"
    "> The content below may be stale or no longer visible to the current "
    "caller.\n"
)


def _rewrite_quarantined_ticket(
    *,
    uid: IssueId,
    context_dir: Path,
    manifest: Manifest,
    last_synced_at: str,
) -> None:
    """
    Rewrite an existing ticket file to reflect quarantine state.

    Reads the existing file, updates frontmatter to add ``root_state`` and
    ``quarantined_reason``, inserts the quarantine warning preamble before
    the first ``<!-- context-sync:section`` marker if not already present,
    and writes the file back atomically.

    This is used when a root ticket is no longer visible and cannot be
    re-fetched.  The existing content is preserved but marked as potentially
    stale.

    Parameters
    ----------
    uid:
        Issue UUID of the quarantined root.
    context_dir:
        Root directory of the context-sync snapshot.
    manifest:
        The loaded manifest.
    last_synced_at:
        RFC 3339 timestamp for the ``last_synced_at`` frontmatter field.
    """
    ticket_entry = manifest.tickets.get(uid)
    if ticket_entry is None:
        logger.warning(
            "Cannot rewrite quarantined ticket %s: no manifest ticket entry",
            uid,
        )
        return

    file_path = context_dir / ticket_entry.current_path
    if not file_path.is_file():
        logger.warning(
            "Cannot rewrite quarantined ticket %s: file does not exist at %s",
            uid,
            file_path,
        )
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
    atomic_write(file_path, new_content)


class ContextSync:
    """
    Deterministic Linear ticket-neighborhood snapshot manager.

    The caller provides an authenticated ``linear-client`` ``Linear`` instance
    (or, for testing, a ``LinearGateway`` via ``_gateway_override``), a target
    directory, and optional traversal configuration.  When *linear* is
    provided, a :class:`RealLinearGateway` is created automatically.
    All mutating and read-only operations are async methods.

    Parameters
    ----------
    linear:
        An authenticated ``linear_client.Linear`` instance.  Wrapped in a
        :class:`RealLinearGateway` automatically.  Ignored when
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
            from context_sync._real_gateway import RealLinearGateway

            self._gateway = RealLinearGateway(linear)
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
        """The context directory this instance operates on."""
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

    async def sync(
        self,
        key: str | None = None,
        max_tickets_per_root: int | None = None,
        dimensions: dict[str, int] | None = None,
    ) -> SyncResult:
        """
        Fully rebuild the snapshot from all tracked roots.

        With *key*, add or reaffirm that root first.  Without *key*, rebuild
        all currently tracked roots without changing root membership.

        When *max_tickets_per_root* or *dimensions* are not supplied, the
        manifest's existing traversal configuration is preserved.  When
        overrides are explicitly given, the new values are persisted.

        Parameters
        ----------
        key:
            Issue key or Linear issue URL of the root to track.  ``None``
            performs a full rebuild of all currently tracked roots with no
            root-membership change.
        max_tickets_per_root:
            Override the per-root cap for this call and persist the new value.
            ``None`` preserves the manifest's existing value.
        dimensions:
            Override the dimension depths for this call and persist the new
            values.  ``None`` preserves the manifest's existing configuration.

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
        ManifestError
            If *key* is ``None`` and no manifest exists (nothing to rebuild).
        ActiveLockError
            If a non-stale writer lock is already held.
        StaleLockError
            If lock staleness cannot be determined safely.
        SystemicRemoteError
            If a systemic remote failure aborts the run.
        WriteError
            If a local file write or post-write verification fails.

        Side Effects
        ------------
        Acquires and releases the writer lock on the context directory.
        Creates or overwrites ticket Markdown files and the
        ``.context-sync.yml`` manifest.  Prunes files for tickets no longer
        reachable from any root.  Persists any *dimensions* or
        *max_tickets_per_root* overrides into the manifest for future runs.

        Mutability
        ----------
        Mutates the context directory on disk (manifest, ticket files, lock
        file).  Does not mutate the ``ContextSync`` instance itself or any
        argument.

        Idempotency
        -----------
        Calling ``sync(key=K)`` twice in succession with the same remote
        state produces the same on-disk result; the second call classifies
        all tickets as ``unchanged``.  Calling ``sync()`` (no key) is also
        idempotent in that sense.  However, traversal configuration overrides
        are persisted, so passing different *dimensions* or
        *max_tickets_per_root* values changes the manifest even if ticket
        content is unchanged.

        Thread Safety
        -------------
        Not thread-safe.  The writer lock prevents concurrent *processes*
        from mutating the same directory, but two coroutines sharing one
        ``ContextSync`` instance must not call mutating methods concurrently.

        Example
        -------
        .. code-block:: python

            from context_sync import ContextSync

            ctx = ContextSync(linear=client, context_dir="./context")

            # Add a root and rebuild
            result = await ctx.sync(key="TEAM-42")
            print(result.created)  # e.g. ['TEAM-42', 'TEAM-43']

            # Full rebuild of all tracked roots
            result = await ctx.sync()

        Behavioral Constraints
        ----------------------
        Requires an authenticated ``LinearGateway`` via the ``linear=``
        constructor parameter.  ``sync()`` without a key requires a
        pre-existing manifest; it does not create an empty snapshot.
        ``sync(key=K)`` for an already-tracked root triggers a full rebuild
        of the entire reachable graph, not just the named root.
        """
        context_dir = self._context_dir
        gateway = self._gateway
        semaphore = self._semaphore

        started_at = _utc_now()
        mono_start = time.monotonic()
        lock = acquire_lock(context_dir, "sync", acquired_at=started_at)

        try:
            if key is not None:
                return await self._sync_under_lock(
                    key=key,
                    dimensions_override=dimensions,
                    cap_override=max_tickets_per_root,
                    context_dir=context_dir,
                    gateway=gateway,
                    semaphore=semaphore,
                    started_at=started_at,
                    mono_start=mono_start,
                )
            else:
                return await self._standalone_sync_under_lock(
                    dimensions_override=dimensions,
                    cap_override=max_tickets_per_root,
                    context_dir=context_dir,
                    gateway=gateway,
                    semaphore=semaphore,
                    started_at=started_at,
                    mono_start=mono_start,
                )
        except BaseException as exc:
            duration = time.monotonic() - mono_start
            logger.info("sync: aborted — %s, duration=%.1fs", exc, duration)
            raise
        finally:
            release_lock(context_dir, lock.writer_id)

    async def _sync_under_lock(
        self,
        *,
        key: str,
        dimensions_override: dict[str, int] | None,
        cap_override: int | None,
        context_dir: Path,
        gateway: LinearGateway,
        semaphore: asyncio.Semaphore,
        started_at: str,
        mono_start: float,
    ) -> SyncResult:
        """
        Core sync-with-key logic executed while the writer lock is held.

        Separated from :meth:`sync` so the ``try/finally`` release-lock
        wrapper remains concise.  All parameters are pre-resolved by the
        caller; this method does not read instance state directly.

        Returns
        -------
        SyncResult
        """
        # -- Normalize key and attempt local resolution -----------------------
        url_slug, normalized_ref = _normalize_ticket_ref(key)
        manifest_path = context_dir / MANIFEST_FILENAME
        manifest: Manifest | None = None
        resolved_uuid: IssueId | None = None

        if manifest_path.is_file():
            manifest = load_manifest(context_dir)

            # URL workspace-slug validation (fail fast before any remote call).
            if url_slug is not None and url_slug != manifest.workspace_slug:
                raise WorkspaceMismatchError(
                    f"URL workspace slug {url_slug!r} does not match the "
                    f"context directory workspace {manifest.workspace_slug!r}"
                )

            # Alias-based local resolution avoids a redundant key→UUID
            # round-trip when the ticket is already tracked locally.
            resolved_uuid = _resolve_ref_to_uuid(normalized_ref, manifest)

        # -- Fetch the requested root ticket ----------------------------------
        fetch_ref = resolved_uuid if resolved_uuid is not None else normalized_ref
        root_bundle = await gateway.fetch_issue(fetch_ref)
        root_uuid = root_bundle.issue.issue_id

        # -- Initialize manifest if needed, or validate workspace -------------
        if manifest is None:
            manifest = initialize_manifest(
                root_bundle.workspace,
                self._dimensions,
                self._max_tickets_per_root,
            )
        elif manifest.workspace_id != root_bundle.workspace.workspace_id:
            raise WorkspaceMismatchError(
                f"Root ticket {root_bundle.issue.issue_key} belongs to "
                f"workspace {root_bundle.workspace.workspace_slug!r} "
                f"({root_bundle.workspace.workspace_id}), but the context "
                f"directory is bound to workspace "
                f"{manifest.workspace_slug!r} ({manifest.workspace_id})"
            )

        # -- Update manifest configuration (preserve when no override) -------
        effective_dims = (
            resolve_dimensions(dimensions_override)
            if dimensions_override is not None
            else dict(manifest.dimensions)
        )
        effective_cap = cap_override if cap_override is not None else manifest.max_tickets_per_root
        manifest.dimensions = dict(effective_dims)
        manifest.max_tickets_per_root = effective_cap

        # -- Record in-progress snapshot metadata -----------------------------
        manifest.snapshot = ManifestSnapshot(
            mode="sync",
            started_at=started_at,
            completed_successfully=False,
        )

        # -- Add the requested root to the manifest root set ------------------
        previous_entry = manifest.roots.get(root_uuid)
        manifest.roots[root_uuid] = ManifestRootEntry(state="active")
        if previous_entry is not None and previous_entry.state == "quarantined":
            logger.info(
                "sync: recovered quarantined root %s (%s) → active",
                root_bundle.issue.issue_key,
                root_uuid,
            )
        elif previous_entry is None:
            logger.info(
                "sync: added root %s (%s)",
                root_bundle.issue.issue_key,
                root_uuid,
            )

        # -- Pre-fetch all active root bundles --------------------------------
        # The requested root is already fetched.  Other active roots are
        # fetched now so that the Tier 3 ticket_ref provider can scan their
        # content at depth 0.  Per-ticket errors are caught so a single
        # unavailable existing root does not abort the entire run.
        fetched: dict[IssueId, TicketBundle] = {root_uuid: root_bundle}
        other_active_roots = [
            uid
            for uid, entry in manifest.roots.items()
            if uid != root_uuid and entry.state == "active"
        ]
        prefetch_failed: set[IssueId] = set()
        if other_active_roots:

            async def _fetch_existing_root(issue_id: IssueId) -> None:
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
        roots_for_traversal: dict[IssueId, IssueKey] = {}
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
            "sync: started — active_roots=%d, max_tickets_per_root=%d",
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

        return await self._sync_write_pass(
            graph=graph,
            fetched=fetched,
            manifest=manifest,
            context_dir=context_dir,
            gateway=gateway,
            semaphore=semaphore,
            started_at=started_at,
            mono_start=mono_start,
            log_label="sync",
        )

    async def _standalone_sync_under_lock(
        self,
        *,
        dimensions_override: dict[str, int] | None,
        cap_override: int | None,
        context_dir: Path,
        gateway: LinearGateway,
        semaphore: asyncio.Semaphore,
        started_at: str,
        mono_start: float,
    ) -> SyncResult:
        """
        Full unconditional rebuild of all tracked roots without changing
        root membership.

        Unlike :meth:`_refresh_under_lock` (incremental — fetches only stale
        tickets), this method re-fetches and re-writes every reachable ticket
        unconditionally.  This is the ``sync`` code path when no *key* is
        supplied.

        Returns
        -------
        SyncResult

        Raises
        ------
        ManifestError
            If no manifest exists (standalone sync requires tracked roots).
        """
        manifest = load_manifest(context_dir)

        # -- Update manifest configuration (preserve when no override) -------
        if dimensions_override is not None:
            manifest.dimensions = dict(resolve_dimensions(dimensions_override))
        if cap_override is not None:
            manifest.max_tickets_per_root = cap_override

        effective_dims = dict(manifest.dimensions)
        effective_cap = manifest.max_tickets_per_root

        # -- Record in-progress snapshot metadata -----------------------------
        manifest.snapshot = ManifestSnapshot(
            mode="sync",
            started_at=started_at,
            completed_successfully=False,
        )

        # -- Pre-fetch all active root bundles --------------------------------
        active_roots = [uid for uid, entry in manifest.roots.items() if entry.state == "active"]

        fetched: dict[IssueId, TicketBundle] = {}
        prefetch_failed: set[IssueId] = set()

        if active_roots:

            async def _fetch_root(issue_id: IssueId) -> None:
                async with semaphore:
                    try:
                        bundle = await gateway.fetch_issue(issue_id)
                        fetched[bundle.issue.issue_id] = bundle
                    except RootNotFoundError:
                        prefetch_failed.add(issue_id)
                        logger.warning(
                            "Root %s unavailable during standalone sync; excluding from traversal",
                            issue_id,
                        )

            async with asyncio.TaskGroup() as tg:
                for uid in active_roots:
                    tg.create_task(_fetch_root(uid))

        # -- Build traversal roots dict {uuid: current_key} -------------------
        roots_for_traversal: dict[IssueId, IssueKey] = {}
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
            "sync: started (standalone) — active_roots=%d, max_tickets_per_root=%d",
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

        return await self._sync_write_pass(
            graph=graph,
            fetched=fetched,
            manifest=manifest,
            context_dir=context_dir,
            gateway=gateway,
            semaphore=semaphore,
            started_at=started_at,
            mono_start=mono_start,
            log_label="sync (standalone)",
        )

    async def _sync_write_pass(
        self,
        *,
        graph: TraversalResult,
        fetched: dict[IssueId, TicketBundle],
        manifest: Manifest,
        context_dir: Path,
        gateway: LinearGateway,
        semaphore: asyncio.Semaphore,
        started_at: str,
        mono_start: float,
        log_label: str,
    ) -> SyncResult:
        """
        Shared post-traversal pipeline for sync write passes.

        Fetches any reachable tickets not yet in *fetched*, writes all
        reachable tickets (skipping byte-identical rewrites per ADR §8),
        prunes unreachable derived tickets, finalizes snapshot metadata,
        and persists the manifest.

        Used by both :meth:`_sync_under_lock` and
        :meth:`_standalone_sync_under_lock`.
        """
        # -- Fetch remaining reachable tickets --------------------------------
        created: list[IssueKey] = []
        updated: list[IssueKey] = []
        unchanged: list[IssueKey] = []
        errors: list[SyncError] = []

        missing_ids = [uid for uid in graph.tickets if uid not in fetched]
        if missing_ids:
            fetch_errors: list[tuple[IssueKey, IssueId]] = []

            async def _fetch_linked(issue_id: IssueId) -> None:
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
                        ticket_key=issue_key,
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
                        context_dir, existing_entry
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
        removed: list[IssueKey] = []
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
        # mode is hardcoded to "sync" because both callers
        # (_sync_under_lock, _standalone_sync_under_lock) are sync paths.
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
            "%s: completed — reachable=%d, created=%d, updated=%d, "
            "unchanged=%d, removed=%d, errors=%d, roots_at_cap=%d, "
            "duration=%.1fs",
            log_label,
            len(graph.tickets),
            len(created),
            len(updated),
            len(unchanged),
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
        Update the snapshot from all tracked roots.

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

        Side Effects
        ------------
        Acquires and releases the writer lock.  Rewrites ticket files that
        are stale or newly discovered.  Quarantines or removes roots that are
        no longer visible (depending on *missing_root_policy*).  Prunes
        derived tickets no longer reachable.  Updates the manifest.

        Mutability
        ----------
        Mutates the context directory on disk (manifest, ticket files, lock
        file).  Quarantined ticket files are rewritten in place with a
        warning preamble.  Does not mutate the ``ContextSync`` instance or
        any argument.

        Idempotency
        -----------
        Calling ``refresh()`` twice with no upstream changes produces the
        same on-disk state; the second call classifies all tickets as
        ``unchanged``.

        Thread Safety
        -------------
        Not thread-safe.  The writer lock prevents concurrent processes from
        mutating the same directory, but two coroutines sharing one
        ``ContextSync`` instance must not call mutating methods concurrently.

        Example
        -------
        .. code-block:: python

            from context_sync import ContextSync

            ctx = ContextSync(linear=client, context_dir="./context")
            result = await ctx.refresh()
            print(f"Updated {len(result.updated)} tickets")

        Behavioral Constraints
        ----------------------
        Requires an existing manifest; cannot be called on an empty context
        directory.  Does not add or remove roots — use ``sync`` to add and
        ``remove`` to delete.  A quarantined root is excluded from traversal
        but its file is preserved; it auto-recovers on the next refresh if
        it becomes visible again.
        """
        valid_policies = ("quarantine", "remove")
        if missing_root_policy not in valid_policies:
            raise ValueError(
                f"missing_root_policy must be one of {valid_policies!r}, "
                f"got {missing_root_policy!r}"
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
        except BaseException as exc:
            duration = time.monotonic() - mono_start
            logger.info("refresh: aborted — %s, duration=%.1fs", exc, duration)
            raise
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
        snapshot_mode: Literal["refresh", "remove"] = "refresh",
        manifest: Manifest | None = None,
    ) -> SyncResult:
        """
        Core refresh logic executed while the writer lock is held.

        Separated from :meth:`refresh` so the ``try/finally`` release-lock
        wrapper remains concise.  All parameters are pre-resolved by the
        caller; this method does not read instance state directly.

        Parameters
        ----------
        missing_root_policy:
            How to handle existing manifest roots that are no longer visible.
        context_dir:
            Root directory of the context-sync snapshot.
        gateway:
            Gateway instance for all Linear reads.
        semaphore:
            Concurrency limiter for ticket fetches.
        started_at:
            RFC 3339 UTC timestamp when the outer operation started.
        mono_start:
            Monotonic clock reading at operation start, for duration logging.
        snapshot_mode:
            Label for the ``ManifestSnapshot.mode`` field.  Defaults to
            ``"refresh"``; the ``remove`` caller passes its own mode so
            the manifest records the triggering operation.
        manifest:
            Pre-loaded manifest to use instead of reading from disk.  When
            ``remove`` has already mutated the manifest in memory, it passes
            the manifest here so the root-set change and the snapshot
            finalization are committed together — avoiding a partial-commit
            window where the manifest is saved but the refresh has not yet
            completed.

        Returns
        -------
        SyncResult
        """
        # -- Load existing manifest (must exist for refresh) -------------------
        if manifest is None:
            manifest = load_manifest(context_dir)

        # Refresh uses the manifest's persisted traversal configuration, not
        # the current ContextSync instance defaults.  The manifest is
        # authoritative for the snapshot's active dimensions and per-root cap.
        effective_dims = dict(manifest.dimensions)
        effective_cap = manifest.max_tickets_per_root

        # -- Record in-progress snapshot metadata -----------------------------
        manifest.snapshot = ManifestSnapshot(
            mode=snapshot_mode,
            started_at=started_at,
            completed_successfully=False,
        )

        errors: list[SyncError] = []
        removed_by_policy: list[IssueKey] = []

        # -- Batch-check root visibility --------------------------------------
        root_uuids = list(manifest.roots.keys())
        if not root_uuids:
            # No roots in manifest — prune all remaining tracked tickets and
            # finalize.  This handles the case where remove_root deleted the
            # last root.
            removed: list[IssueKey] = []
            for uid in list(manifest.tickets.keys()):
                entry = manifest.tickets[uid]
                file_path = context_dir / entry.current_path
                if file_path.is_file():
                    file_path.unlink()
                    logger.debug("Pruned ticket (no roots remain): %s", entry.current_key)
                removed.append(entry.current_key)
                del manifest.tickets[uid]

            completed_at = _utc_now()
            manifest.snapshot = ManifestSnapshot(
                mode=snapshot_mode,
                started_at=started_at,
                completed_at=completed_at,
                completed_successfully=True,
            )
            save_manifest(manifest, context_dir)

            duration = time.monotonic() - mono_start
            logger.info(
                "%s: no roots remain — pruned=%d, duration=%.1fs",
                snapshot_mode,
                len(removed),
                duration,
            )
            return SyncResult(removed=removed)

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
                            # IssueKey(uid) fallback: when neither metadata nor a
                            # manifest entry is available, the UUID is used as the
                            # display key — a deliberate type-boundary crossing so
                            # error consumers always receive a printable identifier.
                            ticket_key=(
                                meta.issue_key
                                if meta is not None
                                else manifest.tickets[uid].current_key
                                if uid in manifest.tickets
                                else IssueKey(uid)
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
                    # IssueKey(uid) fallback: see comment on quarantine path
                    # above — UUID used as display key when no human-readable
                    # key is available.
                    removed_key: IssueKey = (
                        ticket_entry.current_key
                        if ticket_entry is not None
                        else meta.issue_key
                        if meta is not None
                        else IssueKey(uid)
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

        fetched: dict[IssueId, TicketBundle] = {}
        prefetch_failed: set[IssueId] = set()

        if active_root_uuids:

            async def _fetch_root(issue_id: IssueId) -> None:
                async with semaphore:
                    try:
                        bundle = await gateway.fetch_issue(issue_id)
                        fetched[bundle.issue.issue_id] = bundle
                    except RootNotFoundError:
                        prefetch_failed.add(issue_id)

            async with asyncio.TaskGroup() as tg:
                for uid in active_root_uuids:
                    tg.create_task(_fetch_root(uid))

        # Treat a root-prefetch RootNotFoundError as a missing-root condition
        # and apply the requested missing_root_policy rather than silently
        # dropping the root from traversal while leaving it marked active.
        for uid in prefetch_failed:
            ticket_entry = manifest.tickets.get(uid)
            # IssueKey(uid) fallback: UUID used as display key when the
            # manifest has no ticket entry for this root.
            failed_key: IssueKey = (
                ticket_entry.current_key if ticket_entry is not None else IssueKey(uid)
            )

            if missing_root_policy == "quarantine":
                manifest.roots[uid] = ManifestRootEntry(
                    state="quarantined",
                    quarantined_reason="not_available_in_visible_view",
                )
                if ticket_entry is not None:
                    _rewrite_quarantined_ticket(
                        uid=uid,
                        context_dir=context_dir,
                        manifest=manifest,
                        last_synced_at=started_at,
                    )
                errors.append(
                    SyncError(
                        ticket_key=failed_key,
                        error_type="root_quarantined",
                        message=(
                            "Root ticket passed visibility check but was "
                            "unavailable during pre-fetch"
                        ),
                        retriable=True,
                    )
                )
                logger.warning(
                    "refresh: root %s passed visibility but failed pre-fetch; quarantined",
                    uid,
                )
            else:
                # missing_root_policy == "remove"
                if ticket_entry is not None:
                    file_path = context_dir / ticket_entry.current_path
                    if file_path.is_file():
                        file_path.unlink()
                    del manifest.tickets[uid]
                del manifest.roots[uid]
                removed_by_policy.append(failed_key)
                logger.warning(
                    "refresh: root %s passed visibility but failed pre-fetch; removed",
                    uid,
                )

        # -- Build traversal roots dict {uuid: current_key} -------------------
        # Re-derive active roots after prefetch-failure handling since some
        # roots may have been quarantined or removed above.
        roots_for_traversal: dict[IssueId, IssueKey] = {}
        for uid in active_root_uuids:
            if uid in prefetch_failed:
                continue
            if uid in fetched:
                roots_for_traversal[uid] = fetched[uid].issue.issue_key
            elif uid in manifest.tickets:
                roots_for_traversal[uid] = manifest.tickets[uid].current_key

        logger.info(
            "%s: started — active_roots=%d, quarantined=%d, max_tickets_per_root=%d",
            snapshot_mode,
            len(roots_for_traversal),
            sum(1 for e in manifest.roots.values() if e.state == "quarantined"),
            effective_cap,
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
        stale_uuids: set[IssueId] = set()
        newly_discovered: set[IssueId] = set()

        # Identify newly discovered tickets (in graph but not in manifest).
        for uid in reachable_uuids:
            if uid not in manifest.tickets:
                newly_discovered.add(uid)

        # For tickets already in the manifest, batch-query remote cursors.
        tracked_reachable = [uid for uid in reachable_uuids if uid in manifest.tickets]

        if tracked_reachable:
            remote_issue_meta, remote_comment_meta, remote_relation_meta = await asyncio.gather(
                gateway.get_refresh_issue_metadata(tracked_reachable),
                gateway.get_refresh_comment_metadata(tracked_reachable),
                gateway.get_refresh_relation_metadata(tracked_reachable),
            )

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
                ticket_key = manifest.tickets[uid].current_key
                if local_fv is None or local_fv < FORMAT_VERSION:
                    stale_uuids.add(uid)
                    logger.debug("refresh: stale (format_version) — %s", ticket_key)
                elif local_cursor is None:
                    stale_uuids.add(uid)
                    logger.debug("refresh: stale (missing cursor) — %s", ticket_key)
                elif local_cursor != remote_cursor:
                    stale_uuids.add(uid)
                    logger.debug("refresh: stale (cursor mismatch) — %s", ticket_key)
                else:
                    logger.debug("refresh: fresh — %s", ticket_key)

        # -- Fetch stale and newly discovered tickets -------------------------
        created: list[IssueKey] = []
        updated: list[IssueKey] = []
        unchanged: list[IssueKey] = []

        fetch_targets = list(stale_uuids | newly_discovered)
        # Remove tickets already fetched during root pre-fetch.
        to_fetch = [uid for uid in fetch_targets if uid not in fetched]

        if to_fetch:
            fetch_errors: list[tuple[IssueKey, IssueId]] = []

            async def _fetch_linked(issue_id: IssueId) -> None:
                async with semaphore:
                    try:
                        bundle = await gateway.fetch_issue(issue_id)
                        fetched[bundle.issue.issue_id] = bundle
                    except RootNotFoundError:
                        ticket_info = graph.tickets.get(issue_id)
                        # IssueKey(issue_id) fallback: UUID used as display
                        # key when traversal has no record for this ticket.
                        issue_key: IssueKey = (
                            ticket_info.issue_key if ticket_info else IssueKey(issue_id)
                        )
                        fetch_errors.append((issue_key, issue_id))

            async with asyncio.TaskGroup() as tg:
                for uid in to_fetch:
                    tg.create_task(_fetch_linked(uid))

            for issue_key, _uid in fetch_errors:
                errors.append(
                    SyncError(
                        ticket_key=issue_key,
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
        removed: list[IssueKey] = list(removed_by_policy)
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
            mode=snapshot_mode,
            started_at=started_at,
            completed_at=completed_at,
            completed_successfully=True,
        )
        save_manifest(manifest, context_dir)

        duration = time.monotonic() - mono_start
        logger.info(
            "%s: completed — reachable=%d, created=%d, updated=%d, "
            "unchanged=%d, removed=%d, errors=%d, roots_at_cap=%d, "
            "duration=%.1fs",
            snapshot_mode,
            len(graph.tickets),
            len(created),
            len(updated),
            len(unchanged),
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

    async def remove(self, key: str) -> SyncResult:
        """
        Remove a root ticket and run a whole-snapshot refresh.

        Acquires the writer lock, loads the manifest, resolves *key* to a
        UUID through the alias table or ticket entries, verifies the UUID
        is in the root set, removes it, then delegates to the whole-snapshot
        refresh pipeline under the same writer lock.

        If the removed ticket is still reachable from another root, it
        remains in the snapshot as a derived ticket.  If it is no longer
        reachable, the refresh prunes it naturally.

        Parameters
        ----------
        key:
            Issue key (e.g. ``"ACP-123"``), Linear issue URL, or ticket
            UUID identifying the root to remove.

        Returns
        -------
        SyncResult
            Created, updated, unchanged, removed, and errored ticket sets.

        Raises
        ------
        ManifestError
            If the manifest does not exist or is invalid.
        RootNotInManifestError
            If *key* cannot be resolved to a current root.
        WorkspaceMismatchError
            If *key* is a URL whose workspace slug does not match.
        ActiveLockError
            If a non-stale writer lock is already held.
        StaleLockError
            If lock staleness cannot be determined safely.
        SystemicRemoteError
            If a systemic remote failure aborts the run.
        WriteError
            If a local file write or post-write verification fails.

        Side Effects
        ------------
        Acquires and releases the writer lock.  Removes the root entry from
        the manifest and triggers a whole-snapshot refresh that may prune
        ticket files no longer reachable from any remaining root.  Updates
        the manifest.

        Mutability
        ----------
        Mutates the context directory on disk (manifest, ticket files, lock
        file).  Does not mutate the ``ContextSync`` instance or any argument.

        Idempotency
        -----------
        Not idempotent.  Calling ``remove(key=K)`` a second time raises
        ``RootNotInManifestError`` because the root was already removed.

        Thread Safety
        -------------
        Not thread-safe.  The writer lock prevents concurrent processes from
        mutating the same directory, but two coroutines sharing one
        ``ContextSync`` instance must not call mutating methods concurrently.

        Example
        -------
        .. code-block:: python

            from context_sync import ContextSync

            ctx = ContextSync(linear=client, context_dir="./context")
            result = await ctx.remove(key="TEAM-42")
            print(result.removed)  # e.g. ['TEAM-42', 'TEAM-43']

        Behavioral Constraints
        ----------------------
        Requires an existing manifest.  Removing a root does not guarantee
        its ticket file is deleted — if the ticket is still reachable as a
        derived node from another root, it is kept.  The refresh that follows
        removal re-fetches metadata for all remaining tracked tickets.
        """
        context_dir = self._context_dir
        gateway = self._gateway
        semaphore = self._semaphore

        started_at = _utc_now()
        mono_start = time.monotonic()
        lock = acquire_lock(context_dir, "remove", acquired_at=started_at)

        try:
            return await self._remove_under_lock(
                key=key,
                context_dir=context_dir,
                gateway=gateway,
                semaphore=semaphore,
                started_at=started_at,
                mono_start=mono_start,
            )
        except BaseException as exc:
            duration = time.monotonic() - mono_start
            logger.info("remove: aborted — %s, duration=%.1fs", exc, duration)
            raise
        finally:
            release_lock(context_dir, lock.writer_id)

    async def _remove_under_lock(
        self,
        *,
        key: str,
        context_dir: Path,
        gateway: LinearGateway,
        semaphore: asyncio.Semaphore,
        started_at: str,
        mono_start: float,
    ) -> SyncResult:
        """
        Core remove logic executed while the writer lock is held.

        Resolves *key* to a UUID, removes it from the root set,
        persists the manifest, then delegates to :meth:`_refresh_under_lock`
        for the whole-snapshot refresh phase.

        Returns
        -------
        SyncResult
        """
        # -- Load manifest (must exist for remove-root) -------------------------
        manifest = load_manifest(context_dir)

        # -- Normalize key -------------------------------------------------------
        url_slug, normalized_ref = _normalize_ticket_ref(key)

        # URL workspace-slug validation.
        if url_slug is not None and url_slug != manifest.workspace_slug:
            raise WorkspaceMismatchError(
                f"URL workspace slug {url_slug!r} does not match the "
                f"context directory workspace {manifest.workspace_slug!r}"
            )

        # -- Resolve UUID through manifest --------------------------------------
        resolved_uuid = _resolve_ref_to_uuid(normalized_ref, manifest)
        if resolved_uuid is None:
            raise RootNotInManifestError(f"Cannot resolve {key!r} to a ticket in the manifest")

        # -- Verify UUID is in root set -----------------------------------------
        if resolved_uuid not in manifest.roots:
            raise RootNotInManifestError(
                f"Ticket {key!r} (UUID {resolved_uuid}) is tracked but is not in the root set"
            )

        # -- Remove UUID from root set ------------------------------------------
        del manifest.roots[resolved_uuid]
        logger.info("remove: removed root %s", resolved_uuid)

        # -- Execute whole-snapshot refresh under the same writer lock ----------
        # Pass the in-memory manifest so the root-set mutation and snapshot
        # finalization are committed together (no partial-commit window).
        return await self._refresh_under_lock(
            missing_root_policy="quarantine",
            context_dir=context_dir,
            gateway=gateway,
            semaphore=semaphore,
            started_at=started_at,
            mono_start=mono_start,
            snapshot_mode="remove",
            manifest=manifest,
        )

    async def diff(self) -> DiffResult:
        """
        Compare local snapshot to live Linear state without modifying files.

        Inspects the writer lock without acquiring or modifying it.  If a
        lock exists and is not demonstrably stale, raises
        :class:`DiffLockError` to avoid competing for rate-limited Linear
        API capacity while a mutating operation already owns the directory.

        Loads the manifest, reads frontmatter from all tracked ticket files,
        batch-fetches current metadata from Linear, and classifies each
        ticket as ``"current"``, ``"stale"``, ``"missing_locally"``, or
        ``"missing_remotely"``.

        Returns
        -------
        DiffResult
            Per-ticket drift classifications and any ticket-scoped errors.

        Raises
        ------
        DiffLockError
            If a non-stale writer lock is detected.
        ManifestError
            If the manifest does not exist or is invalid.
        ContextSyncError
            If no gateway is available.

        Side Effects
        ------------
        Read-only with respect to local disk state — does not acquire the
        writer lock, create files, or modify the manifest.  Does make
        network calls to the Linear API to fetch current metadata.

        Mutability
        ----------
        Does not mutate any on-disk state, the ``ContextSync`` instance, or
        any argument.

        Idempotency
        -----------
        Idempotent.  Calling ``diff()`` multiple times with the same local
        and remote state returns the same ``DiffResult``.

        Thread Safety
        -------------
        Safe to call concurrently with other ``diff()`` calls on the same
        instance.  Not safe to call concurrently with mutating methods
        (``sync``, ``refresh``, ``remove``) — the writer lock prevents
        concurrent process-level mutation, but ``diff`` deliberately avoids
        acquiring the lock and will raise ``DiffLockError`` if one exists.

        Example
        -------
        .. code-block:: python

            from context_sync import ContextSync

            ctx = ContextSync(linear=client, context_dir="./context")
            result = await ctx.diff()
            for entry in result.entries:
                print(f"{entry.ticket_key}: {entry.status}")

        Behavioral Constraints
        ----------------------
        Requires an existing manifest.  Refuses to run while a non-stale
        writer lock exists to avoid competing for rate-limited Linear API
        capacity with an active writer.  This is intentional — wait for the
        active writer to finish or verify the lock is stale before retrying.
        """
        return await run_diff(
            context_dir=self._context_dir,
            gateway=self._gateway,
        )
