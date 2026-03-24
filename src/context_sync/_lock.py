"""
Writer-lock lifecycle for the context directory.

The ``.context-sync.lock`` file enforces single-writer semantics for
mutating operations (``sync``, ``refresh``, ``remove``, and the
internal ``_add`` path).
The lock is acquired with an atomic create-or-fail step
(``O_CREAT | O_EXCL``) and carries enough metadata for safe contention
handling and operator diagnosis.

``diff`` never acquires, clears, or preempts the lock.  It may inspect
lock metadata through :func:`inspect_lock` and :func:`is_lock_stale`.
"""

from __future__ import annotations

import logging
import os
import platform
import uuid
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from context_sync._errors import ActiveLockError, StaleLockError
from context_sync._yaml import dump_yaml

logger = logging.getLogger(__name__)

LOCK_FILENAME: str = ".context-sync.lock"

LOCK_MODES = Literal["sync", "refresh", "add", "remove"]
"""Allowed mutating operation modes for the writer lock."""


# ---------------------------------------------------------------------------
# Lock record model
# ---------------------------------------------------------------------------


class LockRecord(BaseModel):
    """
    The ``.context-sync.lock`` schema.

    Attributes
    ----------
    writer_id:
        Unique identifier for the owning invocation.
    host:
        Machine or worker host identity.
    pid:
        Process ID of the owning process, or ``None`` if unavailable.
    acquired_at:
        UTC RFC 3339 timestamp when the lock was taken.
    mode:
        The mutating operation (``"sync"``, ``"refresh"``, ``"remove"``,
        or ``"add"`` for the internal ``_add`` path).
    """

    model_config = ConfigDict(extra="forbid")

    writer_id: str
    host: str
    pid: int | None = None
    acquired_at: str
    mode: LOCK_MODES


# ---------------------------------------------------------------------------
# Staleness detection
# ---------------------------------------------------------------------------


def is_lock_stale(lock: LockRecord) -> bool | None:
    """
    Determine whether *lock* is demonstrably stale.

    Returns
    -------
    bool | None
        ``True`` if the lock names the current host and a PID that no
        longer exists (demonstrably stale — safe to preempt).
        ``False`` if the lock names the current host and a PID that is
        still alive (active writer — must not preempt).
        ``None`` if staleness cannot be determined safely (different
        host, or ``pid`` is ``None``).
    """
    current_host = platform.node()
    if lock.host != current_host:
        return None
    if lock.pid is None:
        return None
    return not _check_pid_alive(lock.pid)


def _check_pid_alive(pid: int) -> bool:
    """
    Check whether a process with *pid* is still running.

    Uses ``os.kill(pid, 0)`` on POSIX systems.  Signal 0 does not
    actually send a signal but checks process existence.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we lack permission to signal it.
        return True
    return True


# ---------------------------------------------------------------------------
# Lock lifecycle
# ---------------------------------------------------------------------------


def acquire_lock(
    context_dir: Path,
    mode: LOCK_MODES,
    *,
    writer_id: str | None = None,
    acquired_at: str | None = None,
) -> LockRecord:
    """
    Atomically acquire the writer lock for *context_dir*.

    If a lock file already exists, inspects it for staleness.
    Demonstrably stale locks are preempted (deleted and re-acquired);
    active or indeterminate locks cause a fast failure.

    Parameters
    ----------
    context_dir:
        The context directory.
    mode:
        The mutating operation name.
    writer_id:
        Optional writer UUID.  Generated if not provided.
    acquired_at:
        Optional RFC 3339 timestamp.  Uses a placeholder if not
        provided (the caller is expected to supply the real timestamp
        from the sync pass).

    Returns
    -------
    LockRecord
        The newly acquired lock.

    Raises
    ------
    ActiveLockError
        A non-stale lock is held by an active process.
    StaleLockError
        Lock staleness cannot be determined safely.
    """
    lock_path = context_dir / LOCK_FILENAME
    record = LockRecord(
        writer_id=writer_id or str(uuid.uuid4()),
        host=platform.node(),
        pid=os.getpid(),
        acquired_at=acquired_at or "1970-01-01T00:00:00Z",
        mode=mode,
    )

    context_dir.mkdir(parents=True, exist_ok=True)

    try:
        _atomic_create_lock(lock_path, record)
        logger.debug(
            "Lock acquired cleanly: writer_id=%s, mode=%s",
            record.writer_id,
            record.mode,
        )
        return record
    except FileExistsError:
        pass

    # Lock file already exists — inspect it.
    existing = inspect_lock(context_dir)
    if existing is None:
        # File disappeared between the open and inspect — retry once.
        try:
            _atomic_create_lock(lock_path, record)
            return record
        except FileExistsError as exc:
            existing = inspect_lock(context_dir)
            if existing is None:
                raise StaleLockError(
                    "Lock file appeared and disappeared during acquisition"
                ) from exc

    stale = is_lock_stale(existing)
    if stale is True:
        logger.warning(
            "Preempting stale lock: writer_id=%s, host=%s, pid=%s, mode=%s",
            existing.writer_id,
            existing.host,
            existing.pid,
            existing.mode,
        )
        # Re-read before unlinking to narrow the TOCTOU window (M1-2-R10).
        current = inspect_lock(context_dir)
        if current is not None and current.writer_id != existing.writer_id:
            # Another process preempted first — re-evaluate the new lock.
            new_stale = is_lock_stale(current)
            if new_stale is True:
                pass  # Still stale under the new writer, proceed to unlink.
            elif new_stale is False:
                raise ActiveLockError(
                    f"Lock held by active process: writer_id={current.writer_id}, "
                    f"host={current.host}, pid={current.pid}, mode={current.mode}"
                )
            else:
                raise StaleLockError(
                    f"Cannot determine lock staleness: writer_id={current.writer_id}, "
                    f"host={current.host}, pid={current.pid}, mode={current.mode}"
                )
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
        try:
            _atomic_create_lock(lock_path, record)
            return record
        except FileExistsError as exc:
            raise ActiveLockError("Another process acquired the lock during preemption") from exc
    elif stale is False:
        raise ActiveLockError(
            f"Lock held by active process: writer_id={existing.writer_id}, "
            f"host={existing.host}, pid={existing.pid}, mode={existing.mode}"
        )
    else:
        raise StaleLockError(
            f"Cannot determine lock staleness: writer_id={existing.writer_id}, "
            f"host={existing.host}, pid={existing.pid}, mode={existing.mode}"
        )


def release_lock(context_dir: Path, writer_id: str) -> None:
    """
    Remove the lock file after verifying ownership.

    Parameters
    ----------
    context_dir:
        The context directory.
    writer_id:
        The writer identity that must match the on-disk lock record.

    Raises
    ------
    ActiveLockError
        If the on-disk lock belongs to a different writer.
    """
    lock_path = context_dir / LOCK_FILENAME
    current = inspect_lock(context_dir)
    if current is None:
        return  # Already gone.
    if current.writer_id != writer_id:
        raise ActiveLockError(
            f"Cannot release lock owned by writer_id={current.writer_id} "
            f"(caller writer_id={writer_id})"
        )
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def inspect_lock(context_dir: Path) -> LockRecord | None:
    """
    Read and parse the lock file without modifying it.

    Returns ``None`` if no lock file exists.  Raises
    :class:`StaleLockError` if the file exists but cannot be read or
    parsed.
    """
    lock_path = context_dir / LOCK_FILENAME
    if not lock_path.is_file():
        return None

    try:
        raw_text = lock_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StaleLockError(f"Lock file is unreadable: {lock_path}") from exc

    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise StaleLockError(f"Lock file is corrupt: {lock_path}") from exc

    if not isinstance(raw, dict):
        raise StaleLockError(f"Lock file is not a YAML mapping: {lock_path}")

    try:
        return LockRecord.model_validate(raw)
    except ValidationError as exc:
        raise StaleLockError(f"Lock file has invalid schema: {lock_path}") from exc


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _atomic_create_lock(path: Path, record: LockRecord) -> None:
    """
    Create the lock file atomically using ``O_CREAT | O_EXCL``.

    Raises ``FileExistsError`` if the file already exists.  Cleans up
    the partially written file on write/sync failure.
    """
    content = dump_yaml(record.model_dump(mode="json"))
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, content.encode("utf-8"))
        os.fsync(fd)
    except OSError:
        os.close(fd)
        try:
            os.unlink(str(path))
        except OSError:
            pass
        raise
    else:
        os.close(fd)
