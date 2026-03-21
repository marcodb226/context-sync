"""
Tests for the ContextSync.refresh flow (M3-1).

Exercises incremental whole-snapshot update: composite-cursor freshness
checks, stale-vs-fresh selective re-fetch, quarantine/recovery for
unavailable roots, explicit remove policy, derived-ticket pruning after
reachability changes, and no-rewrite idempotency for unchanged upstream.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from context_sync._errors import ManifestError
from context_sync._gateway import (
    CommentData,
    RelationData,
)
from context_sync._manifest import (
    load_manifest,
    save_manifest,
)
from context_sync._models import SyncResult
from context_sync._testing import (
    FakeLinearGateway,
    make_issue,
    make_syncer,
)
from context_sync._yaml import parse_frontmatter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _sync_then_refresh(
    context_dir: Path,
    gateway: FakeLinearGateway,
    root_id: str = "uuid-root",
    **refresh_kwargs: object,
) -> tuple[SyncResult, SyncResult]:
    """Sync a root, then refresh.  Returns (sync_result, refresh_result)."""
    syncer = make_syncer(context_dir=context_dir, gateway=gateway)
    sync_result = await syncer.sync(root_id)
    refresh_result = await syncer.refresh(**refresh_kwargs)
    return sync_result, refresh_result


def _read_ticket_fm(context_dir: Path, issue_key: str) -> dict:
    """Read the frontmatter of a ticket file."""
    return parse_frontmatter((context_dir / f"{issue_key}.md").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Basic refresh: unchanged upstream → no-op
# ---------------------------------------------------------------------------


class TestRefreshUnchangedNoop:
    """When nothing changed upstream, refresh rewrites nothing."""

    async def test_unchanged_upstream_all_fresh(self, context_dir: Path) -> None:
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-root", issue_key="ROOT-1"))

        syncer = make_syncer(context_dir=context_dir, gateway=gw)
        await syncer.sync("uuid-root")

        # Record file mtime after sync.
        ticket_file = context_dir / "ROOT-1.md"
        mtime_after_sync = ticket_file.stat().st_mtime

        result = await syncer.refresh()

        assert result.created == []
        assert result.updated == []
        assert result.removed == []
        assert result.errors == []
        assert "ROOT-1" in result.unchanged

        # File should NOT have been rewritten.
        assert ticket_file.stat().st_mtime == mtime_after_sync

    async def test_manifest_snapshot_mode_is_refresh(self, context_dir: Path) -> None:
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-root", issue_key="ROOT-1"))

        syncer = make_syncer(context_dir=context_dir, gateway=gw)
        await syncer.sync("uuid-root")
        await syncer.refresh()

        manifest = load_manifest(context_dir)
        assert manifest.snapshot is not None
        assert manifest.snapshot.mode == "refresh"
        assert manifest.snapshot.completed_successfully is True


# ---------------------------------------------------------------------------
# Stale-vs-fresh refresh: selective re-fetch
# ---------------------------------------------------------------------------


class TestRefreshStaleFresh:
    """Refresh re-fetches only stale tickets and skips fresh ones."""

    async def test_stale_ticket_updated(self, context_dir: Path) -> None:
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
                ),
            ],
        )
        child = make_issue(
            issue_id="uuid-child",
            issue_key="CHILD-1",
            title="Original title",
        )
        gw.add_issue(root)
        gw.add_issue(child)

        syncer = make_syncer(context_dir=context_dir, gateway=gw)
        await syncer.sync("uuid-root")

        # Mutate child upstream (change updated_at to trigger staleness).
        child_updated = make_issue(
            issue_id="uuid-child",
            issue_key="CHILD-1",
            title="Updated title",
            updated_at="2026-02-01T00:00:00Z",
        )
        gw.add_issue(child_updated)

        result = await syncer.refresh()

        assert "CHILD-1" in result.updated
        assert "ROOT-1" in result.unchanged
        assert result.created == []
        assert result.removed == []

        # Verify the file content was updated.
        fm = _read_ticket_fm(context_dir, "CHILD-1")
        assert fm["title"] == "Updated title"

    async def test_comment_change_triggers_staleness(self, context_dir: Path) -> None:
        gw = FakeLinearGateway()
        root = make_issue(issue_id="uuid-root", issue_key="ROOT-1")
        gw.add_issue(root)

        syncer = make_syncer(context_dir=context_dir, gateway=gw)
        await syncer.sync("uuid-root")

        # Add a comment upstream (changes comments_signature).
        root_with_comment = make_issue(
            issue_id="uuid-root",
            issue_key="ROOT-1",
            comments=[
                CommentData(
                    comment_id="comment-1",
                    body="New comment",
                    author="tester",
                    created_at="2026-02-01T00:00:00Z",
                    updated_at="2026-02-01T00:00:00Z",
                    parent_comment_id=None,
                ),
            ],
        )
        gw.add_issue(root_with_comment)

        result = await syncer.refresh()

        assert "ROOT-1" in result.updated

    async def test_relation_change_triggers_staleness(self, context_dir: Path) -> None:
        gw = FakeLinearGateway()
        child = make_issue(issue_id="uuid-child", issue_key="CHILD-1")
        root = make_issue(issue_id="uuid-root", issue_key="ROOT-1")
        gw.add_issue(root)
        gw.add_issue(child)

        syncer = make_syncer(context_dir=context_dir, gateway=gw)
        await syncer.sync("uuid-root")

        # Add a relation upstream (changes relations_signature).
        root_with_relation = make_issue(
            issue_id="uuid-root",
            issue_key="ROOT-1",
            relations=[
                RelationData(
                    dimension="blocks",
                    relation_type="blocks",
                    target_issue_id="uuid-child",
                    target_issue_key="CHILD-1",
                ),
            ],
        )
        gw.add_issue(root_with_relation)

        result = await syncer.refresh()

        assert "ROOT-1" in result.updated


# ---------------------------------------------------------------------------
# Root quarantine
# ---------------------------------------------------------------------------


class TestRefreshQuarantine:
    """Unavailable roots are quarantined by default."""

    async def test_unavailable_root_quarantined(self, context_dir: Path) -> None:
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-root", issue_key="ROOT-1"))

        syncer = make_syncer(context_dir=context_dir, gateway=gw)
        await syncer.sync("uuid-root")

        # Hide the root.
        gw.hide_issue("uuid-root")

        result = await syncer.refresh()

        # Root should be quarantined, not removed.
        manifest = load_manifest(context_dir)
        assert "uuid-root" in manifest.roots
        assert manifest.roots["uuid-root"].state == "quarantined"
        assert manifest.roots["uuid-root"].quarantined_reason == "not_available_in_visible_view"

        # Error should be recorded.
        assert len(result.errors) == 1
        assert result.errors[0].error_type == "root_quarantined"
        assert result.errors[0].ticket_id == "ROOT-1"

        # Ticket file should still exist with quarantine markers.
        fm = _read_ticket_fm(context_dir, "ROOT-1")
        assert fm["root_state"] == "quarantined"
        assert fm["quarantined_reason"] == "not_available_in_visible_view"

        # Warning preamble should be in the file body.
        content = (context_dir / "ROOT-1.md").read_text(encoding="utf-8")
        assert "**Warning:**" in content

    async def test_quarantined_root_not_traversed(self, context_dir: Path) -> None:
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
                ),
            ],
        )
        child = make_issue(issue_id="uuid-child", issue_key="CHILD-1")
        gw.add_issue(root)
        gw.add_issue(child)

        syncer = make_syncer(context_dir=context_dir, gateway=gw)
        await syncer.sync("uuid-root")

        # Both files exist after sync.
        assert (context_dir / "ROOT-1.md").is_file()
        assert (context_dir / "CHILD-1.md").is_file()

        # Hide the root — derived child should be pruned since the quarantined
        # root is not traversed.
        gw.hide_issue("uuid-root")

        result = await syncer.refresh()

        assert "CHILD-1" in result.removed
        assert (context_dir / "ROOT-1.md").is_file()  # quarantined, not removed
        assert not (context_dir / "CHILD-1.md").is_file()


# ---------------------------------------------------------------------------
# Root reactivation
# ---------------------------------------------------------------------------


class TestRefreshReactivation:
    """Quarantined roots are reactivated when they become visible again."""

    async def test_quarantined_root_reactivated(self, context_dir: Path) -> None:
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-root", issue_key="ROOT-1"))

        syncer = make_syncer(context_dir=context_dir, gateway=gw)
        await syncer.sync("uuid-root")

        # Quarantine the root.
        gw.hide_issue("uuid-root")
        await syncer.refresh()

        manifest = load_manifest(context_dir)
        assert manifest.roots["uuid-root"].state == "quarantined"

        # Recover the root.
        gw.unhide_issue("uuid-root")
        result = await syncer.refresh()

        manifest = load_manifest(context_dir)
        assert manifest.roots["uuid-root"].state == "active"
        assert manifest.roots["uuid-root"].quarantined_reason is None

        # File should be rewritten to remove quarantine markers.
        fm = _read_ticket_fm(context_dir, "ROOT-1")
        assert fm.get("root_state") == "active"
        assert "quarantined_reason" not in fm

        content = (context_dir / "ROOT-1.md").read_text(encoding="utf-8")
        assert "**Warning:**" not in content

        # The root should appear in updated (rewritten to clear quarantine).
        assert "ROOT-1" in result.updated


# ---------------------------------------------------------------------------
# Explicit remove policy
# ---------------------------------------------------------------------------


class TestRefreshRemovePolicy:
    """Missing-root policy 'remove' deletes unavailable roots immediately."""

    async def test_remove_policy_deletes_root(self, context_dir: Path) -> None:
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-root", issue_key="ROOT-1"))

        syncer = make_syncer(context_dir=context_dir, gateway=gw)
        await syncer.sync("uuid-root")

        # Hide the root and refresh with remove policy.
        gw.hide_issue("uuid-root")
        result = await syncer.refresh(missing_root_policy="remove")

        # Root should be removed from manifest and file deleted.
        manifest = load_manifest(context_dir)
        assert "uuid-root" not in manifest.roots
        assert "uuid-root" not in manifest.tickets
        assert not (context_dir / "ROOT-1.md").is_file()

        # Removed list should contain the root key.
        assert "ROOT-1" in result.removed


# ---------------------------------------------------------------------------
# Changed-ticket selective rewrite
# ---------------------------------------------------------------------------


class TestRefreshSelectiveRewrite:
    """Only stale tickets are re-fetched and rewritten."""

    async def test_mixed_stale_and_fresh(self, context_dir: Path) -> None:
        gw = FakeLinearGateway()
        root = make_issue(
            issue_id="uuid-root",
            issue_key="ROOT-1",
            relations=[
                RelationData(
                    dimension="blocks",
                    relation_type="blocks",
                    target_issue_id="uuid-a",
                    target_issue_key="A-1",
                ),
                RelationData(
                    dimension="blocks",
                    relation_type="blocks",
                    target_issue_id="uuid-b",
                    target_issue_key="B-1",
                ),
            ],
        )
        a = make_issue(issue_id="uuid-a", issue_key="A-1", title="A original")
        b = make_issue(issue_id="uuid-b", issue_key="B-1", title="B original")
        gw.add_issue(root)
        gw.add_issue(a)
        gw.add_issue(b)

        syncer = make_syncer(context_dir=context_dir, gateway=gw)
        await syncer.sync("uuid-root")

        # Mutate only A upstream.
        a_updated = make_issue(
            issue_id="uuid-a",
            issue_key="A-1",
            title="A updated",
            updated_at="2026-02-01T00:00:00Z",
        )
        gw.add_issue(a_updated)

        result = await syncer.refresh()

        assert "A-1" in result.updated
        assert "B-1" in result.unchanged
        assert "ROOT-1" in result.unchanged

        # Verify only A was rewritten.
        fm_a = _read_ticket_fm(context_dir, "A-1")
        assert fm_a["title"] == "A updated"

        fm_b = _read_ticket_fm(context_dir, "B-1")
        assert fm_b["title"] == "B original"


# ---------------------------------------------------------------------------
# Newly discovered tickets
# ---------------------------------------------------------------------------


class TestRefreshNewlyDiscovered:
    """Tickets newly reachable during refresh are created."""

    async def test_new_ticket_discovered_via_relation(self, context_dir: Path) -> None:
        gw = FakeLinearGateway()
        root = make_issue(issue_id="uuid-root", issue_key="ROOT-1")
        gw.add_issue(root)

        syncer = make_syncer(context_dir=context_dir, gateway=gw)
        await syncer.sync("uuid-root")

        # Add a relation to a new ticket after sync.
        new_child = make_issue(issue_id="uuid-new", issue_key="NEW-1")
        root_updated = make_issue(
            issue_id="uuid-root",
            issue_key="ROOT-1",
            updated_at="2026-02-01T00:00:00Z",
            relations=[
                RelationData(
                    dimension="blocks",
                    relation_type="blocks",
                    target_issue_id="uuid-new",
                    target_issue_key="NEW-1",
                ),
            ],
        )
        gw.add_issue(new_child)
        gw.add_issue(root_updated)

        result = await syncer.refresh()

        assert "NEW-1" in result.created
        assert (context_dir / "NEW-1.md").is_file()


# ---------------------------------------------------------------------------
# Derived-ticket pruning
# ---------------------------------------------------------------------------


class TestRefreshPruning:
    """Derived tickets no longer reachable are pruned."""

    async def test_unreachable_derived_ticket_pruned(self, context_dir: Path) -> None:
        gw = FakeLinearGateway()
        child = make_issue(issue_id="uuid-child", issue_key="CHILD-1")
        root = make_issue(
            issue_id="uuid-root",
            issue_key="ROOT-1",
            relations=[
                RelationData(
                    dimension="blocks",
                    relation_type="blocks",
                    target_issue_id="uuid-child",
                    target_issue_key="CHILD-1",
                ),
            ],
        )
        gw.add_issue(root)
        gw.add_issue(child)

        syncer = make_syncer(context_dir=context_dir, gateway=gw)
        await syncer.sync("uuid-root")

        assert (context_dir / "CHILD-1.md").is_file()

        # Remove the relation — child is no longer reachable.
        root_no_rel = make_issue(
            issue_id="uuid-root",
            issue_key="ROOT-1",
            updated_at="2026-02-01T00:00:00Z",
        )
        gw.add_issue(root_no_rel)

        result = await syncer.refresh()

        assert "CHILD-1" in result.removed
        assert not (context_dir / "CHILD-1.md").is_file()


# ---------------------------------------------------------------------------
# Refresh requires existing manifest
# ---------------------------------------------------------------------------


class TestRefreshRequiresManifest:
    """Refresh fails fast when no manifest exists."""

    async def test_no_manifest_raises(self, context_dir: Path) -> None:
        gw = FakeLinearGateway()
        syncer = make_syncer(context_dir=context_dir, gateway=gw)

        with pytest.raises(ManifestError):
            await syncer.refresh()


# ---------------------------------------------------------------------------
# Multi-root refresh
# ---------------------------------------------------------------------------


class TestRefreshMultiRoot:
    """Refresh handles multiple roots correctly."""

    async def test_multi_root_refresh(self, context_dir: Path) -> None:
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-r1", issue_key="R1-1"))
        gw.add_issue(make_issue(issue_id="uuid-r2", issue_key="R2-1"))

        syncer = make_syncer(context_dir=context_dir, gateway=gw)
        await syncer.sync("uuid-r1")
        await syncer.sync("uuid-r2")

        # Both roots are now in the manifest.
        manifest = load_manifest(context_dir)
        assert "uuid-r1" in manifest.roots
        assert "uuid-r2" in manifest.roots

        # Update only R2.
        r2_updated = make_issue(
            issue_id="uuid-r2",
            issue_key="R2-1",
            title="R2 updated",
            updated_at="2026-02-01T00:00:00Z",
        )
        gw.add_issue(r2_updated)

        result = await syncer.refresh()

        assert "R2-1" in result.updated
        assert "R1-1" in result.unchanged

    async def test_one_root_quarantined_other_refreshed(self, context_dir: Path) -> None:
        gw = FakeLinearGateway()
        child = make_issue(issue_id="uuid-child", issue_key="CHILD-1")
        gw.add_issue(
            make_issue(
                issue_id="uuid-r1",
                issue_key="R1-1",
                relations=[
                    RelationData(
                        dimension="blocks",
                        relation_type="blocks",
                        target_issue_id="uuid-child",
                        target_issue_key="CHILD-1",
                    ),
                ],
            )
        )
        gw.add_issue(make_issue(issue_id="uuid-r2", issue_key="R2-1"))
        gw.add_issue(child)

        syncer = make_syncer(context_dir=context_dir, gateway=gw)
        await syncer.sync("uuid-r1")
        await syncer.sync("uuid-r2")

        # Hide R1 but keep R2 visible.
        gw.hide_issue("uuid-r1")

        result = await syncer.refresh()

        manifest = load_manifest(context_dir)
        assert manifest.roots["uuid-r1"].state == "quarantined"
        assert manifest.roots["uuid-r2"].state == "active"

        # R2 should be unchanged, CHILD-1 should be pruned (only reachable
        # from quarantined R1).
        assert "CHILD-1" in result.removed

    async def test_empty_manifest_no_roots(self, context_dir: Path) -> None:
        """Refresh with an existing but root-less manifest succeeds vacuously."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-r1", issue_key="R1-1"))

        syncer = make_syncer(context_dir=context_dir, gateway=gw)
        await syncer.sync("uuid-r1")

        # Manually remove all roots from manifest (edge case).
        manifest = load_manifest(context_dir)
        manifest.roots.clear()
        save_manifest(manifest, context_dir)

        result = await syncer.refresh()

        assert result == SyncResult()
