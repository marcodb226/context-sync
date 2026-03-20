"""
Tests for the reachable graph builder and tiered per-root traversal engine.

Covers the plan-required scenarios for M2-1: per-root caps, tier priority,
shortest-depth resolution, cycle safety, and multi-root overlap — plus
dimension disabling, max-depth constraints, ticket_ref injection, and
cap-reporting accuracy.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from context_sync._config import DEFAULT_DIMENSIONS, Dimension
from context_sync._gateway import RelationData
from context_sync._testing import FakeLinearGateway, make_issue
from context_sync._traversal import (
    TraversalResult,
    TraversedTicket,
    build_reachable_graph,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rel(
    dimension: str,
    target_id: str,
    target_key: str,
    relation_type: str | None = None,
) -> RelationData:
    """Build a :class:`RelationData` with a default ``relation_type``."""
    return RelationData(
        dimension=dimension,
        relation_type=relation_type or dimension,
        target_issue_id=target_id,
        target_issue_key=target_key,
    )


async def _no_refs(issue_ids: Sequence[str]) -> dict[str, list[tuple[str, str]]]:
    """Ticket-ref provider that always returns nothing."""
    return {}


# ---------------------------------------------------------------------------
# Empty and trivial cases
# ---------------------------------------------------------------------------


class TestEmptyAndTrivial:
    async def test_empty_roots_returns_empty_result(self) -> None:
        gw = FakeLinearGateway()
        result = await build_reachable_graph(
            roots={},
            dimensions=DEFAULT_DIMENSIONS,
            max_tickets_per_root=200,
            gateway=gw,
        )
        assert result.per_root_tickets == {}
        assert result.tickets == {}
        assert result.roots_at_cap == frozenset()

    async def test_single_root_no_relations(self) -> None:
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="r1", issue_key="T-1"))

        result = await build_reachable_graph(
            roots={"r1": "T-1"},
            dimensions=DEFAULT_DIMENSIONS,
            max_tickets_per_root=200,
            gateway=gw,
        )

        assert result.per_root_tickets == {"r1": frozenset({"r1"})}
        assert set(result.tickets) == {"r1"}
        assert result.tickets["r1"] == TraversedTicket(
            issue_id="r1",
            issue_key="T-1",
            effective_depth=0,
            root_ids=frozenset({"r1"}),
        )
        assert result.roots_at_cap == frozenset()

    async def test_single_root_tier1_edge_discovered(self) -> None:
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="r1",
                issue_key="T-1",
                relations=[_rel("blocks", "d1", "T-2")],
            )
        )
        gw.add_issue(make_issue(issue_id="d1", issue_key="T-2"))

        result = await build_reachable_graph(
            roots={"r1": "T-1"},
            dimensions=DEFAULT_DIMENSIONS,
            max_tickets_per_root=200,
            gateway=gw,
        )

        assert result.per_root_tickets["r1"] == frozenset({"r1", "d1"})
        assert result.tickets["d1"].effective_depth == 1
        assert result.tickets["d1"].root_ids == frozenset({"r1"})
        assert result.roots_at_cap == frozenset()


# ---------------------------------------------------------------------------
# Per-root cap enforcement
# ---------------------------------------------------------------------------


class TestPerRootCap:
    async def test_cap_limits_derived_tickets(self) -> None:
        # Root has 3 Tier 1 edges; cap=2 allows root + 1 derived only.
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="r1",
                issue_key="T-1",
                relations=[
                    _rel("blocks", "d1", "T-2"),
                    _rel("blocks", "d2", "T-3"),
                    _rel("blocks", "d3", "T-4"),
                ],
            )
        )

        result = await build_reachable_graph(
            roots={"r1": "T-1"},
            dimensions=DEFAULT_DIMENSIONS,
            max_tickets_per_root=2,
            gateway=gw,
        )

        assert "r1" in result.per_root_tickets["r1"]
        assert len(result.per_root_tickets["r1"]) == 2
        assert "r1" in result.roots_at_cap

    async def test_cap_of_one_keeps_only_root(self) -> None:
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="r1",
                issue_key="T-1",
                relations=[_rel("blocks", "d1", "T-2")],
            )
        )

        result = await build_reachable_graph(
            roots={"r1": "T-1"},
            dimensions=DEFAULT_DIMENSIONS,
            max_tickets_per_root=1,
            gateway=gw,
        )

        assert result.per_root_tickets["r1"] == frozenset({"r1"})
        assert "r1" in result.roots_at_cap

    async def test_no_cap_hit_when_graph_fits(self) -> None:
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="r1",
                issue_key="T-1",
                relations=[_rel("blocks", "d1", "T-2")],
            )
        )
        gw.add_issue(make_issue(issue_id="d1", issue_key="T-2"))

        result = await build_reachable_graph(
            roots={"r1": "T-1"},
            dimensions=DEFAULT_DIMENSIONS,
            max_tickets_per_root=200,
            gateway=gw,
        )

        assert result.roots_at_cap == frozenset()
        assert "d1" in result.per_root_tickets["r1"]


# ---------------------------------------------------------------------------
# Tier priority
# ---------------------------------------------------------------------------


class TestTierPriority:
    async def test_tier1_beats_tier2_at_cap(self) -> None:
        # Root has one Tier 1 (blocks→d1) and one Tier 2 (relates_to→d2).
        # Cap=2 allows only one derived ticket; Tier 1 must win.
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="r1",
                issue_key="T-1",
                relations=[
                    _rel("blocks", "d1", "T-2"),
                    _rel("relates_to", "d2", "T-3"),
                ],
            )
        )

        result = await build_reachable_graph(
            roots={"r1": "T-1"},
            dimensions=DEFAULT_DIMENSIONS,
            max_tickets_per_root=2,
            gateway=gw,
        )

        assert "d1" in result.per_root_tickets["r1"]
        assert "d2" not in result.per_root_tickets["r1"]
        assert "r1" in result.roots_at_cap

    async def test_tier2_beats_ticket_ref_at_cap(self) -> None:
        # Root has one Tier 2 (relates_to→d2) and one Tier 3 via ticket_ref_fn.
        # Cap=2 allows only one derived ticket; Tier 2 must win.
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="r1",
                issue_key="T-1",
                relations=[_rel("relates_to", "d2", "T-2")],
            )
        )

        async def fake_refs(
            issue_ids: Sequence[str],
        ) -> dict[str, list[tuple[str, str]]]:
            return {"r1": [("d3", "T-3")]}

        result = await build_reachable_graph(
            roots={"r1": "T-1"},
            dimensions=DEFAULT_DIMENSIONS,
            max_tickets_per_root=2,
            gateway=gw,
            ticket_ref_fn=fake_refs,
        )

        assert "d2" in result.per_root_tickets["r1"]
        assert "d3" not in result.per_root_tickets["r1"]
        assert "r1" in result.roots_at_cap

    async def test_all_tiers_included_when_cap_not_hit(self) -> None:
        # When cap is not a constraint, all three tiers contribute.
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="r1",
                issue_key="T-1",
                relations=[
                    _rel("blocks", "d1", "T-2"),
                    _rel("relates_to", "d2", "T-3"),
                ],
            )
        )

        async def fake_refs(
            issue_ids: Sequence[str],
        ) -> dict[str, list[tuple[str, str]]]:
            return {"r1": [("d3", "T-4")]}

        result = await build_reachable_graph(
            roots={"r1": "T-1"},
            dimensions=DEFAULT_DIMENSIONS,
            max_tickets_per_root=200,
            gateway=gw,
            ticket_ref_fn=fake_refs,
        )

        assert {"r1", "d1", "d2", "d3"} == result.per_root_tickets["r1"]
        assert result.roots_at_cap == frozenset()


# ---------------------------------------------------------------------------
# Shortest-depth resolution and multi-root overlap
# ---------------------------------------------------------------------------


class TestMultiRoot:
    async def test_ticket_in_multiple_roots(self) -> None:
        # Root A and Root B both reach ticket C at depth 1.
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="a1",
                issue_key="T-A",
                relations=[_rel("blocks", "c1", "T-C")],
            )
        )
        gw.add_issue(
            make_issue(
                issue_id="b1",
                issue_key="T-B",
                relations=[_rel("blocks", "c1", "T-C")],
            )
        )
        gw.add_issue(make_issue(issue_id="c1", issue_key="T-C"))

        result = await build_reachable_graph(
            roots={"a1": "T-A", "b1": "T-B"},
            dimensions=DEFAULT_DIMENSIONS,
            max_tickets_per_root=200,
            gateway=gw,
        )

        assert "c1" in result.per_root_tickets["a1"]
        assert "c1" in result.per_root_tickets["b1"]
        assert "c1" in result.tickets
        assert result.tickets["c1"].root_ids == frozenset({"a1", "b1"})
        assert result.tickets["c1"].effective_depth == 1

    async def test_shortest_depth_resolution(self) -> None:
        # Root A reaches X at depth 2 (A→B→X); Root B reaches X at depth 1
        # (B→X).  Effective depth of X must be 1.
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="a1",
                issue_key="T-A",
                relations=[_rel("blocks", "b1", "T-B")],
            )
        )
        gw.add_issue(
            make_issue(
                issue_id="b1",
                issue_key="T-B",
                relations=[_rel("blocks", "x1", "T-X")],
            )
        )
        gw.add_issue(make_issue(issue_id="x1", issue_key="T-X"))

        result = await build_reachable_graph(
            roots={"a1": "T-A", "b1": "T-B"},
            dimensions=DEFAULT_DIMENSIONS,
            max_tickets_per_root=200,
            gateway=gw,
        )

        assert result.tickets["x1"].effective_depth == 1
        assert result.tickets["x1"].root_ids == frozenset({"a1", "b1"})

    async def test_per_root_sets_are_independent(self) -> None:
        # Root A can reach d1 but Root B cannot.  Per-root sets must differ.
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="a1",
                issue_key="T-A",
                relations=[_rel("blocks", "d1", "T-D")],
            )
        )
        gw.add_issue(make_issue(issue_id="b1", issue_key="T-B"))
        gw.add_issue(make_issue(issue_id="d1", issue_key="T-D"))

        result = await build_reachable_graph(
            roots={"a1": "T-A", "b1": "T-B"},
            dimensions=DEFAULT_DIMENSIONS,
            max_tickets_per_root=200,
            gateway=gw,
        )

        assert "d1" in result.per_root_tickets["a1"]
        assert "d1" not in result.per_root_tickets["b1"]
        assert result.tickets["d1"].root_ids == frozenset({"a1"})


# ---------------------------------------------------------------------------
# Cycle safety
# ---------------------------------------------------------------------------


class TestCycleSafety:
    async def test_direct_cycle(self) -> None:
        # A→B→A: both tickets should appear exactly once; no infinite loop.
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="a1",
                issue_key="T-A",
                relations=[_rel("blocks", "b1", "T-B")],
            )
        )
        gw.add_issue(
            make_issue(
                issue_id="b1",
                issue_key="T-B",
                relations=[_rel("blocks", "a1", "T-A")],
            )
        )

        result = await build_reachable_graph(
            roots={"a1": "T-A"},
            dimensions=DEFAULT_DIMENSIONS,
            max_tickets_per_root=200,
            gateway=gw,
        )

        assert set(result.tickets) == {"a1", "b1"}
        assert result.tickets["a1"].effective_depth == 0
        assert result.tickets["b1"].effective_depth == 1

    async def test_self_loop(self) -> None:
        # A→A: traversal must terminate; only A in result.
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="a1",
                issue_key="T-A",
                relations=[_rel("blocks", "a1", "T-A")],
            )
        )

        result = await build_reachable_graph(
            roots={"a1": "T-A"},
            dimensions=DEFAULT_DIMENSIONS,
            max_tickets_per_root=200,
            gateway=gw,
        )

        assert set(result.tickets) == {"a1"}
        assert result.tickets["a1"].effective_depth == 0


# ---------------------------------------------------------------------------
# Dimension configuration
# ---------------------------------------------------------------------------


class TestDimensionConfig:
    async def test_disabled_dimension_not_followed(self) -> None:
        # relates_to=0 means the dimension is disabled.
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="r1",
                issue_key="T-1",
                relations=[_rel("relates_to", "d1", "T-2")],
            )
        )

        dims = dict(DEFAULT_DIMENSIONS)
        dims[Dimension.RELATES_TO] = 0

        result = await build_reachable_graph(
            roots={"r1": "T-1"},
            dimensions=dims,
            max_tickets_per_root=200,
            gateway=gw,
        )

        assert "d1" not in result.tickets
        assert result.per_root_tickets["r1"] == frozenset({"r1"})

    async def test_depth_boundary_not_followed_at_exact_depth(self) -> None:
        # relates_to=1 means follow from depth-0 tickets only.
        # r1 (depth 0) →relates_to→ a1 (depth 1) →relates_to→ b1 (depth 2).
        # b1 must not be discovered because a1 is at depth 1 and 1 > 1 is False.
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="r1",
                issue_key="T-1",
                relations=[_rel("relates_to", "a1", "T-A")],
            )
        )
        gw.add_issue(
            make_issue(
                issue_id="a1",
                issue_key="T-A",
                relations=[_rel("relates_to", "b1", "T-B")],
            )
        )
        gw.add_issue(make_issue(issue_id="b1", issue_key="T-B"))

        result = await build_reachable_graph(
            roots={"r1": "T-1"},
            dimensions=DEFAULT_DIMENSIONS,  # relates_to=1
            max_tickets_per_root=200,
            gateway=gw,
        )

        assert "a1" in result.tickets
        assert result.tickets["a1"].effective_depth == 1
        assert "b1" not in result.tickets

    async def test_multi_hop_traversal_within_depth(self) -> None:
        # blocks=3 allows A→B (depth 1)→C (depth 2)→D (depth 3).
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="r1",
                issue_key="T-1",
                relations=[_rel("blocks", "b1", "T-B")],
            )
        )
        gw.add_issue(
            make_issue(
                issue_id="b1",
                issue_key="T-B",
                relations=[_rel("blocks", "c1", "T-C")],
            )
        )
        gw.add_issue(
            make_issue(
                issue_id="c1",
                issue_key="T-C",
                relations=[_rel("blocks", "d1", "T-D")],
            )
        )
        gw.add_issue(make_issue(issue_id="d1", issue_key="T-D"))

        result = await build_reachable_graph(
            roots={"r1": "T-1"},
            dimensions=DEFAULT_DIMENSIONS,  # blocks=3
            max_tickets_per_root=200,
            gateway=gw,
        )

        assert result.tickets["r1"].effective_depth == 0
        assert result.tickets["b1"].effective_depth == 1
        assert result.tickets["c1"].effective_depth == 2
        assert result.tickets["d1"].effective_depth == 3

    async def test_depth_4_not_reached_with_default_blocks(self) -> None:
        # Default blocks=3; depth-3 ticket's blocks edges must not be followed.
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="r1",
                issue_key="T-1",
                relations=[_rel("blocks", "b1", "T-B")],
            )
        )
        gw.add_issue(
            make_issue(
                issue_id="b1",
                issue_key="T-B",
                relations=[_rel("blocks", "c1", "T-C")],
            )
        )
        gw.add_issue(
            make_issue(
                issue_id="c1",
                issue_key="T-C",
                relations=[_rel("blocks", "d1", "T-D")],
            )
        )
        gw.add_issue(
            make_issue(
                issue_id="d1",
                issue_key="T-D",
                relations=[_rel("blocks", "e1", "T-E")],  # depth 4 — must be skipped
            )
        )
        gw.add_issue(make_issue(issue_id="e1", issue_key="T-E"))

        result = await build_reachable_graph(
            roots={"r1": "T-1"},
            dimensions=DEFAULT_DIMENSIONS,  # blocks=3
            max_tickets_per_root=200,
            gateway=gw,
        )

        assert "d1" in result.tickets
        assert "e1" not in result.tickets


# ---------------------------------------------------------------------------
# ticket_ref_fn
# ---------------------------------------------------------------------------


class TestTicketRefFn:
    async def test_ticket_ref_fn_discovers_tier3_edge(self) -> None:
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="r1", issue_key="T-1"))

        async def fake_refs(
            issue_ids: Sequence[str],
        ) -> dict[str, list[tuple[str, str]]]:
            return {"r1": [("d1", "T-2")]}

        result = await build_reachable_graph(
            roots={"r1": "T-1"},
            dimensions=DEFAULT_DIMENSIONS,  # ticket_ref=1
            max_tickets_per_root=200,
            gateway=gw,
            ticket_ref_fn=fake_refs,
        )

        assert "d1" in result.tickets
        assert result.tickets["d1"].effective_depth == 1

    async def test_ticket_ref_fn_none_skips_tier3(self) -> None:
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="r1", issue_key="T-1"))

        result = await build_reachable_graph(
            roots={"r1": "T-1"},
            dimensions=DEFAULT_DIMENSIONS,
            max_tickets_per_root=200,
            gateway=gw,
            ticket_ref_fn=None,
        )

        assert set(result.tickets) == {"r1"}

    async def test_ticket_ref_depth_boundary(self) -> None:
        # ticket_ref=1 means ticket_ref edges are only followed from depth-0.
        # r1 (depth 0) → d1 (depth 1 via tier1).
        # d1 (depth 1): ticket_ref=1, so 1 > 1 is False — refs from d1 not followed.
        gw = FakeLinearGateway()
        gw.add_issue(
            make_issue(
                issue_id="r1",
                issue_key="T-1",
                relations=[_rel("blocks", "d1", "T-D")],
            )
        )
        gw.add_issue(make_issue(issue_id="d1", issue_key="T-D"))

        call_log: list[list[str]] = []

        async def tracking_refs(
            issue_ids: Sequence[str],
        ) -> dict[str, list[tuple[str, str]]]:
            call_log.append(list(issue_ids))
            # Return a ref from d1 — but this should not be followed.
            return {"d1": [("e1", "T-E")]}

        result = await build_reachable_graph(
            roots={"r1": "T-1"},
            dimensions=DEFAULT_DIMENSIONS,  # ticket_ref=1
            max_tickets_per_root=200,
            gateway=gw,
            ticket_ref_fn=tracking_refs,
        )

        # Only r1 (depth 0) should trigger ticket_ref expansion.
        for call in call_log:
            assert "d1" not in call or "e1" not in result.tickets

        assert "e1" not in result.tickets


# ---------------------------------------------------------------------------
# Result type contracts
# ---------------------------------------------------------------------------


class TestResultTypes:
    def test_traversed_ticket_frozen(self) -> None:
        t = TraversedTicket(
            issue_id="a1",
            issue_key="T-A",
            effective_depth=2,
            root_ids=frozenset({"r1"}),
        )
        with pytest.raises(AttributeError):
            t.effective_depth = 99  # type: ignore[misc]

    def test_traversal_result_frozen(self) -> None:
        r = TraversalResult(
            per_root_tickets={},
            tickets={},
            roots_at_cap=frozenset(),
        )
        with pytest.raises(AttributeError):
            r.roots_at_cap = frozenset({"x"})  # type: ignore[misc]
