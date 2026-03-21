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
    make_issue,
    make_syncer,
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
            make_syncer(max_tickets_per_root=0)

    def test_negative_concurrency(self) -> None:
        with pytest.raises(ValueError, match="concurrency_limit"):
            make_syncer(concurrency_limit=0)

    def test_invalid_dimension(self) -> None:
        with pytest.raises(ValueError, match="Unknown dimension"):
            make_syncer(dimensions={"not_real": 1})

    def test_negative_dimension_depth(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            make_syncer(dimensions={"blocks": -1})


class TestProperties:
    """Public properties reflect constructor arguments."""

    def test_default_dimensions(self) -> None:
        syncer = make_syncer()
        assert syncer.dimensions == DEFAULT_DIMENSIONS

    def test_custom_dimensions(self) -> None:
        syncer = make_syncer(dimensions={"blocks": 5})
        assert syncer.dimensions["blocks"] == 5
        assert syncer.dimensions["relates_to"] == 1

    def test_context_dir(self, tmp_path: Path) -> None:
        syncer = make_syncer(context_dir=tmp_path / "ctx")
        assert syncer.context_dir == tmp_path / "ctx"

    def test_max_tickets_per_root(self) -> None:
        syncer = make_syncer(max_tickets_per_root=50)
        assert syncer.max_tickets_per_root == 50

    def test_concurrency_limit(self) -> None:
        syncer = make_syncer(concurrency_limit=5)
        assert syncer.concurrency_limit == 5

    def test_dimensions_returns_copy(self) -> None:
        syncer = make_syncer()
        d1 = syncer.dimensions
        d2 = syncer.dimensions
        assert d1 is not d2


class TestAsyncStubs:
    """Stub entry points raise NotImplementedError until implemented."""

    async def test_refresh_stub(self) -> None:
        syncer = make_syncer()
        with pytest.raises(NotImplementedError):
            await syncer.refresh()

    async def test_add_stub(self) -> None:
        syncer = make_syncer()
        with pytest.raises(NotImplementedError):
            await syncer.add("NEW-1")

    async def test_remove_root_stub(self) -> None:
        syncer = make_syncer()
        with pytest.raises(NotImplementedError):
            await syncer.remove_root("OLD-1")

    async def test_diff_stub(self) -> None:
        syncer = make_syncer()
        with pytest.raises(NotImplementedError):
            await syncer.diff()


class TestGatewayOverride:
    """The _gateway_override testing hook works correctly."""

    def test_fake_gateway_accepted(self) -> None:
        gw = FakeLinearGateway()
        syncer = make_syncer(gateway=gw)
        assert syncer is not None

    async def test_fake_gateway_reachable(self) -> None:
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_key="FAKE-1"))
        syncer = make_syncer(gateway=gw)
        bundle = await syncer._gateway.fetch_issue("FAKE-1")
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
        syncer = make_syncer(gateway=gw, context_dir=tmp_path / "ctx")

        result = await syncer.sync("PROJ-1")

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
        syncer = make_syncer(gateway=gw, context_dir=tmp_path / "ctx")

        result = await syncer.sync("PROJ-1")

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
        ctx = tmp_path / "nonexistent" / "ctx"
        assert not ctx.exists()

        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-r", issue_key="NEW-1"))
        syncer = make_syncer(gateway=gw, context_dir=ctx)

        result = await syncer.sync("NEW-1")

        assert result.created == ["NEW-1"]
        assert ctx.is_dir()
        assert (ctx / "NEW-1.md").is_file()

    async def test_root_frontmatter_marks_root_state(self, tmp_path: Path) -> None:
        """Root ticket file includes ``root: true`` and ``root_state: active``."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-r", issue_key="R-1"))
        syncer = make_syncer(gateway=gw, context_dir=tmp_path / "ctx")

        await syncer.sync("R-1")

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
        syncer = make_syncer(gateway=gw, context_dir=tmp_path / "ctx")

        await syncer.sync("R-1")

        content = (tmp_path / "ctx" / "D-1.md").read_text(encoding="utf-8")
        parts = content.split("---", maxsplit=2)
        fm = yaml.safe_load(parts[1])
        assert fm["root"] is False
        assert "root_state" not in fm


class TestSyncIdempotency:
    """Repeated sync without upstream changes produces stable output."""

    async def test_second_sync_reports_updated_not_created(self, tmp_path: Path) -> None:
        """Running sync twice classifies all tickets as updated on the second run."""
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
        syncer = make_syncer(gateway=gw, context_dir=tmp_path / "ctx")

        first = await syncer.sync("R-1")
        assert sorted(first.created) == ["D-1", "R-1"]
        assert first.updated == []

        second = await syncer.sync("R-1")
        assert second.created == []
        assert sorted(second.updated) == ["D-1", "R-1"]
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
        syncer = make_syncer(gateway=gw, context_dir=tmp_path / "ctx")

        await syncer.sync("STABLE-1")
        first_content = (tmp_path / "ctx" / "STABLE-1.md").read_text(encoding="utf-8")

        await syncer.sync("STABLE-1")
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
        syncer_a = make_syncer(gateway=gw_a, context_dir=ctx)
        await syncer_a.sync("A-1")

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
        syncer_b = make_syncer(gateway=gw_b, context_dir=ctx)

        with pytest.raises(WorkspaceMismatchError, match="other-workspace"):
            await syncer_b.sync("B-1")

    async def test_root_not_found_raises(self, tmp_path: Path) -> None:
        """Sync with a non-existent root ticket raises RootNotFoundError."""
        gw = FakeLinearGateway()
        syncer = make_syncer(gateway=gw, context_dir=tmp_path / "ctx")

        with pytest.raises(RootNotFoundError):
            await syncer.sync("MISSING-1")


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
        syncer = make_syncer(gateway=gw, context_dir=tmp_path / "ctx")

        first = await syncer.sync("ROOT-1")
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

        second = await syncer.sync("ROOT-1")
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
        syncer = make_syncer(gateway=gw, context_dir=tmp_path / "ctx")

        result = await syncer.sync("R-1")
        assert result.created == ["R-1"]

        # Re-sync — root should remain, not be pruned.
        result2 = await syncer.sync("R-1")
        assert result2.updated == ["R-1"]
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
        syncer = make_syncer(gateway=gw, context_dir=tmp_path / "ctx")

        # First sync with R-1 only.
        first = await syncer.sync("R-1")
        assert first.created == ["R-1"]

        # Second sync adds R-2 and its child.
        second = await syncer.sync("R-2")
        assert sorted(second.created) == ["C-1", "R-2"]
        assert second.updated == ["R-1"]

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
        ctx = tmp_path / "ctx"
        syncer = make_syncer(gateway=gw, context_dir=ctx)

        await syncer.sync("L-1")

        assert not (ctx / LOCK_FILENAME).exists()

    async def test_lock_released_after_failure(self, tmp_path: Path) -> None:
        """Lock file is removed even when sync fails."""
        gw = FakeLinearGateway()
        ctx = tmp_path / "ctx"
        syncer = make_syncer(gateway=gw, context_dir=ctx)

        with pytest.raises(RootNotFoundError):
            await syncer.sync("MISSING-1")

        assert not (ctx / LOCK_FILENAME).exists()


class TestSyncManifestConfig:
    """Manifest records the traversal configuration used by the sync pass."""

    async def test_per_call_dimension_overrides_saved(self, tmp_path: Path) -> None:
        """Per-call dimension overrides are persisted in the manifest."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-r", issue_key="CFG-1"))
        syncer = make_syncer(gateway=gw, context_dir=tmp_path / "ctx")

        await syncer.sync("CFG-1", dimensions={"blocks": 5})

        manifest = load_manifest(tmp_path / "ctx")
        assert manifest.dimensions["blocks"] == 5
        # Non-overridden dimensions retain defaults.
        assert manifest.dimensions["relates_to"] == 1

    async def test_per_call_cap_override_saved(self, tmp_path: Path) -> None:
        """Per-call max_tickets_per_root override is persisted in the manifest."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-r", issue_key="CAP-1"))
        syncer = make_syncer(gateway=gw, context_dir=tmp_path / "ctx")

        await syncer.sync("CAP-1", max_tickets_per_root=42)

        manifest = load_manifest(tmp_path / "ctx")
        assert manifest.max_tickets_per_root == 42

    async def test_snapshot_metadata_recorded(self, tmp_path: Path) -> None:
        """Manifest snapshot metadata is populated after sync."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-r", issue_key="SNP-1"))
        syncer = make_syncer(gateway=gw, context_dir=tmp_path / "ctx")

        await syncer.sync("SNP-1")

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
        ctx = tmp_path / "ctx"
        syncer = make_syncer(gateway=gw, context_dir=ctx)

        await syncer.sync("OLD-1")
        assert (ctx / "OLD-1.md").is_file()

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

        result = await syncer.sync("uuid-r")
        assert result.updated == ["NEW-1"]
        assert not (ctx / "OLD-1.md").exists()
        assert (ctx / "NEW-1.md").is_file()

        manifest = load_manifest(ctx)
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
        syncer = make_syncer(gateway=gw, context_dir=tmp_path / "ctx")

        result = await syncer.sync("REF-1")

        assert sorted(result.created) == ["REF-1", "REF-2"]
        assert (tmp_path / "ctx" / "REF-2.md").is_file()
