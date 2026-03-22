"""
Tests for the ContextSync.add and ContextSync.remove_root flows (M3-2).

Exercises root-set mutation through alias-aware ticket resolution, workspace
checks, manifest updates, and reuse of the whole-snapshot refresh behavior:
add by issue key, add by Linear URL, URL workspace mismatch, overlapping-root
refresh, idempotent re-add, add to empty context, remove-root basic, remove
with still-reachable ticket, and RootNotInManifestError for non-roots.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from context_sync._errors import (
    RootNotFoundError,
    RootNotInManifestError,
    WorkspaceMismatchError,
)
from context_sync._gateway import RelationData
from context_sync._manifest import load_manifest
from context_sync._testing import (
    DEFAULT_FAKE_WORKSPACE,
    FakeLinearGateway,
    make_issue,
    make_syncer,
)
from context_sync._yaml import parse_frontmatter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_ticket_fm(context_dir: Path, issue_key: str) -> dict:
    """Read the frontmatter of a ticket file."""
    return parse_frontmatter((context_dir / f"{issue_key}.md").read_text(encoding="utf-8"))


# ===========================================================================
# add — by issue key
# ===========================================================================


class TestAddByIssueKey:
    """Add a root by issue key."""

    async def test_add_to_existing_context(
        self,
        context_dir: Path,
        fake_gateway: FakeLinearGateway,
    ) -> None:
        """Add a second root to a context that already has one root."""
        root1 = make_issue(issue_id="uuid-root1", issue_key="ROOT-1")
        root2 = make_issue(issue_id="uuid-root2", issue_key="ROOT-2")
        fake_gateway.add_issue(root1)
        fake_gateway.add_issue(root2)

        syncer = make_syncer(context_dir=context_dir, gateway=fake_gateway)
        await syncer.sync("ROOT-1")

        result = await syncer.add("ROOT-2")

        # ROOT-2 should appear in the result.
        assert "ROOT-2" in result.created or "ROOT-2" in result.updated

        # Manifest reflects both roots and the correct snapshot mode.
        manifest = load_manifest(context_dir)
        assert "uuid-root1" in manifest.roots
        assert "uuid-root2" in manifest.roots
        assert manifest.roots["uuid-root2"].state == "active"
        assert manifest.snapshot is not None
        assert manifest.snapshot.mode == "add"
        assert manifest.snapshot.completed_successfully is True

    async def test_add_first_root_empty_context(
        self,
        context_dir: Path,
        fake_gateway: FakeLinearGateway,
    ) -> None:
        """Add a root to an empty context directory (initializes manifest)."""
        root = make_issue(issue_id="uuid-root", issue_key="ROOT-1")
        fake_gateway.add_issue(root)

        syncer = make_syncer(context_dir=context_dir, gateway=fake_gateway)
        result = await syncer.add("ROOT-1")

        assert "ROOT-1" in result.created
        assert (context_dir / "ROOT-1.md").is_file()

        manifest = load_manifest(context_dir)
        assert "uuid-root" in manifest.roots
        assert manifest.workspace_id == DEFAULT_FAKE_WORKSPACE.workspace_id
        assert manifest.snapshot is not None
        assert manifest.snapshot.mode == "add"

    async def test_add_already_active_root_is_idempotent(
        self,
        context_dir: Path,
        fake_gateway: FakeLinearGateway,
    ) -> None:
        """Adding an already-active root re-runs refresh without error."""
        root = make_issue(issue_id="uuid-root", issue_key="ROOT-1")
        fake_gateway.add_issue(root)

        syncer = make_syncer(context_dir=context_dir, gateway=fake_gateway)
        await syncer.sync("ROOT-1")

        result = await syncer.add("ROOT-1")

        # Succeeds; ticket is unchanged.
        assert result.errors == []
        manifest = load_manifest(context_dir)
        assert "uuid-root" in manifest.roots
        assert manifest.roots["uuid-root"].state == "active"
        assert manifest.snapshot is not None
        assert manifest.snapshot.mode == "add"

    async def test_add_promotes_derived_to_root(
        self,
        context_dir: Path,
        fake_gateway: FakeLinearGateway,
    ) -> None:
        """Adding a ticket that is already tracked as derived promotes it to root."""
        child = make_issue(issue_id="uuid-child", issue_key="CHILD-1")
        root = make_issue(
            issue_id="uuid-root",
            issue_key="ROOT-1",
            relations=[
                RelationData(
                    dimension="child",
                    relation_type="has_child",
                    target_issue_id="uuid-child",
                    target_issue_key="CHILD-1",
                ),
            ],
        )
        fake_gateway.add_issue(root)
        fake_gateway.add_issue(child)

        syncer = make_syncer(context_dir=context_dir, gateway=fake_gateway)
        await syncer.sync("ROOT-1")

        # CHILD-1 is currently derived (not a root).
        manifest = load_manifest(context_dir)
        assert "uuid-child" not in manifest.roots
        assert "uuid-child" in manifest.tickets

        await syncer.add("CHILD-1")

        manifest = load_manifest(context_dir)
        assert "uuid-child" in manifest.roots
        assert manifest.roots["uuid-child"].state == "active"

        # Frontmatter should reflect root status.
        fm = _read_ticket_fm(context_dir, "CHILD-1")
        assert fm.get("root_state") == "active"

    async def test_add_not_found_raises(
        self,
        context_dir: Path,
        fake_gateway: FakeLinearGateway,
    ) -> None:
        """Add fails with RootNotFoundError for an unavailable ticket."""
        root = make_issue(issue_id="uuid-root", issue_key="ROOT-1")
        fake_gateway.add_issue(root)

        syncer = make_syncer(context_dir=context_dir, gateway=fake_gateway)
        await syncer.sync("ROOT-1")

        with pytest.raises(RootNotFoundError):
            await syncer.add("NONEXISTENT-99")


# ===========================================================================
# add — by Linear URL
# ===========================================================================


class TestAddByUrl:
    """Add a root by Linear issue URL."""

    async def test_add_by_url_extracts_key(
        self,
        context_dir: Path,
        fake_gateway: FakeLinearGateway,
    ) -> None:
        """URL is parsed to extract the issue key for resolution."""
        root1 = make_issue(issue_id="uuid-root1", issue_key="ROOT-1")
        root2 = make_issue(issue_id="uuid-root2", issue_key="ROOT-2")
        fake_gateway.add_issue(root1)
        fake_gateway.add_issue(root2)

        syncer = make_syncer(context_dir=context_dir, gateway=fake_gateway)
        await syncer.sync("ROOT-1")

        result = await syncer.add("https://linear.app/fake-workspace/issue/ROOT-2")

        manifest = load_manifest(context_dir)
        assert "uuid-root2" in manifest.roots
        assert manifest.roots["uuid-root2"].state == "active"
        assert "ROOT-2" in result.created or "ROOT-2" in result.updated

    async def test_add_by_url_with_title_slug(
        self,
        context_dir: Path,
        fake_gateway: FakeLinearGateway,
    ) -> None:
        """URLs with a trailing title slug are parsed correctly."""
        root1 = make_issue(issue_id="uuid-root1", issue_key="ROOT-1")
        root2 = make_issue(issue_id="uuid-root2", issue_key="ROOT-2")
        fake_gateway.add_issue(root1)
        fake_gateway.add_issue(root2)

        syncer = make_syncer(context_dir=context_dir, gateway=fake_gateway)
        await syncer.sync("ROOT-1")

        await syncer.add("https://linear.app/fake-workspace/issue/ROOT-2/some-title-slug")

        manifest = load_manifest(context_dir)
        assert "uuid-root2" in manifest.roots

    async def test_add_by_url_workspace_mismatch_fails_fast(
        self,
        context_dir: Path,
        fake_gateway: FakeLinearGateway,
    ) -> None:
        """URL whose workspace slug differs from the manifest is rejected."""
        root = make_issue(issue_id="uuid-root", issue_key="ROOT-1")
        fake_gateway.add_issue(root)

        syncer = make_syncer(context_dir=context_dir, gateway=fake_gateway)
        await syncer.sync("ROOT-1")

        with pytest.raises(WorkspaceMismatchError, match="wrong-workspace"):
            await syncer.add("https://linear.app/wrong-workspace/issue/ROOT-2")


# ===========================================================================
# add — overlapping root graphs
# ===========================================================================


class TestAddOverlappingRoots:
    """Whole-snapshot refresh is correct when root graphs overlap."""

    async def test_overlapping_root_shared_ticket_preserved(
        self,
        context_dir: Path,
        fake_gateway: FakeLinearGateway,
    ) -> None:
        """A ticket reachable from both roots stays in the snapshot."""
        shared = make_issue(issue_id="uuid-shared", issue_key="SHARED-1")
        root1 = make_issue(
            issue_id="uuid-root1",
            issue_key="ROOT-1",
            relations=[
                RelationData(
                    dimension="child",
                    relation_type="has_child",
                    target_issue_id="uuid-shared",
                    target_issue_key="SHARED-1",
                ),
            ],
        )
        root2 = make_issue(
            issue_id="uuid-root2",
            issue_key="ROOT-2",
            relations=[
                RelationData(
                    dimension="child",
                    relation_type="has_child",
                    target_issue_id="uuid-shared",
                    target_issue_key="SHARED-1",
                ),
            ],
        )
        fake_gateway.add_issue(root1)
        fake_gateway.add_issue(root2)
        fake_gateway.add_issue(shared)

        syncer = make_syncer(context_dir=context_dir, gateway=fake_gateway)
        await syncer.sync("ROOT-1")

        # Before add: shared ticket exists as derived.
        manifest = load_manifest(context_dir)
        assert "uuid-shared" in manifest.tickets
        assert "uuid-root2" not in manifest.roots

        result = await syncer.add("ROOT-2")
        assert result.errors == []

        # After add: both roots and the shared ticket are present.
        manifest = load_manifest(context_dir)
        assert "uuid-root1" in manifest.roots
        assert "uuid-root2" in manifest.roots
        assert "uuid-shared" in manifest.tickets

        # All three ticket files exist.
        assert (context_dir / "ROOT-1.md").is_file()
        assert (context_dir / "ROOT-2.md").is_file()
        assert (context_dir / "SHARED-1.md").is_file()


# ===========================================================================
# remove_root — basic
# ===========================================================================


class TestRemoveRoot:
    """Basic remove-root flows."""

    async def test_remove_sole_root_prunes_everything(
        self,
        context_dir: Path,
        fake_gateway: FakeLinearGateway,
    ) -> None:
        """Removing the only root prunes its ticket file."""
        child = make_issue(issue_id="uuid-child", issue_key="CHILD-1")
        root = make_issue(
            issue_id="uuid-root",
            issue_key="ROOT-1",
            relations=[
                RelationData(
                    dimension="child",
                    relation_type="has_child",
                    target_issue_id="uuid-child",
                    target_issue_key="CHILD-1",
                ),
            ],
        )
        fake_gateway.add_issue(root)
        fake_gateway.add_issue(child)

        syncer = make_syncer(context_dir=context_dir, gateway=fake_gateway)
        await syncer.sync("ROOT-1")

        assert (context_dir / "ROOT-1.md").is_file()
        assert (context_dir / "CHILD-1.md").is_file()

        result = await syncer.remove_root("ROOT-1")

        # Root and derived child are both pruned.
        assert "ROOT-1" in result.removed
        assert "CHILD-1" in result.removed
        assert not (context_dir / "ROOT-1.md").is_file()
        assert not (context_dir / "CHILD-1.md").is_file()

        manifest = load_manifest(context_dir)
        assert "uuid-root" not in manifest.roots
        assert manifest.snapshot is not None
        assert manifest.snapshot.mode == "remove-root"
        assert manifest.snapshot.completed_successfully is True

    async def test_remove_root_still_reachable_becomes_derived(
        self,
        context_dir: Path,
        fake_gateway: FakeLinearGateway,
    ) -> None:
        """A removed root that is still reachable from another root stays as derived."""
        # ROOT-2 is a child of ROOT-1.
        root2 = make_issue(issue_id="uuid-root2", issue_key="ROOT-2")
        root1 = make_issue(
            issue_id="uuid-root1",
            issue_key="ROOT-1",
            relations=[
                RelationData(
                    dimension="child",
                    relation_type="has_child",
                    target_issue_id="uuid-root2",
                    target_issue_key="ROOT-2",
                ),
            ],
        )
        fake_gateway.add_issue(root1)
        fake_gateway.add_issue(root2)

        syncer = make_syncer(context_dir=context_dir, gateway=fake_gateway)
        await syncer.sync("ROOT-1")
        await syncer.add("ROOT-2")

        # Both are roots now.
        manifest = load_manifest(context_dir)
        assert "uuid-root2" in manifest.roots

        result = await syncer.remove_root("ROOT-2")

        # ROOT-2 is no longer a root but remains tracked (reachable from ROOT-1).
        manifest = load_manifest(context_dir)
        assert "uuid-root2" not in manifest.roots
        assert "uuid-root2" in manifest.tickets
        assert (context_dir / "ROOT-2.md").is_file()
        # ROOT-2 should NOT be in the removed list (still reachable).
        assert "ROOT-2" not in result.removed

    async def test_remove_root_snapshot_mode(
        self,
        context_dir: Path,
        fake_gateway: FakeLinearGateway,
    ) -> None:
        """Snapshot mode is recorded as ``remove-root``."""
        root1 = make_issue(issue_id="uuid-root1", issue_key="ROOT-1")
        root2 = make_issue(issue_id="uuid-root2", issue_key="ROOT-2")
        fake_gateway.add_issue(root1)
        fake_gateway.add_issue(root2)

        syncer = make_syncer(context_dir=context_dir, gateway=fake_gateway)
        await syncer.sync("ROOT-1")
        await syncer.add("ROOT-2")
        await syncer.remove_root("ROOT-2")

        manifest = load_manifest(context_dir)
        assert manifest.snapshot is not None
        assert manifest.snapshot.mode == "remove-root"


# ===========================================================================
# remove_root — error cases
# ===========================================================================


class TestRemoveRootErrors:
    """Error paths for remove_root."""

    async def test_remove_non_root_raises(
        self,
        context_dir: Path,
        fake_gateway: FakeLinearGateway,
    ) -> None:
        """Removing a derived (non-root) ticket raises RootNotInManifestError."""
        child = make_issue(issue_id="uuid-child", issue_key="CHILD-1")
        root = make_issue(
            issue_id="uuid-root",
            issue_key="ROOT-1",
            relations=[
                RelationData(
                    dimension="child",
                    relation_type="has_child",
                    target_issue_id="uuid-child",
                    target_issue_key="CHILD-1",
                ),
            ],
        )
        fake_gateway.add_issue(root)
        fake_gateway.add_issue(child)

        syncer = make_syncer(context_dir=context_dir, gateway=fake_gateway)
        await syncer.sync("ROOT-1")

        with pytest.raises(RootNotInManifestError):
            await syncer.remove_root("CHILD-1")

    async def test_remove_unknown_ticket_raises(
        self,
        context_dir: Path,
        fake_gateway: FakeLinearGateway,
    ) -> None:
        """Removing a ticket that is not in the manifest at all raises."""
        root = make_issue(issue_id="uuid-root", issue_key="ROOT-1")
        fake_gateway.add_issue(root)

        syncer = make_syncer(context_dir=context_dir, gateway=fake_gateway)
        await syncer.sync("ROOT-1")

        with pytest.raises(RootNotInManifestError, match="Cannot resolve"):
            await syncer.remove_root("UNKNOWN-99")

    async def test_remove_root_url_workspace_mismatch(
        self,
        context_dir: Path,
        fake_gateway: FakeLinearGateway,
    ) -> None:
        """URL workspace mismatch is caught before root-set lookup."""
        root = make_issue(issue_id="uuid-root", issue_key="ROOT-1")
        fake_gateway.add_issue(root)

        syncer = make_syncer(context_dir=context_dir, gateway=fake_gateway)
        await syncer.sync("ROOT-1")

        with pytest.raises(WorkspaceMismatchError, match="wrong-ws"):
            await syncer.remove_root("https://linear.app/wrong-ws/issue/ROOT-1")

    async def test_remove_root_no_manifest_raises(
        self,
        context_dir: Path,
        fake_gateway: FakeLinearGateway,
    ) -> None:
        """remove_root on an empty context (no manifest) raises ManifestError."""
        from context_sync._errors import ManifestError

        syncer = make_syncer(context_dir=context_dir, gateway=fake_gateway)

        with pytest.raises(ManifestError):
            await syncer.remove_root("ROOT-1")
