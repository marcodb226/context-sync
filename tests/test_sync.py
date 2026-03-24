"""
Tests for the ContextSync class and the full-snapshot sync flow.

Constructor, property, and gateway-override tests are retained from M1-1.
Integration tests for the ``sync`` method (M2-3) exercise the full flow:
lock acquisition, manifest bootstrap, workspace validation, traversal,
ticket-file writing, derived-ticket pruning, and manifest finalization.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from context_sync._config import DEFAULT_DIMENSIONS
from context_sync._errors import (
    ContextSyncError,
    RootNotFoundError,
    WorkspaceMismatchError,
)
from context_sync._gateway import RelationData, WorkspaceIdentity
from context_sync._lock import LOCK_FILENAME
from context_sync._manifest import load_manifest
from context_sync._testing import (
    DEFAULT_FAKE_WORKSPACE,
    FakeLinearGateway,
    make_context_sync,
    make_issue,
)

# ---------------------------------------------------------------------------
# Constructor and property tests (retained from M1-1)
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    """ContextSync rejects invalid constructor arguments."""

    def test_requires_linear_or_gateway(self) -> None:
        from context_sync._sync import ContextSync

        with pytest.raises(ContextSyncError, match="linear.*gateway"):
            ContextSync(context_dir=Path("/tmp"))

    def test_negative_max_tickets(self) -> None:
        with pytest.raises(ValueError, match="max_tickets_per_root"):
            make_context_sync(max_tickets_per_root=0)

    def test_negative_concurrency(self) -> None:
        with pytest.raises(ValueError, match="concurrency_limit"):
            make_context_sync(concurrency_limit=0)

    def test_invalid_dimension(self) -> None:
        with pytest.raises(ValueError, match="Unknown dimension"):
            make_context_sync(dimensions={"not_real": 1})

    def test_negative_dimension_depth(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            make_context_sync(dimensions={"blocks": -1})


class TestProperties:
    """Public properties reflect constructor arguments."""

    def test_default_dimensions(self) -> None:
        ctx = make_context_sync()
        assert ctx.dimensions == DEFAULT_DIMENSIONS

    def test_custom_dimensions(self) -> None:
        ctx = make_context_sync(dimensions={"blocks": 5})
        assert ctx.dimensions["blocks"] == 5
        assert ctx.dimensions["relates_to"] == 1

    def test_context_dir(self, tmp_path: Path) -> None:
        ctx = make_context_sync(context_dir=tmp_path / "ctx")
        assert ctx.context_dir == tmp_path / "ctx"

    def test_max_tickets_per_root(self) -> None:
        ctx = make_context_sync(max_tickets_per_root=50)
        assert ctx.max_tickets_per_root == 50

    def test_concurrency_limit(self) -> None:
        ctx = make_context_sync(concurrency_limit=5)
        assert ctx.concurrency_limit == 5

    def test_dimensions_returns_copy(self) -> None:
        ctx = make_context_sync()
        d1 = ctx.dimensions
        d2 = ctx.dimensions
        assert d1 is not d2


class TestGatewayOverride:
    """The _gateway_override testing hook works correctly."""

    def test_fake_gateway_accepted(self) -> None:
        gw = FakeLinearGateway()
        ctx = make_context_sync(gateway=gw)
        assert ctx is not None

    async def test_fake_gateway_reachable(self) -> None:
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_key="FAKE-1"))
        ctx = make_context_sync(gateway=gw)
        bundle = await ctx._gateway.fetch_issue("FAKE-1")
        assert bundle.issue.issue_key == "FAKE-1"


# ---------------------------------------------------------------------------
# Sync integration tests (M2-3)
# ---------------------------------------------------------------------------


class TestSyncInitial:
    """Initial sync creates context directory, manifest, and ticket files."""

    async def test_single_root_no_relations(self, tmp_path: Path) -> None:
        """Sync a lone root ticket with no relations."""
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="uuid-root",
                issue_key="PROJ-1",
                title="Root ticket",
            )
        )
        ctx = make_context_sync(gateway=gw, context_dir=tmp_path / "ctx")

        result = await ctx.sync("PROJ-1")

        assert result.created == ["PROJ-1"]
        assert result.updated == []
        assert result.removed == []
        assert result.errors == []

        # Ticket file exists.
        ticket_file = tmp_path / "ctx" / "PROJ-1.md"
        assert ticket_file.is_file()
        content = ticket_file.read_text(encoding="utf-8")
        assert "Root ticket" in content

        # Manifest is valid and records the root.
        manifest = load_manifest(tmp_path / "ctx")
        assert "uuid-root" in manifest.roots
        assert manifest.roots["uuid-root"].state == "active"
        assert manifest.workspace_id == DEFAULT_FAKE_WORKSPACE.workspace_id
        assert manifest.snapshot is not None
        assert manifest.snapshot.mode == "sync"
        assert manifest.snapshot.completed_successfully is True

    async def test_root_with_relations(self, tmp_path: Path) -> None:
        """Sync a root that has Tier 1 relations — derived tickets are created."""
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="uuid-root",
                issue_key="PROJ-1",
                title="Root",
                relations=[
                    RelationData(
                        dimension="blocks",
                        relation_type="blocks",
                        target_issue_id="uuid-child",
                        target_issue_key="PROJ-2",
                    ),
                ],
            )
        )
        gw.add_issue(
            make_issue(
                issue_id="uuid-child",
                issue_key="PROJ-2",
                title="Child ticket",
            )
        )
        ctx = make_context_sync(gateway=gw, context_dir=tmp_path / "ctx")

        result = await ctx.sync("PROJ-1")

        assert sorted(result.created) == ["PROJ-1", "PROJ-2"]
        assert result.updated == []
        assert result.removed == []

        # Both files exist.
        assert (tmp_path / "ctx" / "PROJ-1.md").is_file()
        assert (tmp_path / "ctx" / "PROJ-2.md").is_file()

        # Manifest tracks both tickets.
        manifest = load_manifest(tmp_path / "ctx")
        assert "uuid-root" in manifest.tickets
        assert "uuid-child" in manifest.tickets
        # Only the root is in the root set.
        assert "uuid-root" in manifest.roots
        assert "uuid-child" not in manifest.roots

    async def test_creates_context_dir(self, tmp_path: Path) -> None:
        """Sync creates the context directory if it does not exist."""
        context_dir = tmp_path / "nonexistent" / "ctx"
        assert not context_dir.exists()

        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-r", issue_key="NEW-1"))
        ctx = make_context_sync(gateway=gw, context_dir=context_dir)

        result = await ctx.sync("NEW-1")

        assert result.created == ["NEW-1"]
        assert context_dir.is_dir()
        assert (context_dir / "NEW-1.md").is_file()

    async def test_root_frontmatter_marks_root_state(self, tmp_path: Path) -> None:
        """Root ticket file includes ``root: true`` and ``root_state: active``."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-r", issue_key="R-1"))
        ctx = make_context_sync(gateway=gw, context_dir=tmp_path / "ctx")

        await ctx.sync("R-1")

        content = (tmp_path / "ctx" / "R-1.md").read_text(encoding="utf-8")
        # Extract frontmatter between --- markers.
        parts = content.split("---", maxsplit=2)
        fm = yaml.safe_load(parts[1])
        assert fm["root"] is True
        assert fm["root_state"] == "active"

    async def test_derived_frontmatter_no_root_state(self, tmp_path: Path) -> None:
        """Derived ticket file has ``root: false`` and no ``root_state``."""
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="uuid-root",
                issue_key="R-1",
                relations=[
                    RelationData(
                        dimension="blocks",
                        relation_type="blocks",
                        target_issue_id="uuid-d",
                        target_issue_key="D-1",
                    )
                ],
            )
        )
        gw.add_issue(make_issue(issue_id="uuid-d", issue_key="D-1"))
        ctx = make_context_sync(gateway=gw, context_dir=tmp_path / "ctx")

        await ctx.sync("R-1")

        content = (tmp_path / "ctx" / "D-1.md").read_text(encoding="utf-8")
        parts = content.split("---", maxsplit=2)
        fm = yaml.safe_load(parts[1])
        assert fm["root"] is False
        assert "root_state" not in fm


class TestSyncIdempotency:
    """Repeated sync without upstream changes produces stable output."""

    async def test_second_sync_reports_unchanged_when_no_upstream_change(
        self, tmp_path: Path
    ) -> None:
        """Running sync twice with no upstream change classifies tickets as unchanged."""
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="uuid-r",
                issue_key="R-1",
                relations=[
                    RelationData(
                        dimension="blocks",
                        relation_type="blocks",
                        target_issue_id="uuid-d",
                        target_issue_key="D-1",
                    )
                ],
            )
        )
        gw.add_issue(make_issue(issue_id="uuid-d", issue_key="D-1"))
        ctx = make_context_sync(gateway=gw, context_dir=tmp_path / "ctx")

        first = await ctx.sync("R-1")
        assert sorted(first.created) == ["D-1", "R-1"]
        assert first.updated == []

        second = await ctx.sync("R-1")
        assert second.created == []
        assert second.updated == []
        assert sorted(second.unchanged) == ["D-1", "R-1"]
        assert second.removed == []

    async def test_ticket_content_stable_across_syncs(self, tmp_path: Path) -> None:
        """Non-timestamp frontmatter fields are stable across syncs."""
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="uuid-r",
                issue_key="STABLE-1",
                title="Stable title",
                description="Stable description.",
            )
        )
        ctx = make_context_sync(gateway=gw, context_dir=tmp_path / "ctx")

        await ctx.sync("STABLE-1")
        first_content = (tmp_path / "ctx" / "STABLE-1.md").read_text(encoding="utf-8")

        await ctx.sync("STABLE-1")
        second_content = (tmp_path / "ctx" / "STABLE-1.md").read_text(encoding="utf-8")

        # Extract frontmatter and compare non-timestamp fields.
        def extract_stable_fm(text: str) -> dict:
            parts = text.split("---", maxsplit=2)
            fm = yaml.safe_load(parts[1])
            # Remove timestamp fields that naturally advance.
            fm.pop("last_synced_at", None)
            fm.pop("refresh_cursor", None)
            return fm

        assert extract_stable_fm(first_content) == extract_stable_fm(second_content)

        # Body sections (description + comments) should be identical.
        def extract_body(text: str) -> str:
            parts = text.split("---", maxsplit=2)
            return parts[2]

        assert extract_body(first_content) == extract_body(second_content)


class TestSyncWorkspaceValidation:
    """Sync validates workspace identity before mutating the directory."""

    async def test_workspace_mismatch_raises(self, tmp_path: Path) -> None:
        """Adding a root from workspace B to a directory bound to workspace A."""
        ctx = tmp_path / "ctx"

        # First sync binds the directory to workspace A.
        gw_a = FakeLinearGateway()
        gw_a.add_issue(
            make_issue(
                issue_id="uuid-a",
                issue_key="A-1",
                workspace=DEFAULT_FAKE_WORKSPACE,
            )
        )
        ctx_a = make_context_sync(gateway=gw_a, context_dir=ctx)
        await ctx_a.sync("A-1")

        # Attempt sync with a ticket from workspace B.
        other_ws = WorkspaceIdentity(
            workspace_id="ws-other-99999",
            workspace_slug="other-workspace",
        )
        gw_b = FakeLinearGateway()
        gw_b.add_issue(
            make_issue(
                issue_id="uuid-b",
                issue_key="B-1",
                workspace=other_ws,
            )
        )
        ctx_b = make_context_sync(gateway=gw_b, context_dir=ctx)

        with pytest.raises(WorkspaceMismatchError, match="other-workspace"):
            await ctx_b.sync("B-1")

    async def test_root_not_found_raises(self, tmp_path: Path) -> None:
        """Sync with a non-existent root ticket raises RootNotFoundError."""
        gw = FakeLinearGateway()
        ctx = make_context_sync(gateway=gw, context_dir=tmp_path / "ctx")

        with pytest.raises(RootNotFoundError):
            await ctx.sync("MISSING-1")


class TestSyncPruning:
    """Derived tickets are pruned when they fall out of the reachable graph."""

    async def test_derived_ticket_pruned_when_relation_removed(
        self,
        tmp_path: Path,
    ) -> None:
        """Removing a relation causes the formerly derived ticket to be pruned."""
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="uuid-root",
                issue_key="ROOT-1",
                relations=[
                    RelationData(
                        dimension="blocks",
                        relation_type="blocks",
                        target_issue_id="uuid-derived",
                        target_issue_key="DER-1",
                    )
                ],
            )
        )
        gw.add_issue(make_issue(issue_id="uuid-derived", issue_key="DER-1"))
        ctx = make_context_sync(gateway=gw, context_dir=tmp_path / "ctx")

        first = await ctx.sync("ROOT-1")
        assert sorted(first.created) == ["DER-1", "ROOT-1"]
        assert (tmp_path / "ctx" / "DER-1.md").is_file()

        # Remove the relation so DER-1 is no longer reachable.
        gw.add_issue(
            make_issue(
                issue_id="uuid-root",
                issue_key="ROOT-1",
                relations=[],
            )
        )

        second = await ctx.sync("ROOT-1")
        assert second.removed == ["DER-1"]
        assert not (tmp_path / "ctx" / "DER-1.md").exists()
        assert (tmp_path / "ctx" / "ROOT-1.md").is_file()

        # Manifest no longer tracks the derived ticket.
        manifest = load_manifest(tmp_path / "ctx")
        assert "uuid-derived" not in manifest.tickets
        assert "uuid-root" in manifest.tickets

    async def test_root_tickets_never_pruned(self, tmp_path: Path) -> None:
        """Root tickets are retained even if they have no outgoing relations."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-r1", issue_key="R-1"))
        ctx = make_context_sync(gateway=gw, context_dir=tmp_path / "ctx")

        result = await ctx.sync("R-1")
        assert result.created == ["R-1"]

        # Re-sync — root should remain, not be pruned.
        result2 = await ctx.sync("R-1")
        assert result2.unchanged == ["R-1"]
        assert result2.removed == []


class TestSyncMultiRoot:
    """Sync with multiple roots produces a unified snapshot."""

    async def test_add_second_root_expands_snapshot(self, tmp_path: Path) -> None:
        """Syncing a second root into an existing directory adds its neighborhood."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-r1", issue_key="R-1"))
        gw.add_issue(
            make_issue(
                issue_id="uuid-r2",
                issue_key="R-2",
                relations=[
                    RelationData(
                        dimension="child",
                        relation_type="child",
                        target_issue_id="uuid-c1",
                        target_issue_key="C-1",
                    )
                ],
            )
        )
        gw.add_issue(make_issue(issue_id="uuid-c1", issue_key="C-1"))
        ctx = make_context_sync(gateway=gw, context_dir=tmp_path / "ctx")

        # First sync with R-1 only.
        first = await ctx.sync("R-1")
        assert first.created == ["R-1"]

        # Second sync adds R-2 and its child; R-1 is unchanged.
        second = await ctx.sync("R-2")
        assert sorted(second.created) == ["C-1", "R-2"]
        assert second.updated == []
        assert second.unchanged == ["R-1"]

        # Manifest has both roots.
        manifest = load_manifest(tmp_path / "ctx")
        assert "uuid-r1" in manifest.roots
        assert "uuid-r2" in manifest.roots
        assert len(manifest.tickets) == 3


class TestSyncLockBehavior:
    """Writer lock is acquired and released correctly."""

    async def test_lock_released_after_success(self, tmp_path: Path) -> None:
        """Lock file is removed after a successful sync."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-r", issue_key="L-1"))
        context_dir = tmp_path / "ctx"
        ctx = make_context_sync(gateway=gw, context_dir=context_dir)

        await ctx.sync("L-1")

        assert not (context_dir / LOCK_FILENAME).exists()

    async def test_lock_released_after_failure(self, tmp_path: Path) -> None:
        """Lock file is removed even when sync fails."""
        gw = FakeLinearGateway()
        context_dir = tmp_path / "ctx"
        ctx = make_context_sync(gateway=gw, context_dir=context_dir)

        with pytest.raises(RootNotFoundError):
            await ctx.sync("MISSING-1")

        assert not (context_dir / LOCK_FILENAME).exists()


class TestSyncManifestConfig:
    """Manifest records the traversal configuration used by the sync pass."""

    async def test_per_call_dimension_overrides_saved(self, tmp_path: Path) -> None:
        """Per-call dimension overrides are persisted in the manifest."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-r", issue_key="CFG-1"))
        ctx = make_context_sync(gateway=gw, context_dir=tmp_path / "ctx")

        await ctx.sync("CFG-1", dimensions={"blocks": 5})

        manifest = load_manifest(tmp_path / "ctx")
        assert manifest.dimensions["blocks"] == 5
        # Non-overridden dimensions retain defaults.
        assert manifest.dimensions["relates_to"] == 1

    async def test_per_call_cap_override_saved(self, tmp_path: Path) -> None:
        """Per-call max_tickets_per_root override is persisted in the manifest."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-r", issue_key="CAP-1"))
        ctx = make_context_sync(gateway=gw, context_dir=tmp_path / "ctx")

        await ctx.sync("CAP-1", max_tickets_per_root=42)

        manifest = load_manifest(tmp_path / "ctx")
        assert manifest.max_tickets_per_root == 42

    async def test_snapshot_metadata_recorded(self, tmp_path: Path) -> None:
        """Manifest snapshot metadata is populated after sync."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-r", issue_key="SNP-1"))
        ctx = make_context_sync(gateway=gw, context_dir=tmp_path / "ctx")

        await ctx.sync("SNP-1")

        manifest = load_manifest(tmp_path / "ctx")
        assert manifest.snapshot is not None
        assert manifest.snapshot.mode == "sync"
        assert manifest.snapshot.started_at is not None
        assert manifest.snapshot.completed_at is not None
        assert manifest.snapshot.completed_successfully is True


class TestSyncIssueKeyRename:
    """Sync handles issue-key renames detected during the write pass."""

    async def test_issue_key_rename_updates_file_and_alias(
        self,
        tmp_path: Path,
    ) -> None:
        """
        When a ticket's key changes between syncs, the file is renamed
        and the old key is recorded as an alias in the manifest.
        """
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="uuid-r",
                issue_key="OLD-1",
                title="Rename me",
            )
        )
        context_dir = tmp_path / "ctx"
        ctx = make_context_sync(gateway=gw, context_dir=context_dir)

        await ctx.sync("OLD-1")
        assert (context_dir / "OLD-1.md").is_file()

        # Simulate an issue-key rename upstream.
        gw.add_issue(
            make_issue(
                issue_id="uuid-r",
                issue_key="NEW-1",
                title="Rename me",
            )
        )
        # Also update the key index so the gateway can resolve the old key.
        gw._key_index["OLD-1"] = "uuid-r"

        result = await ctx.sync("uuid-r")
        assert result.updated == ["NEW-1"]
        assert not (context_dir / "OLD-1.md").exists()
        assert (context_dir / "NEW-1.md").is_file()

        manifest = load_manifest(context_dir)
        assert manifest.aliases.get("OLD-1") == "uuid-r"
        assert manifest.tickets["uuid-r"].current_key == "NEW-1"


class TestSyncTicketRefTier3:
    """Tier 3 ticket_ref edges are discovered from root content."""

    async def test_ticket_ref_in_root_description_discovered(
        self,
        tmp_path: Path,
    ) -> None:
        """A Linear URL in the root description adds the referenced ticket."""
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="uuid-root",
                issue_key="REF-1",
                description="See https://linear.app/fake-workspace/issue/REF-2 for details.",
            )
        )
        gw.add_issue(
            make_issue(
                issue_id="uuid-ref",
                issue_key="REF-2",
                title="Referenced ticket",
            )
        )
        ctx = make_context_sync(gateway=gw, context_dir=tmp_path / "ctx")

        result = await ctx.sync("REF-1")

        assert sorted(result.created) == ["REF-1", "REF-2"]
        assert (tmp_path / "ctx" / "REF-2.md").is_file()


# ---------------------------------------------------------------------------
# Review-finding regression tests (M2-3 Phase C)
# ---------------------------------------------------------------------------


class TestSyncLinkedTicketFetchFailure:
    """R1: linked-ticket fetch failure records an error instead of aborting."""

    async def test_linked_ticket_unavailable_records_error(
        self,
        tmp_path: Path,
    ) -> None:
        """A linked ticket that is unreachable produces a SyncError, not an abort."""
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="uuid-root",
                issue_key="ROOT-1",
                title="Root ticket",
                relations=[
                    RelationData(
                        dimension="blocks",
                        relation_type="blocks",
                        target_issue_id="uuid-linked",
                        target_issue_key="LINKED-1",
                    ),
                ],
            )
        )
        # Add the linked ticket so traversal discovers it, then hide it
        # so the post-traversal fetch fails.
        gw.add_issue(make_issue(issue_id="uuid-linked", issue_key="LINKED-1"))
        gw.hide_issue("uuid-linked")

        ctx = make_context_sync(gateway=gw, context_dir=tmp_path / "ctx")
        result = await ctx.sync("ROOT-1")

        # Root was written successfully.
        assert result.created == ["ROOT-1"]
        assert (tmp_path / "ctx" / "ROOT-1.md").is_file()

        # Linked ticket failure recorded as an error, not an exception.
        assert len(result.errors) == 1
        assert result.errors[0].ticket_key == "LINKED-1"
        assert result.errors[0].error_type == "fetch_failed"
        assert result.errors[0].retriable is True

        # No file was written for the failed ticket.
        assert not (tmp_path / "ctx" / "LINKED-1.md").exists()


class TestSyncGatewayReadiness:
    """R2: ContextSync(linear=...) fails fast when gateway is not wired."""

    async def test_linear_constructor_raises_on_sync(self) -> None:
        """Calling sync() through the linear= constructor path raises immediately."""
        from context_sync._sync import ContextSync

        ctx = ContextSync(linear=object(), context_dir="/tmp/ctx-r2-test")
        with pytest.raises(ContextSyncError, match="No gateway available"):
            await ctx.sync("ANY-1")


class TestSyncExistingRootPrefetchFailure:
    """R3: existing root unavailable during pre-fetch does not abort sync."""

    async def test_hidden_existing_root_excluded_from_traversal(
        self,
        tmp_path: Path,
    ) -> None:
        """When an existing root is hidden, sync completes for the healthy root."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-r1", issue_key="R-1"))
        gw.add_issue(make_issue(issue_id="uuid-r2", issue_key="R-2"))
        context_dir = tmp_path / "ctx"
        ctx = make_context_sync(gateway=gw, context_dir=context_dir)

        # First sync: both roots healthy.
        await ctx.sync("R-1")
        await ctx.sync("R-2")
        manifest = load_manifest(context_dir)
        assert "uuid-r1" in manifest.roots
        assert "uuid-r2" in manifest.roots

        # Hide R-1 and re-sync via R-2.
        gw.hide_issue("uuid-r1")
        result = await ctx.sync("R-2")

        # R-2 was processed successfully (unchanged since no upstream change).
        assert result.errors == []
        assert (context_dir / "R-2.md").is_file()


class TestSyncWriteAvoidance:
    """R4: files are not rewritten when upstream content is unchanged."""

    async def test_file_mtime_stable_when_unchanged(self, tmp_path: Path) -> None:
        """File modification time does not advance on a no-change re-sync."""
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="uuid-r",
                issue_key="IDLE-1",
                title="Idle ticket",
            )
        )
        context_dir = tmp_path / "ctx"
        ctx = make_context_sync(gateway=gw, context_dir=context_dir)

        await ctx.sync("IDLE-1")
        first_mtime = (context_dir / "IDLE-1.md").stat().st_mtime

        result = await ctx.sync("IDLE-1")
        second_mtime = (context_dir / "IDLE-1.md").stat().st_mtime

        assert result.unchanged == ["IDLE-1"]
        assert result.updated == []
        assert first_mtime == second_mtime

    async def test_upstream_change_triggers_rewrite(self, tmp_path: Path) -> None:
        """A ticket whose upstream content changed is classified as updated."""
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="uuid-r",
                issue_key="UPD-1",
                title="Original title",
                updated_at="2026-01-01T00:00:00Z",
            )
        )
        context_dir = tmp_path / "ctx"
        ctx = make_context_sync(gateway=gw, context_dir=context_dir)

        first = await ctx.sync("UPD-1")
        assert first.created == ["UPD-1"]

        # Simulate upstream update.
        gw.add_issue(
            make_issue(
                issue_id="uuid-r",
                issue_key="UPD-1",
                title="Updated title",
                updated_at="2026-01-02T00:00:00Z",
            )
        )

        second = await ctx.sync("UPD-1")
        assert second.updated == ["UPD-1"]
        assert second.unchanged == []

        content = (context_dir / "UPD-1.md").read_text(encoding="utf-8")
        assert "Updated title" in content
