"""Tests for the _lock module."""

from __future__ import annotations

import os
import platform
from pathlib import Path

import pytest
import yaml

from context_sync._errors import ActiveLockError, StaleLockError
from context_sync._lock import (
    LOCK_FILENAME,
    LockRecord,
    acquire_lock,
    inspect_lock,
    is_lock_stale,
    release_lock,
)

# ---------------------------------------------------------------------------
# TestLockRecord
# ---------------------------------------------------------------------------


class TestLockRecord:
    def test_constructs_with_all_fields(self) -> None:
        record = LockRecord(
            writer_id="abc-123",
            host="myhost",
            pid=42,
            acquired_at="2026-01-01T00:00:00Z",
            mode="sync",
        )
        assert record.writer_id == "abc-123"
        assert record.host == "myhost"
        assert record.pid == 42
        assert record.acquired_at == "2026-01-01T00:00:00Z"
        assert record.mode == "sync"

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValueError):
            LockRecord(
                writer_id="abc",
                host="h",
                pid=1,
                acquired_at="t",
                mode="sync",
                extra_field="nope",  # type: ignore[call-arg]
            )

    def test_pid_can_be_none(self) -> None:
        record = LockRecord(
            writer_id="abc",
            host="h",
            pid=None,
            acquired_at="t",
            mode="sync",
        )
        assert record.pid is None


# ---------------------------------------------------------------------------
# TestAcquireLock
# ---------------------------------------------------------------------------


class TestAcquireLock:
    def test_acquires_on_empty_directory(self, tmp_path: Path) -> None:
        record = acquire_lock(
            tmp_path,
            "sync",
            writer_id="w1",
            acquired_at="2026-01-01T00:00:00Z",
        )
        lock_path = tmp_path / LOCK_FILENAME
        assert lock_path.is_file()
        assert record.writer_id == "w1"
        assert record.mode == "sync"
        assert record.pid == os.getpid()

    def test_lock_file_contains_valid_yaml(self, tmp_path: Path) -> None:
        acquire_lock(
            tmp_path,
            "refresh",
            writer_id="w2",
            acquired_at="2026-03-01T12:00:00Z",
        )
        lock_path = tmp_path / LOCK_FILENAME
        raw = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
        assert isinstance(raw, dict)
        assert raw["writer_id"] == "w2"
        assert raw["mode"] == "refresh"
        assert raw["acquired_at"] == "2026-03-01T12:00:00Z"
        assert raw["host"] == platform.node()
        assert raw["pid"] == os.getpid()

    def test_second_acquire_raises_active_lock_error(self, tmp_path: Path) -> None:
        acquire_lock(tmp_path, "sync", writer_id="first")
        # The existing lock has pid=os.getpid(), which is alive, so this
        # should raise ActiveLockError.
        with pytest.raises(ActiveLockError):
            acquire_lock(tmp_path, "sync", writer_id="second")

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "sub" / "deep"
        record = acquire_lock(nested, "add", writer_id="w3")
        assert (nested / LOCK_FILENAME).is_file()
        assert record.writer_id == "w3"


# ---------------------------------------------------------------------------
# TestReleaseLock
# ---------------------------------------------------------------------------


class TestReleaseLock:
    def test_removes_lock_file(self, tmp_path: Path) -> None:
        acquire_lock(tmp_path, "sync", writer_id="w1")
        lock_path = tmp_path / LOCK_FILENAME
        assert lock_path.is_file()
        release_lock(tmp_path)
        assert not lock_path.exists()

    def test_idempotent_when_already_gone(self, tmp_path: Path) -> None:
        release_lock(tmp_path)  # no file at all — should not raise
        release_lock(tmp_path)  # still fine


# ---------------------------------------------------------------------------
# TestInspectLock
# ---------------------------------------------------------------------------


class TestInspectLock:
    def test_returns_none_when_no_lock(self, tmp_path: Path) -> None:
        assert inspect_lock(tmp_path) is None

    def test_returns_lock_record_when_present(self, tmp_path: Path) -> None:
        acquire_lock(tmp_path, "sync", writer_id="w1", acquired_at="t0")
        record = inspect_lock(tmp_path)
        assert record is not None
        assert record.writer_id == "w1"
        assert record.mode == "sync"

    def test_raises_stale_lock_error_for_corrupt_file(self, tmp_path: Path) -> None:
        lock_path = tmp_path / LOCK_FILENAME
        lock_path.write_text(":::not yaml:::", encoding="utf-8")
        with pytest.raises(StaleLockError):
            inspect_lock(tmp_path)

    def test_raises_stale_lock_error_for_non_mapping(self, tmp_path: Path) -> None:
        lock_path = tmp_path / LOCK_FILENAME
        lock_path.write_text("- just\n- a\n- list\n", encoding="utf-8")
        with pytest.raises(StaleLockError):
            inspect_lock(tmp_path)

    def test_raises_stale_lock_error_for_invalid_schema(self, tmp_path: Path) -> None:
        lock_path = tmp_path / LOCK_FILENAME
        lock_path.write_text("unrelated_key: value\n", encoding="utf-8")
        with pytest.raises(StaleLockError):
            inspect_lock(tmp_path)


# ---------------------------------------------------------------------------
# TestIsLockStale
# ---------------------------------------------------------------------------


class TestIsLockStale:
    def test_same_host_dead_pid_returns_true(self) -> None:
        lock = LockRecord(
            writer_id="w",
            host=platform.node(),
            pid=999_999_999,
            acquired_at="t",
            mode="sync",
        )
        assert is_lock_stale(lock) is True

    def test_same_host_live_pid_returns_false(self) -> None:
        lock = LockRecord(
            writer_id="w",
            host=platform.node(),
            pid=os.getpid(),
            acquired_at="t",
            mode="sync",
        )
        assert is_lock_stale(lock) is False

    def test_different_host_returns_none(self) -> None:
        lock = LockRecord(
            writer_id="w",
            host="some-other-host-that-is-not-this-one",
            pid=os.getpid(),
            acquired_at="t",
            mode="sync",
        )
        assert is_lock_stale(lock) is None

    def test_none_pid_returns_none(self) -> None:
        lock = LockRecord(
            writer_id="w",
            host=platform.node(),
            pid=None,
            acquired_at="t",
            mode="sync",
        )
        assert is_lock_stale(lock) is None


# ---------------------------------------------------------------------------
# TestPreemption
# ---------------------------------------------------------------------------


class TestPreemption:
    def test_stale_lock_is_preempted(self, tmp_path: Path) -> None:
        dead_pid = 999_999_999
        lock_path = tmp_path / LOCK_FILENAME
        stale_content = yaml.safe_dump(
            {
                "writer_id": "old-writer",
                "host": platform.node(),
                "pid": dead_pid,
                "acquired_at": "2020-01-01T00:00:00Z",
                "mode": "sync",
            }
        )
        lock_path.write_text(stale_content, encoding="utf-8")

        record = acquire_lock(tmp_path, "refresh", writer_id="new-writer")
        assert record.writer_id == "new-writer"
        assert record.mode == "refresh"

        # Verify the file on disk belongs to the new writer.
        inspected = inspect_lock(tmp_path)
        assert inspected is not None
        assert inspected.writer_id == "new-writer"

    def test_indeterminate_lock_raises_stale_lock_error(self, tmp_path: Path) -> None:
        lock_path = tmp_path / LOCK_FILENAME
        remote_content = yaml.safe_dump(
            {
                "writer_id": "remote-writer",
                "host": "some-other-host-that-is-not-this-one",
                "pid": 12345,
                "acquired_at": "2020-01-01T00:00:00Z",
                "mode": "sync",
            }
        )
        lock_path.write_text(remote_content, encoding="utf-8")

        with pytest.raises(StaleLockError):
            acquire_lock(tmp_path, "sync", writer_id="local-writer")

    def test_active_lock_raises_active_lock_error(self, tmp_path: Path) -> None:
        lock_path = tmp_path / LOCK_FILENAME
        active_content = yaml.safe_dump(
            {
                "writer_id": "active-writer",
                "host": platform.node(),
                "pid": os.getpid(),
                "acquired_at": "2026-01-01T00:00:00Z",
                "mode": "sync",
            }
        )
        lock_path.write_text(active_content, encoding="utf-8")

        with pytest.raises(ActiveLockError):
            acquire_lock(tmp_path, "sync", writer_id="contender")
