"""
Tests for the ContextSync.diff flow (M3-3).

Exercises the non-mutating drift inspection path: lock-aware refusal,
stale-lock observation without mutation, per-ticket classification
(current, stale, missing_locally, missing_remotely), changed-field
reporting, and issue-key rename detection.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path

import pytest

from context_sync._errors import DiffLockError, ManifestError
from context_sync._lock import LOCK_FILENAME, LockRecord
from context_sync._models import DiffEntry
from context_sync._testing import (
    FakeLinearGateway,
    make_context_sync,
    make_issue,
)
from context_sync._yaml import dump_yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_lock_file(context_dir: Path, lock: LockRecord) -> Path:
    """Write a lock file with the given record and return its path."""
    lock_path = context_dir / LOCK_FILENAME
    content = dump_yaml(lock.model_dump(mode="json"))
    lock_path.write_text(content, encoding="utf-8")
    return lock_path


def _find_entry(entries: list[DiffEntry], ticket_id: str) -> DiffEntry:
    """Find a DiffEntry by ticket_key, or fail the test."""
    for e in entries:
        if e.ticket_key == ticket_id:
            return e
    raise AssertionError(f"No DiffEntry with ticket_key={ticket_id!r}")


# ---------------------------------------------------------------------------
# Lock refusal: active lock → DiffLockError
# ---------------------------------------------------------------------------


class TestDiffLockRefusal:
    """diff refuses to run when a non-stale writer lock is detected."""

    async def test_active_lock_raises_diff_lock_error(self, context_dir: Path) -> None:
        """An active (same-host, live-PID) lock causes DiffLockError."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        # Plant an active lock (current PID is alive).
        _write_lock_file(
            context_dir,
            LockRecord(
                writer_id="other-writer",
                host=platform.node(),
                pid=os.getpid(),
                acquired_at="2026-01-01T00:00:00Z",
                mode="refresh",
            ),
        )

        with pytest.raises(DiffLockError, match="mutating operation"):
            await ctx.diff()

    async def test_indeterminate_lock_raises_diff_lock_error(self, context_dir: Path) -> None:
        """A lock from a different host (staleness unknown) causes DiffLockError."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        _write_lock_file(
            context_dir,
            LockRecord(
                writer_id="remote-writer",
                host="some-other-host",
                pid=12345,
                acquired_at="2026-01-01T00:00:00Z",
                mode="sync",
            ),
        )

        with pytest.raises(DiffLockError, match="mutating operation"):
            await ctx.diff()

    async def test_corrupt_lock_file_raises_diff_lock_error(self, context_dir: Path) -> None:
        """A corrupt lock file causes DiffLockError (not StaleLockError)."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        lock_path = context_dir / LOCK_FILENAME
        lock_path.write_text(":::not yaml:::", encoding="utf-8")

        with pytest.raises(DiffLockError, match="could not be read"):
            await ctx.diff()

    async def test_lock_error_message_explains_rationale(self, context_dir: Path) -> None:
        """The DiffLockError message explains why lock refusal is intentional."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        _write_lock_file(
            context_dir,
            LockRecord(
                writer_id="writer-x",
                host=platform.node(),
                pid=os.getpid(),
                acquired_at="2026-01-01T00:00:00Z",
                mode="refresh",
            ),
        )

        with pytest.raises(DiffLockError, match="rate-limited"):
            await ctx.diff()


# ---------------------------------------------------------------------------
# Stale-lock observation: diff proceeds, lock file remains
# ---------------------------------------------------------------------------


class TestDiffStaleLock:
    """diff proceeds when a stale lock is detected, but does not modify it."""

    async def test_stale_lock_allows_diff(self, context_dir: Path) -> None:
        """A demonstrably stale lock (dead PID, same host) does not block diff."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        # Use PID 2**22 which is almost certainly not alive.
        _write_lock_file(
            context_dir,
            LockRecord(
                writer_id="dead-writer",
                host=platform.node(),
                pid=2**22,
                acquired_at="2026-01-01T00:00:00Z",
                mode="sync",
            ),
        )

        result = await ctx.diff()
        assert len(result.entries) == 1
        assert result.entries[0].status == "current"

    async def test_stale_lock_is_not_cleared(self, context_dir: Path) -> None:
        """Diff must never clear, preempt, or create the writer lock record."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        lock_path = context_dir / LOCK_FILENAME
        _write_lock_file(
            context_dir,
            LockRecord(
                writer_id="dead-writer",
                host=platform.node(),
                pid=2**22,
                acquired_at="2026-01-01T00:00:00Z",
                mode="sync",
            ),
        )
        content_before = lock_path.read_text(encoding="utf-8")

        await ctx.diff()

        # Lock file must still exist and be unchanged.
        assert lock_path.is_file()
        assert lock_path.read_text(encoding="utf-8") == content_before


# ---------------------------------------------------------------------------
# No lock present: diff runs normally
# ---------------------------------------------------------------------------


class TestDiffNoLock:
    """diff runs normally when no lock file exists."""

    async def test_no_lock_file_allows_diff(self, context_dir: Path) -> None:
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        # Confirm no lock remains after sync.
        assert not (context_dir / LOCK_FILENAME).exists()

        result = await ctx.diff()
        assert len(result.entries) == 1


# ---------------------------------------------------------------------------
# Changed-field reporting
# ---------------------------------------------------------------------------


class TestDiffChangedFields:
    """diff detects and reports changed cursor components."""

    async def test_unchanged_upstream_is_current(self, context_dir: Path) -> None:
        """When nothing changed upstream, all tickets are current."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        result = await ctx.diff()
        assert len(result.entries) == 1
        entry = result.entries[0]
        assert entry.ticket_key == "TEST-1"
        assert entry.status == "current"
        assert entry.changed_fields == []

    async def test_issue_updated_at_change_is_stale(self, context_dir: Path) -> None:
        """A changed issue updated_at makes the ticket stale."""
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="uuid-1",
                issue_key="TEST-1",
                updated_at="2026-01-01T00:00:00Z",
            )
        )
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        # Update the issue's updated_at to simulate upstream change.
        gw.add_issue(
            make_issue(
                issue_id="uuid-1",
                issue_key="TEST-1",
                updated_at="2026-01-02T00:00:00Z",
            )
        )

        result = await ctx.diff()
        entry = result.entries[0]
        assert entry.status == "stale"
        assert "issue_updated_at" in entry.changed_fields

    async def test_comments_change_is_stale(self, context_dir: Path) -> None:
        """A changed comments_signature makes the ticket stale."""
        from context_sync._gateway import CommentData

        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        # Add a comment to the issue.
        gw.add_issue(
            make_issue(
                issue_id="uuid-1",
                issue_key="TEST-1",
                comments=[
                    CommentData(
                        comment_id="c1",
                        body="New comment",
                        author="user",
                        created_at="2026-01-02T00:00:00Z",
                        updated_at="2026-01-02T00:00:00Z",
                        parent_comment_id=None,
                    )
                ],
            )
        )

        result = await ctx.diff()
        entry = result.entries[0]
        assert entry.status == "stale"
        assert "comments_signature" in entry.changed_fields

    async def test_relations_change_is_stale(self, context_dir: Path) -> None:
        """A changed relations_signature makes the ticket stale."""
        from context_sync._gateway import RelationData

        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        # Add a relation to the issue.
        gw.add_issue(
            make_issue(
                issue_id="uuid-1",
                issue_key="TEST-1",
                relations=[
                    RelationData(
                        dimension="blocks",
                        relation_type="blocks",
                        target_issue_id="uuid-other",
                        target_issue_key="TEST-99",
                    )
                ],
            )
        )

        result = await ctx.diff()
        entry = result.entries[0]
        assert entry.status == "stale"
        assert "relations_signature" in entry.changed_fields

    async def test_issue_key_rename_is_stale(self, context_dir: Path) -> None:
        """An issue key rename is detected and reported."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="OLD-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        # Change the issue key (simulates a team prefix rename in Linear).
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="NEW-1"))

        result = await ctx.diff()
        entry = result.entries[0]
        assert entry.status == "stale"
        assert "issue_key" in entry.changed_fields
        # The ticket_id should reflect the new remote key.
        assert entry.ticket_key == "NEW-1"

    async def test_multiple_changed_fields(self, context_dir: Path) -> None:
        """Multiple cursor components can change simultaneously."""
        from context_sync._gateway import CommentData

        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="uuid-1",
                issue_key="TEST-1",
                updated_at="2026-01-01T00:00:00Z",
            )
        )
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        # Change both updated_at and add a comment.
        gw.add_issue(
            make_issue(
                issue_id="uuid-1",
                issue_key="TEST-1",
                updated_at="2026-01-02T00:00:00Z",
                comments=[
                    CommentData(
                        comment_id="c1",
                        body="New",
                        author="u",
                        created_at="2026-01-02T00:00:00Z",
                        updated_at="2026-01-02T00:00:00Z",
                        parent_comment_id=None,
                    )
                ],
            )
        )

        result = await ctx.diff()
        entry = result.entries[0]
        assert entry.status == "stale"
        assert "comments_signature" in entry.changed_fields
        assert "issue_updated_at" in entry.changed_fields
        # changed_fields should be sorted.
        assert entry.changed_fields == sorted(entry.changed_fields)

    async def test_changed_fields_sorted(self, context_dir: Path) -> None:
        """changed_fields list is always lexicographically sorted."""
        from context_sync._gateway import CommentData, RelationData

        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="uuid-1",
                issue_key="OLD-1",
                updated_at="2026-01-01T00:00:00Z",
            )
        )
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        # Change everything: updated_at, comments, relations, and key.
        gw.add_issue(
            make_issue(
                issue_id="uuid-1",
                issue_key="NEW-1",
                updated_at="2026-01-02T00:00:00Z",
                comments=[
                    CommentData(
                        comment_id="c1",
                        body="x",
                        author="u",
                        created_at="2026-01-02T00:00:00Z",
                        updated_at="2026-01-02T00:00:00Z",
                        parent_comment_id=None,
                    )
                ],
                relations=[
                    RelationData(
                        dimension="blocks",
                        relation_type="blocks",
                        target_issue_id="uuid-x",
                        target_issue_key="X-1",
                    )
                ],
            )
        )

        result = await ctx.diff()
        entry = result.entries[0]
        assert entry.changed_fields == sorted(entry.changed_fields)
        assert len(entry.changed_fields) == 4


# ---------------------------------------------------------------------------
# Unavailable-ticket classification (missing_remotely)
# ---------------------------------------------------------------------------


class TestDiffMissingRemotely:
    """diff classifies unavailable tickets as missing_remotely."""

    async def test_hidden_issue_is_missing_remotely(self, context_dir: Path) -> None:
        """An issue that becomes invisible is classified as missing_remotely."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        gw.hide_issue("uuid-1")

        result = await ctx.diff()
        assert len(result.entries) == 1
        entry = result.entries[0]
        assert entry.ticket_key == "TEST-1"
        assert entry.status == "missing_remotely"
        assert entry.changed_fields == []

    async def test_multiple_tickets_mixed_visibility(self, context_dir: Path) -> None:
        """Some tickets visible, some not — classified correctly."""
        from context_sync._gateway import RelationData

        gw = FakeLinearGateway()
        root = make_issue(
            issue_id="uuid-root",
            issue_key="ROOT-1",
            relations=[
                RelationData(
                    dimension="blocks",
                    relation_type="blocks",
                    target_issue_id="uuid-child",
                    target_issue_key="CHILD-1",
                )
            ],
        )
        child = make_issue(issue_id="uuid-child", issue_key="CHILD-1")
        gw.add_issue(root)
        gw.add_issue(child)

        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-root")

        # Hide the child but keep the root visible.
        gw.hide_issue("uuid-child")

        result = await ctx.diff()
        root_entry = _find_entry(result.entries, "ROOT-1")
        child_entry = _find_entry(result.entries, "CHILD-1")

        assert root_entry.status == "current"
        assert child_entry.status == "missing_remotely"


# ---------------------------------------------------------------------------
# Missing locally
# ---------------------------------------------------------------------------


class TestDiffMissingLocally:
    """diff detects tickets tracked in the manifest but absent from disk."""

    async def test_deleted_file_is_missing_locally(self, context_dir: Path) -> None:
        """A file deleted after sync is classified as missing_locally."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        # Verify the file was created, then delete it.
        ticket_file = context_dir / "TEST-1.md"
        assert ticket_file.is_file()
        ticket_file.unlink()

        result = await ctx.diff()
        assert len(result.entries) == 1
        entry = result.entries[0]
        assert entry.ticket_key == "TEST-1"
        assert entry.status == "missing_locally"
        assert entry.changed_fields == []


# ---------------------------------------------------------------------------
# Manifest errors
# ---------------------------------------------------------------------------


class TestDiffManifestErrors:
    """diff fails when the manifest is missing or invalid."""

    async def test_no_manifest_raises_manifest_error(self, context_dir: Path) -> None:
        """Running diff without a prior sync raises ManifestError."""
        gw = FakeLinearGateway()
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)

        with pytest.raises(ManifestError):
            await ctx.diff()


# ---------------------------------------------------------------------------
# Empty manifest (no tickets tracked)
# ---------------------------------------------------------------------------


class TestDiffEmptyManifest:
    """diff with an empty manifest returns an empty DiffResult."""

    async def test_empty_manifest_returns_empty_result(self, context_dir: Path) -> None:
        """A manifest with no tracked tickets yields an empty DiffResult."""
        from context_sync._manifest import initialize_manifest, save_manifest
        from context_sync._testing import DEFAULT_FAKE_WORKSPACE

        manifest = initialize_manifest(
            workspace=DEFAULT_FAKE_WORKSPACE,
            dimensions={"blocks": 1, "sub_issues": 2, "relates_to": 1},
            max_tickets_per_root=200,
        )
        save_manifest(manifest, context_dir)

        gw = FakeLinearGateway()
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)

        result = await ctx.diff()
        assert result.entries == []
        assert result.errors == []


# ---------------------------------------------------------------------------
# No files modified (immutability contract)
# ---------------------------------------------------------------------------


class TestDiffNeverModifiesFiles:
    """diff must not modify any files, even when drift is detected."""

    async def test_no_file_writes_when_stale(self, context_dir: Path) -> None:
        """Even when tickets are stale, no files are written or changed."""
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="uuid-1",
                issue_key="TEST-1",
                updated_at="2026-01-01T00:00:00Z",
            )
        )
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        # Record file mtimes.
        ticket_file = context_dir / "TEST-1.md"
        manifest_file = context_dir / ".context-sync.yml"
        ticket_mtime = ticket_file.stat().st_mtime
        manifest_mtime = manifest_file.stat().st_mtime
        ticket_content = ticket_file.read_text(encoding="utf-8")

        # Make the ticket stale.
        gw.add_issue(
            make_issue(
                issue_id="uuid-1",
                issue_key="TEST-1",
                updated_at="2026-01-02T00:00:00Z",
            )
        )

        result = await ctx.diff()
        assert result.entries[0].status == "stale"

        # No files should be modified.
        assert ticket_file.stat().st_mtime == ticket_mtime
        assert manifest_file.stat().st_mtime == manifest_mtime
        assert ticket_file.read_text(encoding="utf-8") == ticket_content
        # No lock file should be created.
        assert not (context_dir / LOCK_FILENAME).exists()

    async def test_no_lock_file_created(self, context_dir: Path) -> None:
        """Diff must not create a lock file."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        assert not (context_dir / LOCK_FILENAME).exists()

        await ctx.diff()

        assert not (context_dir / LOCK_FILENAME).exists()


# ---------------------------------------------------------------------------
# Format-version freshness gate (M3-3-R1)
# ---------------------------------------------------------------------------


class TestDiffFormatVersion:
    """diff treats outdated format_version as stale."""

    async def test_outdated_format_version_is_stale(self, context_dir: Path) -> None:
        """A file with format_version below current is stale even if cursor matches."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        # Downgrade format_version without changing the cursor.
        ticket_file = context_dir / "TEST-1.md"
        text = ticket_file.read_text(encoding="utf-8")
        text = text.replace("format_version: 1", "format_version: 0")
        ticket_file.write_text(text, encoding="utf-8")

        result = await ctx.diff()
        assert len(result.entries) == 1
        entry = result.entries[0]
        assert entry.status == "stale"

    async def test_missing_format_version_is_stale(self, context_dir: Path) -> None:
        """A file without format_version is stale."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        # Remove format_version line from frontmatter.
        ticket_file = context_dir / "TEST-1.md"
        lines = ticket_file.read_text(encoding="utf-8").splitlines(keepends=True)
        lines = [ln for ln in lines if not ln.startswith("format_version:")]
        ticket_file.write_text("".join(lines), encoding="utf-8")

        result = await ctx.diff()
        assert len(result.entries) == 1
        assert result.entries[0].status == "stale"


# ---------------------------------------------------------------------------
# Identity validation (M3-3-R2)
# ---------------------------------------------------------------------------


class TestDiffIdentityValidation:
    """diff validates ticket_uuid against manifest and reports mismatches."""

    async def test_mismatched_ticket_uuid_is_error(self, context_dir: Path) -> None:
        """Mismatched ticket_uuid produces an identity-mismatch error."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        # Change ticket_uuid to a different value.
        ticket_file = context_dir / "TEST-1.md"
        text = ticket_file.read_text(encoding="utf-8")
        text = text.replace("ticket_uuid: uuid-1", "ticket_uuid: uuid-other")
        ticket_file.write_text(text, encoding="utf-8")

        result = await ctx.diff()
        assert result.entries == []  # no normal entries
        assert len(result.errors) == 1
        assert result.errors[0].error_type == "identity_mismatch"
        assert result.errors[0].ticket_key == "TEST-1"

    async def test_missing_ticket_uuid_is_error(self, context_dir: Path) -> None:
        """A file without ticket_uuid produces an identity-mismatch error."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        # Remove ticket_uuid line.
        ticket_file = context_dir / "TEST-1.md"
        lines = ticket_file.read_text(encoding="utf-8").splitlines(keepends=True)
        lines = [ln for ln in lines if not ln.startswith("ticket_uuid:")]
        ticket_file.write_text("".join(lines), encoding="utf-8")

        result = await ctx.diff()
        assert result.entries == []
        assert len(result.errors) == 1
        assert result.errors[0].error_type == "identity_mismatch"

    async def test_malformed_frontmatter_is_error(self, context_dir: Path) -> None:
        """Corrupt YAML frontmatter produces a corrupt_frontmatter error."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="TEST-1"))
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-1")

        # Replace file content with genuinely unparseable YAML.
        ticket_file = context_dir / "TEST-1.md"
        ticket_file.write_text("---\nkey: [unclosed\n---\nbody\n", encoding="utf-8")

        result = await ctx.diff()
        assert result.entries == []
        assert len(result.errors) == 1
        assert result.errors[0].error_type == "corrupt_frontmatter"
        assert result.errors[0].ticket_key == "TEST-1"


# ---------------------------------------------------------------------------
# Error surface (M3-3-R3)
# ---------------------------------------------------------------------------


class TestDiffErrorSurface:
    """diff reports ticket-level read errors through DiffResult.errors."""

    async def test_unreadable_file_produces_error(self, context_dir: Path) -> None:
        """An unreadable ticket file produces a read_error in DiffResult.errors."""
        from context_sync._gateway import RelationData

        gw = FakeLinearGateway()
        root = make_issue(
            issue_id="uuid-root",
            issue_key="ROOT-1",
            relations=[
                RelationData(
                    dimension="blocks",
                    relation_type="blocks",
                    target_issue_id="uuid-child",
                    target_issue_key="CHILD-1",
                )
            ],
        )
        child = make_issue(issue_id="uuid-child", issue_key="CHILD-1")
        gw.add_issue(root)
        gw.add_issue(child)
        ctx = make_context_sync(context_dir=context_dir, gateway=gw)
        await ctx.sync("uuid-root")

        # Make the child file unreadable.
        child_file = context_dir / "CHILD-1.md"
        child_file.chmod(0o000)

        try:
            result = await ctx.diff()
            # The root should still be classified normally.
            assert len(result.entries) == 1
            assert result.entries[0].ticket_key == "ROOT-1"
            # The child should appear in errors.
            assert len(result.errors) == 1
            assert result.errors[0].error_type == "read_error"
            assert result.errors[0].ticket_key == "CHILD-1"
        finally:
            # Restore permissions for cleanup.
            child_file.chmod(0o644)
