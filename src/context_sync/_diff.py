"""
Diff-specific helpers for the non-mutating drift inspection flow (M3-3).

This module contains the lock-inspection and changed-field-detection helpers
used by :meth:`ContextSync.diff`.  Extracted from ``_sync.py`` to keep that
module within the 1 000 code-line guideline.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from context_sync._errors import DiffLockError, StaleLockError
from context_sync._lock import inspect_lock, is_lock_stale
from context_sync._signatures import compute_comments_signature, compute_relations_signature

if TYPE_CHECKING:
    from context_sync._gateway import (
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
