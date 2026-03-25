"""
Sync workflow example — demonstrates the primary ContextSync operations.

This script exercises the four public ``ContextSync`` methods (``sync``,
``refresh``, ``remove``, ``diff``) against a ``FakeLinearGateway`` so it
can run without Linear credentials or network access.

Prerequisites
-------------
- Python 3.13+
- ``context-sync`` installed (``pip install -e ".[dev]"``)

Usage
-----
Run from the repository root with the virtualenv active::

    python examples/sync_workflow.py

The script creates a temporary directory, runs a complete sync/refresh/
diff/remove cycle, and prints the results to stdout.

.. note::

   This example uses the ``_gateway_override`` testing hook because the
   real ``linear-client``-backed gateway is not yet available. Once M5-1
   lands the real gateway, this script will be updated to use the
   standard ``ContextSync(linear=...)`` constructor.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from context_sync import ContextSync, DiffResult, IssueId, IssueKey, RelationData, SyncResult, Timestamp
from context_sync._testing import FakeLinearGateway, make_issue


def _print_sync_result(label: str, result: SyncResult) -> None:
    """Print a human-readable summary of a SyncResult."""
    print(f"\n--- {label} ---")
    print(f"  created:   {result.created}")
    print(f"  updated:   {result.updated}")
    print(f"  unchanged: {result.unchanged}")
    print(f"  removed:   {result.removed}")
    if result.errors:
        print(f"  errors:    {[e.ticket_key for e in result.errors]}")


def _print_diff_result(result: DiffResult) -> None:
    """Print a human-readable summary of a DiffResult."""
    print("\n--- diff ---")
    for entry in result.entries:
        print(f"  {entry.ticket_key}: {entry.status}")
    if result.errors:
        print(f"  errors: {[e.ticket_key for e in result.errors]}")


async def main() -> None:
    """Run a complete sync/refresh/diff/remove cycle."""
    # -- Set up a fake gateway with a small ticket graph -------------------
    gateway = FakeLinearGateway()

    root = make_issue(
        issue_id=IssueId("aaaaaaaa-0000-0000-0000-000000000001"),
        issue_key=IssueKey("DEMO-1"),
        title="Root ticket for the sync demo",
        description="This is the root of a small example graph.",
        created_at=Timestamp("2026-01-15T10:00:00Z"),
        updated_at=Timestamp("2026-01-15T12:00:00Z"),
        relations=[
            RelationData(
                dimension="child",
                relation_type="child",
                target_issue_id=IssueId("aaaaaaaa-0000-0000-0000-000000000002"),
                target_issue_key=IssueKey("DEMO-2"),
            ),
        ],
    )
    child = make_issue(
        issue_id=IssueId("aaaaaaaa-0000-0000-0000-000000000002"),
        issue_key=IssueKey("DEMO-2"),
        title="Child ticket discovered via relation",
        description="Linked from the root ticket.",
        parent_issue_id=IssueId("aaaaaaaa-0000-0000-0000-000000000001"),
        parent_issue_key=IssueKey("DEMO-1"),
        created_at=Timestamp("2026-01-15T10:30:00Z"),
        updated_at=Timestamp("2026-01-15T11:00:00Z"),
        relations=[
            RelationData(
                dimension="parent",
                relation_type="parent",
                target_issue_id=IssueId("aaaaaaaa-0000-0000-0000-000000000001"),
                target_issue_key=IssueKey("DEMO-1"),
            ),
        ],
    )

    gateway.add_issue(root)
    gateway.add_issue(child)

    # -- Run the workflow in a temporary directory -------------------------
    with tempfile.TemporaryDirectory(prefix="context-sync-example-") as tmpdir:
        context_dir = Path(tmpdir) / "context"
        context_dir.mkdir()

        # The _gateway_override hook is temporary; the real constructor
        # will be ContextSync(linear=linear_client, context_dir=...) once
        # M5-1 lands the real gateway.
        ctx = ContextSync(
            context_dir=context_dir,
            _gateway_override=gateway,
        )

        # 1. Initial sync — adds DEMO-1 as a root and discovers DEMO-2.
        result = await ctx.sync(key="DEMO-1")
        _print_sync_result("sync DEMO-1", result)

        # 2. Refresh — re-fetches all tracked tickets incrementally.
        result = await ctx.refresh()
        _print_sync_result("refresh", result)

        # 3. Diff — compares local snapshot to the (fake) remote state.
        diff = await ctx.diff()
        _print_diff_result(diff)

        # 4. Remove — stops tracking DEMO-1 and prunes orphaned tickets.
        result = await ctx.remove(key="DEMO-1")
        _print_sync_result("remove DEMO-1", result)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
