"""Tests for public result and error model contracts."""

from __future__ import annotations

import pytest

from context_sync._models import DiffEntry, DiffResult, SyncError, SyncResult


class TestSyncError:
    """SyncError contract checks."""

    def test_construction(self) -> None:
        err = SyncError(
            ticket_key="ACP-1",
            error_type="not_found",
            message="Not available",
            retriable=False,
        )
        assert err.ticket_key == "ACP-1"
        assert err.error_type == "not_found"
        assert err.message == "Not available"
        assert err.retriable is False

    def test_frozen(self) -> None:
        err = SyncError("X-1", "api_error", "fail", True)
        with pytest.raises(AttributeError):
            err.ticket_key = "X-2"  # type: ignore[misc]

    def test_retriable_flag(self) -> None:
        retriable = SyncError("X-1", "api_error", "transient", True)
        non_retriable = SyncError("X-2", "not_found", "gone", False)
        assert retriable.retriable is True
        assert non_retriable.retriable is False


class TestSyncResult:
    """SyncResult contract checks."""

    def test_default_empty(self) -> None:
        result = SyncResult()
        assert result.created == []
        assert result.updated == []
        assert result.unchanged == []
        assert result.removed == []
        assert result.errors == []

    def test_populated(self) -> None:
        err = SyncError("X-3", "api_error", "oops", True)
        result = SyncResult(
            created=["A-1"],
            updated=["A-2"],
            unchanged=["A-3"],
            removed=["A-4"],
            errors=[err],
        )
        assert result.created == ["A-1"]
        assert result.updated == ["A-2"]
        assert result.unchanged == ["A-3"]
        assert result.removed == ["A-4"]
        assert len(result.errors) == 1
        assert result.errors[0].ticket_key == "X-3"

    def test_frozen(self) -> None:
        result = SyncResult()
        with pytest.raises(AttributeError):
            result.created = ["NEW"]  # type: ignore[misc]

    def test_default_factory_isolation(self) -> None:
        """Each instance gets its own list objects."""
        a = SyncResult()
        b = SyncResult()
        assert a.created is not b.created


class TestDiffEntry:
    """DiffEntry contract checks."""

    def test_construction(self) -> None:
        entry = DiffEntry(
            ticket_key="ACP-5",
            status="stale",
            changed_fields=["status", "comments"],
        )
        assert entry.ticket_key == "ACP-5"
        assert entry.status == "stale"
        assert entry.changed_fields == ["status", "comments"]

    def test_current_has_no_changed_fields(self) -> None:
        entry = DiffEntry(ticket_key="ACP-6", status="current")
        assert entry.changed_fields == []

    def test_frozen(self) -> None:
        entry = DiffEntry(ticket_key="X-1", status="current")
        with pytest.raises(AttributeError):
            entry.status = "stale"  # type: ignore[misc]


class TestDiffResult:
    """DiffResult contract checks."""

    def test_default_empty(self) -> None:
        result = DiffResult()
        assert result.entries == []
        assert result.errors == []

    def test_populated(self) -> None:
        entry = DiffEntry("X-1", "stale", ["title"])
        err = SyncError("X-2", "api_error", "oops", True)
        result = DiffResult(entries=[entry], errors=[err])
        assert len(result.entries) == 1
        assert len(result.errors) == 1
