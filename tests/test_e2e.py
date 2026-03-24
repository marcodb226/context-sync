"""
Library pipeline and component tests for all major modes (M4-2).

These tests exercise the library pipeline through private CLI handler functions
(``_run_sync``, ``_run_refresh``, etc.) and directly via ``make_context_sync()`` with
a :class:`FakeLinearGateway`.  They do **not** exercise ``main()``,
``build_parser()``, or the installed console-script entry point — those are
covered by :mod:`test_cli`.

Coverage includes:
- correct exit codes and output (text + JSON) from private handlers,
- INFO- and DEBUG-level logging contract per ADR §6.1,
- idempotent second-run behavior (no rewrites on unchanged upstream),
- operational scenarios (multi-root, quarantine, remove, diff).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from context_sync._cli import (
    DEFAULT_LOG_LEVEL,
    EXIT_SUCCESS,
    _run_diff,
    _run_refresh,
    _run_remove,
    _run_sync,
)
from context_sync._config import Dimension
from context_sync._gateway import RelationData
from context_sync._manifest import load_manifest
from context_sync._testing import FakeLinearGateway, make_context_sync, make_issue

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_args(**overrides: object) -> object:
    """Build a minimal ``argparse.Namespace``-like object for CLI handlers."""
    import argparse

    defaults = {
        "context_dir": ".",
        "ticket": None,
        "max_tickets_per_root": None,
        "missing_root_policy": "quarantine",
        "json": False,
        "log_level": DEFAULT_LOG_LEVEL,
    }
    # Default all depth_* overrides to None.
    for d in Dimension:
        defaults[f"depth_{d.value.replace('-', '_')}"] = None
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# Full-cycle sync → refresh → diff → sync (add root) → remove
# ---------------------------------------------------------------------------


class TestFullCycleE2E:
    """Exercise a complete lifecycle across all four modes."""

    @pytest.fixture()
    def gateway(self) -> FakeLinearGateway:
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="uuid-root",
                issue_key="PROJ-1",
                title="Root",
                relations=[
                    RelationData(
                        relation_type="blocks",
                        dimension="blocks",
                        target_issue_id="uuid-child",
                        target_issue_key="PROJ-2",
                    )
                ],
            )
        )
        gw.add_issue(make_issue(issue_id="uuid-child", issue_key="PROJ-2", title="Child"))
        return gw

    async def test_sync_creates_snapshot(
        self, context_dir: Path, gateway: FakeLinearGateway
    ) -> None:
        """Sync materializes root and child ticket files."""
        args = _make_args(context_dir=str(context_dir), ticket="PROJ-1")
        code = await _run_sync(args, _gateway_override=gateway)
        assert code == EXIT_SUCCESS
        assert (context_dir / "PROJ-1.md").is_file()
        assert (context_dir / "PROJ-2.md").is_file()

        manifest = load_manifest(context_dir)
        assert "uuid-root" in manifest.roots
        assert manifest.snapshot is not None
        assert manifest.snapshot.completed_successfully is True

    async def test_refresh_no_op_on_unchanged(
        self, context_dir: Path, gateway: FakeLinearGateway
    ) -> None:
        """Refresh with unchanged upstream produces no rewrites."""
        # Bootstrap
        args = _make_args(context_dir=str(context_dir), ticket="PROJ-1")
        await _run_sync(args, _gateway_override=gateway)

        # Record mtimes
        root_mtime = (context_dir / "PROJ-1.md").stat().st_mtime_ns
        child_mtime = (context_dir / "PROJ-2.md").stat().st_mtime_ns

        # Refresh
        args = _make_args(context_dir=str(context_dir))
        code = await _run_refresh(args, _gateway_override=gateway)
        assert code == EXIT_SUCCESS

        # No file rewrites
        assert (context_dir / "PROJ-1.md").stat().st_mtime_ns == root_mtime
        assert (context_dir / "PROJ-2.md").stat().st_mtime_ns == child_mtime

    async def test_diff_reports_current(
        self, context_dir: Path, gateway: FakeLinearGateway
    ) -> None:
        """Diff classifies a fresh snapshot as current."""
        # Bootstrap
        args = _make_args(context_dir=str(context_dir), ticket="PROJ-1")
        await _run_sync(args, _gateway_override=gateway)

        # Diff
        args = _make_args(context_dir=str(context_dir), json=True)
        code = await _run_diff(args, _gateway_override=gateway)
        assert code == EXIT_SUCCESS

    async def test_sync_adds_second_root(
        self, context_dir: Path, gateway: FakeLinearGateway
    ) -> None:
        """Sync TICKET introduces a second root and rebuilds the snapshot."""
        gateway.add_issue(make_issue(issue_id="uuid-new", issue_key="PROJ-3", title="New Root"))

        # Bootstrap with first root
        args = _make_args(context_dir=str(context_dir), ticket="PROJ-1")
        await _run_sync(args, _gateway_override=gateway)

        # Add second root via sync
        args = _make_args(context_dir=str(context_dir), ticket="PROJ-3")
        code = await _run_sync(args, _gateway_override=gateway)
        assert code == EXIT_SUCCESS
        assert (context_dir / "PROJ-3.md").is_file()

        manifest = load_manifest(context_dir)
        assert "uuid-new" in manifest.roots

    async def test_remove_prunes(self, context_dir: Path, gateway: FakeLinearGateway) -> None:
        """Remove drops the root and prunes its unreachable children."""
        # Bootstrap
        args = _make_args(context_dir=str(context_dir), ticket="PROJ-1")
        await _run_sync(args, _gateway_override=gateway)
        assert (context_dir / "PROJ-2.md").is_file()

        # Remove the only root
        args = _make_args(context_dir=str(context_dir), ticket="PROJ-1")
        code = await _run_remove(args, _gateway_override=gateway)
        assert code == EXIT_SUCCESS

        manifest = load_manifest(context_dir)
        assert "uuid-root" not in manifest.roots
        # Derived ticket pruned since no roots remain.
        assert not (context_dir / "PROJ-2.md").is_file()


# ---------------------------------------------------------------------------
# Logging contract tests (ADR §6.1)
# ---------------------------------------------------------------------------


class TestLoggingContract:
    """Verify INFO-level logging covers the ADR §6.1 observability contract."""

    @pytest.fixture()
    def gateway(self) -> FakeLinearGateway:
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="LOG-1", title="Root"))
        return gw

    async def test_sync_info_logs(
        self,
        context_dir: Path,
        gateway: FakeLinearGateway,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Sync emits INFO logs for started and completed with counts."""
        ctx = make_context_sync(gateway=gateway, context_dir=context_dir)
        with caplog.at_level(logging.INFO, logger="context_sync"):
            await ctx.sync(key="LOG-1")

        log_text = caplog.text
        assert "sync: started" in log_text
        assert "active_roots=" in log_text
        assert "max_tickets_per_root=" in log_text
        assert "sync: completed" in log_text
        assert "created=" in log_text
        assert "unchanged=" in log_text
        assert "duration=" in log_text
        assert "roots_at_cap=" in log_text

    async def test_refresh_info_logs(
        self,
        context_dir: Path,
        gateway: FakeLinearGateway,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Refresh emits INFO logs for started and completed with counts."""
        ctx = make_context_sync(gateway=gateway, context_dir=context_dir)
        await ctx.sync(key="LOG-1")

        caplog.clear()
        with caplog.at_level(logging.INFO, logger="context_sync"):
            await ctx.refresh()

        log_text = caplog.text
        assert "started" in log_text
        assert "active_roots=" in log_text
        assert "max_tickets_per_root=" in log_text
        assert "completed" in log_text
        assert "roots_at_cap=" in log_text
        assert "duration=" in log_text

    async def test_diff_info_logs(
        self,
        context_dir: Path,
        gateway: FakeLinearGateway,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Diff emits INFO logs for started and completed with counts."""
        ctx = make_context_sync(gateway=gateway, context_dir=context_dir)
        await ctx.sync(key="LOG-1")

        caplog.clear()
        with caplog.at_level(logging.INFO, logger="context_sync"):
            await ctx.diff()

        log_text = caplog.text
        assert "diff: started" in log_text
        assert "tracked_tickets=" in log_text
        assert "diff: completed" in log_text
        assert "duration=" in log_text

    async def test_refresh_debug_stale_fresh(
        self,
        context_dir: Path,
        gateway: FakeLinearGateway,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Refresh emits DEBUG logs for per-ticket fresh/stale decisions."""
        ctx = make_context_sync(gateway=gateway, context_dir=context_dir)
        await ctx.sync(key="LOG-1")

        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="context_sync"):
            await ctx.refresh()

        log_text = caplog.text
        # Ticket should be fresh (unchanged upstream).
        assert "refresh: fresh" in log_text

    async def test_lock_debug_acquired(
        self,
        context_dir: Path,
        gateway: FakeLinearGateway,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Lock acquisition emits a DEBUG log."""
        ctx = make_context_sync(gateway=gateway, context_dir=context_dir)

        with caplog.at_level(logging.DEBUG, logger="context_sync"):
            await ctx.sync(key="LOG-1")

        log_text = caplog.text
        assert "Lock acquired cleanly" in log_text


# ---------------------------------------------------------------------------
# JSON output end-to-end
# ---------------------------------------------------------------------------


class TestJsonOutputE2E:
    """Verify JSON output mode produces valid, parseable payloads."""

    @pytest.fixture()
    def gateway(self) -> FakeLinearGateway:
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-1", issue_key="JSON-1", title="Root"))
        return gw

    async def test_sync_json_output(
        self,
        context_dir: Path,
        gateway: FakeLinearGateway,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Sync with --json produces valid JSON on stdout."""
        args = _make_args(context_dir=str(context_dir), ticket="JSON-1", json=True)
        code = await _run_sync(args, _gateway_override=gateway)
        assert code == EXIT_SUCCESS

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "created" in data
        assert "JSON-1" in data["created"]

    async def test_diff_json_output(
        self,
        context_dir: Path,
        gateway: FakeLinearGateway,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Diff with --json produces valid JSON on stdout."""
        ctx = make_context_sync(gateway=gateway, context_dir=context_dir)
        await ctx.sync(key="JSON-1")

        args = _make_args(context_dir=str(context_dir), json=True)
        code = await _run_diff(args, _gateway_override=gateway)
        assert code == EXIT_SUCCESS

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "entries" in data


# ---------------------------------------------------------------------------
# Multi-root and quarantine scenarios
# ---------------------------------------------------------------------------


class TestMultiRootE2E:
    """Exercise multi-root and quarantine scenarios end to end."""

    async def test_overlapping_root_graphs(self, context_dir: Path) -> None:
        """Two roots sharing a child produce one copy of the child."""
        gw = FakeLinearGateway()
        shared_rel = RelationData(
            relation_type="blocks",
            dimension="blocks",
            target_issue_id="uuid-c",
            target_issue_key="MR-C",
        )
        gw.add_issue(
            make_issue(issue_id="uuid-a", issue_key="MR-A", title="Root A", relations=[shared_rel])
        )
        gw.add_issue(
            make_issue(issue_id="uuid-b", issue_key="MR-B", title="Root B", relations=[shared_rel])
        )
        gw.add_issue(make_issue(issue_id="uuid-c", issue_key="MR-C", title="Shared"))

        # Sync root A
        args = _make_args(context_dir=str(context_dir), ticket="MR-A")
        await _run_sync(args, _gateway_override=gw)

        # Add root B via sync
        args = _make_args(context_dir=str(context_dir), ticket="MR-B")
        code = await _run_sync(args, _gateway_override=gw)
        assert code == EXIT_SUCCESS

        manifest = load_manifest(context_dir)
        assert "uuid-a" in manifest.roots
        assert "uuid-b" in manifest.roots
        # Shared child exists once
        assert (context_dir / "MR-C.md").is_file()
        assert "uuid-c" in manifest.tickets

    async def test_quarantine_and_recovery(self, context_dir: Path) -> None:
        """A root that disappears is quarantined and recovered on return."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-q", issue_key="QR-1", title="Unstable"))

        # Sync
        ctx = make_context_sync(gateway=gw, context_dir=context_dir)
        await ctx.sync(key="QR-1")

        # Make root invisible
        gw.hide_issue("uuid-q")

        # Refresh — root should be quarantined
        await ctx.refresh(missing_root_policy="quarantine")
        manifest = load_manifest(context_dir)
        assert manifest.roots["uuid-q"].state == "quarantined"

        # Restore visibility
        gw.unhide_issue("uuid-q")

        # Refresh again — root should recover
        await ctx.refresh(missing_root_policy="quarantine")
        manifest = load_manifest(context_dir)
        assert manifest.roots["uuid-q"].state == "active"


# ---------------------------------------------------------------------------
# Idempotency verification (ADR §8)
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Verify that repeated runs against unchanged upstream produce no churn."""

    async def test_sync_twice_no_rewrite(self, context_dir: Path) -> None:
        """Running sync twice with no upstream changes produces unchanged."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-idem", issue_key="IDEM-1"))

        ctx = make_context_sync(gateway=gw, context_dir=context_dir)
        r1 = await ctx.sync(key="IDEM-1")
        assert "IDEM-1" in r1.created

        r2 = await ctx.sync(key="IDEM-1")
        assert "IDEM-1" in r2.unchanged
        assert len(r2.created) == 0
        assert len(r2.updated) == 0

    async def test_refresh_unchanged_no_rewrite(self, context_dir: Path) -> None:
        """Refresh with no upstream changes produces zero local churn."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uuid-ref", issue_key="REF-1"))

        ctx = make_context_sync(gateway=gw, context_dir=context_dir)
        await ctx.sync(key="REF-1")

        result = await ctx.refresh()
        assert "REF-1" in result.unchanged
        assert len(result.created) == 0
        assert len(result.updated) == 0
