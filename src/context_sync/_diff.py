"""
Diff-specific helpers for the non-mutating drift inspection flow (M3-3).

This module contains the lock-inspection, changed-field-detection, and
diff-execution helpers used by :meth:`ContextSync.diff`.  The core diff
pipeline was extracted from ``_sync.py`` to keep that module within the
1 000 code-line guideline.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from context_sync._config import FORMAT_VERSION
from context_sync._errors import DiffLockError, ManifestError, StaleLockError
from context_sync._lock import inspect_lock, is_lock_stale
from context_sync._manifest import load_manifest
from context_sync._models import DiffEntry, DiffResult, SyncError
from context_sync._signatures import compute_comments_signature, compute_relations_signature
from context_sync._yaml import parse_frontmatter

if TYPE_CHECKING:
    from context_sync._gateway import (
        LinearGateway,
        RefreshCommentMeta,
        RefreshIssueMeta,
        RefreshThreadMeta,
        RelationData,
    )

logger = logging.getLogger(__name__)


def check_diff_lock(context_dir: Path) -> None:
    """
    Inspect the writer lock for ``diff`` without acquiring or modifying it.

    ``diff`` must never acquire, clear, or preempt the writer lock.  If a
    lock exists and is demonstrably stale, diff logs a warning and proceeds.
    If the lock is active or staleness is indeterminate, raises
    :class:`DiffLockError` with an explanation of why running diff now would
    be counterproductive (rate-limit contention with the active writer).

    Parameters
    ----------
    context_dir:
        Root directory of the context-sync snapshot.

    Raises
    ------
    DiffLockError
        If a non-stale lock is detected or the lock file cannot be parsed.
    """
    try:
        lock = inspect_lock(context_dir)
    except StaleLockError:
        raise DiffLockError(
            "A lock file exists but could not be read or parsed. Cannot "
            "determine whether a mutating operation is in progress. Wait "
            "for the lock to clear and retry."
        ) from None

    if lock is None:
        return

    stale = is_lock_stale(lock)
    if stale is True:
        logger.info(
            "Stale writer lock detected during diff — not clearing or "
            "preempting (writer_id=%s, host=%s, pid=%s, mode=%s)",
            lock.writer_id,
            lock.host,
            lock.pid,
            lock.mode,
        )
        return

    raise DiffLockError(
        f"A mutating operation ({lock.mode!r}) currently holds the writer "
        f"lock on this context directory (writer_id={lock.writer_id}, "
        f"host={lock.host}, pid={lock.pid}). Running diff now would compete "
        f"for rate-limited Linear API capacity and could delay the active "
        f"write. Wait for the lock to clear and retry."
    )


def compute_changed_fields(
    *,
    fm: dict[str, Any],
    remote_issue: RefreshIssueMeta,
    remote_comment_meta: tuple[list[RefreshCommentMeta], list[RefreshThreadMeta]],
    remote_relation_meta: list[RelationData],
) -> list[str]:
    """
    Compare local frontmatter against remote metadata to identify drift.

    Returns a sorted list of cursor-component names that differ between the
    local snapshot and the current remote state.  An empty list means the
    ticket is current.

    Parameters
    ----------
    fm:
        Parsed YAML frontmatter from the local ticket file.
    remote_issue:
        Issue-level metadata from the gateway.
    remote_comment_meta:
        ``(comments, threads)`` pair for ``comments_signature`` computation.
    remote_relation_meta:
        Relation metadata for ``relations_signature`` computation.

    Returns
    -------
    list[str]
        Sorted names of changed cursor components and/or ``"issue_key"``.
    """
    local_cursor = fm.get("refresh_cursor")
    if not isinstance(local_cursor, dict):
        local_cursor = {}

    changed: list[str] = []

    # issue_updated_at
    if local_cursor.get("issue_updated_at") != remote_issue.updated_at:
        changed.append("issue_updated_at")

    # comments_signature
    remote_comments, remote_threads = remote_comment_meta
    remote_comments_sig = compute_comments_signature(remote_comments, remote_threads)
    if local_cursor.get("comments_signature") != remote_comments_sig:
        changed.append("comments_signature")

    # relations_signature
    remote_relations_sig = compute_relations_signature(remote_relation_meta)
    if local_cursor.get("relations_signature") != remote_relations_sig:
        changed.append("relations_signature")

    # issue_key rename
    local_key = fm.get("ticket_key")
    if local_key and remote_issue.issue_key != local_key:
        changed.append("issue_key")

    return sorted(changed)


async def run_diff(
    *,
    context_dir: Path,
    gateway: LinearGateway,
) -> DiffResult:
    """
    Execute the non-mutating diff pipeline.

    Inspects the writer lock (never acquires or modifies it), loads the
    manifest, reads frontmatter from all tracked ticket files, batch-fetches
    current metadata from Linear, and classifies each ticket as
    ``"current"``, ``"stale"``, ``"missing_locally"``, or
    ``"missing_remotely"``.

    Parameters
    ----------
    context_dir:
        Root directory of the context-sync snapshot.
    gateway:
        Gateway instance for all Linear reads.

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
    """
    mono_start = time.monotonic()

    # --- Lock inspection (never acquire, clear, or preempt) ----------------
    check_diff_lock(context_dir)

    # --- Load manifest -----------------------------------------------------
    manifest = load_manifest(context_dir)

    tracked_uids = list(manifest.tickets.keys())
    if not tracked_uids:
        logger.info("diff: no tracked tickets — nothing to compare")
        return DiffResult()

    logger.info("diff: started — tracked_tickets=%d", len(tracked_uids))

    # --- Read local state --------------------------------------------------
    #
    # For each tracked ticket, read its frontmatter.  ``None`` means the
    # file does not exist on disk (missing_locally); an empty dict means
    # the file exists but its frontmatter is corrupt (treated as stale).
    local_frontmatter: dict[str, dict[str, Any] | None] = {}
    read_errors: list[SyncError] = []
    for uid in tracked_uids:
        entry = manifest.tickets[uid]
        file_path = context_dir / entry.current_path
        if not file_path.is_file():
            local_frontmatter[uid] = None
        else:
            try:
                text = file_path.read_text(encoding="utf-8")
                local_frontmatter[uid] = parse_frontmatter(text)
            except OSError as exc:
                logger.warning(
                    "Cannot read ticket file %s: %s",
                    file_path,
                    exc,
                )
                read_errors.append(
                    SyncError(
                        ticket_id=entry.current_key,
                        error_type="read_error",
                        message=f"Cannot read ticket file: {exc}",
                        retriable=True,
                    )
                )
                local_frontmatter[uid] = None
            except (ValueError, KeyError, ManifestError) as exc:
                logger.warning(
                    "Corrupt frontmatter for %s: %s",
                    file_path,
                    exc,
                )
                read_errors.append(
                    SyncError(
                        ticket_id=entry.current_key,
                        error_type="corrupt_frontmatter",
                        message=f"Cannot parse ticket frontmatter: {exc}",
                        retriable=False,
                    )
                )
                local_frontmatter[uid] = None

    # --- Fetch remote state (batch metadata) -------------------------------
    issue_meta, comment_meta, relation_meta = await asyncio.gather(
        gateway.get_refresh_issue_metadata(tracked_uids),
        gateway.get_refresh_comment_metadata(tracked_uids),
        gateway.get_refresh_relation_metadata(tracked_uids),
    )

    # --- Compare and classify ----------------------------------------------
    entries: list[DiffEntry] = []
    errors: list[SyncError] = list(read_errors)

    # UUIDs that had read errors are already in errors; skip them below.
    errored_uids = {e.ticket_id for e in read_errors}

    for uid in tracked_uids:
        manifest_entry = manifest.tickets[uid]

        # Skip tickets that had read errors — already reported.
        if manifest_entry.current_key in errored_uids:
            continue

        fm = local_frontmatter[uid]

        # missing_locally: tracked in manifest but no file on disk.
        if fm is None:
            entries.append(
                DiffEntry(
                    ticket_id=manifest_entry.current_key,
                    status="missing_locally",
                )
            )
            continue

        # Identity validation: ticket_uuid must match the manifest UUID.
        local_uuid = fm.get("ticket_uuid")
        if local_uuid != uid:
            errors.append(
                SyncError(
                    ticket_id=manifest_entry.current_key,
                    error_type="identity_mismatch",
                    message=(
                        f"Local ticket_uuid {local_uuid!r} does not match manifest UUID {uid!r}"
                    ),
                    retriable=False,
                )
            )
            continue

        # missing_remotely: not available in the current visible view.
        remote_issue = issue_meta.get(uid)
        if remote_issue is None or not remote_issue.visible:
            entries.append(
                DiffEntry(
                    ticket_id=manifest_entry.current_key,
                    status="missing_remotely",
                )
            )
            continue

        # format_version gate: a file whose format is too old for the
        # accepted cursor contract is stale regardless of cursor match.
        local_fv = fm.get("format_version")
        format_stale = not isinstance(local_fv, int) or local_fv < FORMAT_VERSION

        # Compare local cursor vs remote metadata.
        changed = compute_changed_fields(
            fm=fm,
            remote_issue=remote_issue,
            remote_comment_meta=comment_meta.get(uid, ([], [])),
            remote_relation_meta=relation_meta.get(uid, []),
        )

        stale = bool(changed) or format_stale

        entries.append(
            DiffEntry(
                ticket_id=remote_issue.issue_key,
                status="stale" if stale else "current",
                changed_fields=changed,
            )
        )

    duration = time.monotonic() - mono_start
    current_count = sum(1 for e in entries if e.status == "current")
    stale_count = sum(1 for e in entries if e.status == "stale")
    missing_local = sum(1 for e in entries if e.status == "missing_locally")
    missing_remote = sum(1 for e in entries if e.status == "missing_remotely")
    logger.info(
        "diff: completed — current=%d, stale=%d, missing_locally=%d, "
        "missing_remotely=%d, errors=%d, duration=%.1fs",
        current_count,
        stale_count,
        missing_local,
        missing_remote,
        len(errors),
        duration,
    )

    return DiffResult(entries=entries, errors=errors)
