"""Tests for manifest schema, initialization, and round-trip I/O."""

from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from context_sync._config import FORMAT_VERSION
from context_sync._errors import ManifestError
from context_sync._gateway import WorkspaceIdentity
from context_sync._manifest import (
    MANIFEST_FILENAME,
    Manifest,
    ManifestRootEntry,
    ManifestSnapshot,
    ManifestTicketEntry,
    initialize_manifest,
    load_manifest,
    save_manifest,
)
from context_sync._testing import DEFAULT_FAKE_WORKSPACE, make_manifest

# ---------------------------------------------------------------------------
# Pydantic model contracts
# ---------------------------------------------------------------------------


class TestManifestModels:
    def test_root_entry_active(self) -> None:
        entry = ManifestRootEntry(state="active")
        assert entry.state == "active"
        assert entry.quarantined_reason is None

    def test_root_entry_quarantined(self) -> None:
        entry = ManifestRootEntry(
            state="quarantined",
            quarantined_reason="not_available_in_visible_view",
        )
        assert entry.state == "quarantined"
        assert entry.quarantined_reason == "not_available_in_visible_view"

    def test_root_entry_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            ManifestRootEntry(state="active", bogus="x")  # type: ignore[call-arg]

    def test_ticket_entry_fields(self) -> None:
        entry = ManifestTicketEntry(current_key="ACP-123", current_path="tickets/ACP-123.md")
        assert entry.current_key == "ACP-123"
        assert entry.current_path == "tickets/ACP-123.md"

    def test_ticket_entry_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            ManifestTicketEntry(  # type: ignore[call-arg]
                current_key="X-1",
                current_path="p.md",
                stale=True,
            )

    def test_snapshot_required_fields(self) -> None:
        snap = ManifestSnapshot(mode="sync", started_at="2026-01-01T00:00:00Z")
        assert snap.mode == "sync"
        assert snap.started_at == "2026-01-01T00:00:00Z"
        assert snap.completed_at is None
        assert snap.completed_successfully is None

    def test_snapshot_all_fields(self) -> None:
        snap = ManifestSnapshot(
            mode="refresh",
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:01:00Z",
            completed_successfully=True,
        )
        assert snap.completed_at == "2026-01-01T00:01:00Z"
        assert snap.completed_successfully is True

    def test_snapshot_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            ManifestSnapshot(  # type: ignore[call-arg]
                mode="sync",
                started_at="2026-01-01T00:00:00Z",
                extra_field="bad",
            )

    def test_manifest_defaults(self) -> None:
        m = Manifest(
            format_version=FORMAT_VERSION,
            workspace_id="ws-1",
            workspace_slug="slug",
            dimensions={"blocks": 3},
            max_tickets_per_root=200,
        )
        assert m.roots == {}
        assert m.tickets == {}
        assert m.aliases == {}
        assert m.snapshot is None

    def test_manifest_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            Manifest(  # type: ignore[call-arg]
                format_version=FORMAT_VERSION,
                workspace_id="ws-1",
                workspace_slug="slug",
                dimensions={},
                max_tickets_per_root=200,
                unknown_key="oops",
            )


# ---------------------------------------------------------------------------
# initialize_manifest
# ---------------------------------------------------------------------------


class TestInitializeManifest:
    def test_format_version(self) -> None:
        m = initialize_manifest(
            workspace=DEFAULT_FAKE_WORKSPACE,
            dimensions={"blocks": 3},
            max_tickets_per_root=100,
        )
        assert m.format_version == FORMAT_VERSION

    def test_workspace_identity(self) -> None:
        ws = WorkspaceIdentity(workspace_id="ws-abc", workspace_slug="my-team")
        m = initialize_manifest(workspace=ws, dimensions={}, max_tickets_per_root=50)
        assert m.workspace_id == "ws-abc"
        assert m.workspace_slug == "my-team"

    def test_dimensions_and_cap(self) -> None:
        dims = {"blocks": 5, "parent": 1}
        m = initialize_manifest(
            workspace=DEFAULT_FAKE_WORKSPACE,
            dimensions=dims,
            max_tickets_per_root=42,
        )
        assert m.dimensions == dims
        assert m.max_tickets_per_root == 42

    def test_collections_start_empty(self) -> None:
        m = initialize_manifest(
            workspace=DEFAULT_FAKE_WORKSPACE,
            dimensions={},
            max_tickets_per_root=200,
        )
        assert m.roots == {}
        assert m.tickets == {}
        assert m.aliases == {}
        assert m.snapshot is None


# ---------------------------------------------------------------------------
# save / load round-trip
# ---------------------------------------------------------------------------


class TestSaveAndLoadManifest:
    def test_round_trip(self, tmp_path: object) -> None:
        from pathlib import Path

        ctx = Path(str(tmp_path))
        original = make_manifest()
        save_manifest(original, ctx)
        loaded = load_manifest(ctx)
        assert loaded == original

    def test_yaml_keys_are_sorted(self, tmp_path: object) -> None:
        from pathlib import Path

        ctx = Path(str(tmp_path))
        save_manifest(make_manifest(), ctx)
        text = (ctx / MANIFEST_FILENAME).read_text(encoding="utf-8")
        keys = [line.split(":")[0] for line in text.splitlines() if not line.startswith(" ")]
        assert keys == sorted(keys)

    def test_empty_collections_omitted(self, tmp_path: object) -> None:
        from pathlib import Path

        ctx = Path(str(tmp_path))
        m = make_manifest()
        # Defaults have empty roots, tickets, aliases and no snapshot.
        save_manifest(m, ctx)
        text = (ctx / MANIFEST_FILENAME).read_text(encoding="utf-8")
        assert "roots:" not in text
        assert "tickets:" not in text
        assert "aliases:" not in text
        assert "snapshot:" not in text

    def test_load_missing_file_raises(self, tmp_path: object) -> None:
        from pathlib import Path

        ctx = Path(str(tmp_path))
        with pytest.raises(ManifestError, match="not found"):
            load_manifest(ctx)

    def test_load_corrupt_yaml_raises(self, tmp_path: object) -> None:
        from pathlib import Path

        ctx = Path(str(tmp_path))
        (ctx / MANIFEST_FILENAME).write_text("{{bad yaml", encoding="utf-8")
        with pytest.raises(ManifestError, match="[Mm]alformed|[Mm]apping"):
            load_manifest(ctx)

    def test_load_non_mapping_raises(self, tmp_path: object) -> None:
        from pathlib import Path

        ctx = Path(str(tmp_path))
        (ctx / MANIFEST_FILENAME).write_text("- just\n- a\n- list\n", encoding="utf-8")
        with pytest.raises(ManifestError, match="mapping"):
            load_manifest(ctx)

    def test_load_wrong_format_version_raises(self, tmp_path: object) -> None:
        from pathlib import Path

        ctx = Path(str(tmp_path))
        m = make_manifest()
        save_manifest(m, ctx)
        # Patch the format_version in the file on disk.
        path = ctx / MANIFEST_FILENAME
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        raw["format_version"] = 9999
        path.write_text(
            yaml.safe_dump(raw, sort_keys=True, default_flow_style=False),
            encoding="utf-8",
        )
        with pytest.raises(ManifestError, match="format_version"):
            load_manifest(ctx)


# ---------------------------------------------------------------------------
# Manifest with populated data
# ---------------------------------------------------------------------------


class TestManifestWithData:
    def test_manifest_with_roots_and_tickets(self, tmp_path: object) -> None:
        from pathlib import Path

        ctx = Path(str(tmp_path))
        m = make_manifest()
        m = m.model_copy(
            update={
                "roots": {
                    "uuid-1": ManifestRootEntry(state="active"),
                    "uuid-2": ManifestRootEntry(
                        state="quarantined",
                        quarantined_reason="not_available_in_visible_view",
                    ),
                },
                "tickets": {
                    "uuid-1": ManifestTicketEntry(
                        current_key="ACP-1",
                        current_path="tickets/ACP-1.md",
                    ),
                },
                "aliases": {"OLD-1": "ACP-1"},
            },
        )
        save_manifest(m, ctx)
        loaded = load_manifest(ctx)
        assert loaded.roots["uuid-1"].state == "active"
        assert loaded.roots["uuid-2"].state == "quarantined"
        assert loaded.roots["uuid-2"].quarantined_reason == "not_available_in_visible_view"
        assert loaded.tickets["uuid-1"].current_key == "ACP-1"
        assert loaded.aliases["OLD-1"] == "ACP-1"

    def test_manifest_with_snapshot(self, tmp_path: object) -> None:
        from pathlib import Path

        ctx = Path(str(tmp_path))
        snap = ManifestSnapshot(
            mode="sync",
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:01:00Z",
            completed_successfully=True,
        )
        m = make_manifest(snapshot=snap)
        save_manifest(m, ctx)
        loaded = load_manifest(ctx)
        assert loaded.snapshot is not None
        assert loaded.snapshot.mode == "sync"
        assert loaded.snapshot.started_at == "2026-01-01T00:00:00Z"
        assert loaded.snapshot.completed_at == "2026-01-01T00:01:00Z"
        assert loaded.snapshot.completed_successfully is True

    def test_snapshot_without_completion(self, tmp_path: object) -> None:
        from pathlib import Path

        ctx = Path(str(tmp_path))
        snap = ManifestSnapshot(mode="add", started_at="2026-03-01T12:00:00Z")
        m = make_manifest(snapshot=snap)
        save_manifest(m, ctx)
        loaded = load_manifest(ctx)
        assert loaded.snapshot is not None
        assert loaded.snapshot.completed_at is None
        assert loaded.snapshot.completed_successfully is None
