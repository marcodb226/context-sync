"""
Exception hierarchy for context-sync.

The hierarchy mirrors the error-handling contract from the top-level design
(§4).  Each exception class maps to a specific failure scenario so callers can
distinguish between lock contention, remote failures, workspace mismatches,
and local write problems without inspecting message strings.
"""

from __future__ import annotations


class ContextSyncError(Exception):
    """Base exception for all context-sync errors."""


# ---------------------------------------------------------------------------
# Lock contention
# ---------------------------------------------------------------------------


class LockError(ContextSyncError):
    """Base for writer-lock contention or staleness errors."""


class ActiveLockError(LockError):
    """A non-stale writer lock is held by another process.

    The caller should not wait indefinitely; fail fast and let the operator
    decide when to retry.
    """


class StaleLockError(LockError):
    """Lock staleness cannot be determined safely.

    The tool can neither prove the recorded writer is gone nor confirm it is
    still running.  Failing explicitly avoids guessing.
    """


class DiffLockError(LockError):
    """``diff`` detected a lock that is not demonstrably stale.

    Running ``diff`` now would compete with the mutating run for rate-limited
    Linear API calls and could delay the write.  Retry after the lock clears.
    """


# ---------------------------------------------------------------------------
# Workspace and root validation
# ---------------------------------------------------------------------------


class WorkspaceMismatchError(ContextSyncError):
    """Ticket belongs to a different workspace than the context directory."""


class RootNotFoundError(ContextSyncError):
    """An explicitly requested root ticket is not available in the current
    visible view.

    This is terminal for ``sync`` and ``add`` — there is no meaningful partial
    result without the requested root.
    """


class RootNotInManifestError(ContextSyncError):
    """``remove_root`` target is not in the manifest root set."""


# ---------------------------------------------------------------------------
# Remote failures
# ---------------------------------------------------------------------------


class SystemicRemoteError(ContextSyncError):
    """Whole-system remote failure that is terminal for the current run.

    Covers lost authentication, lost network access, workspace access loss,
    and retry-exhausted upstream ``5xx`` failures reported by
    ``linear-client``.
    """


# ---------------------------------------------------------------------------
# Local I/O
# ---------------------------------------------------------------------------


class WriteError(ContextSyncError):
    """Local file-write failure.

    Terminal because it breaks the integrity of the local snapshot.
    """


class ManifestError(ContextSyncError):
    """Manifest is missing, corrupt, or format-incompatible."""
