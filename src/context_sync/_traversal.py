"""
Reachable graph builder and tiered per-root traversal engine.

Implements the BFS-based traversal described in the ADR (§1.1–§1.3):

- Each root runs an independent bounded BFS; depth is measured from that root.
- Within each depth level, dimension-priority tiers are processed in order
  (Tier 1 → Tier 2 → Tier 3) so structural edges win over informational edges
  when the per-root ticket cap is near.
- Ticket cap enforcement is per-root; a root that hits its cap stops expanding,
  but other roots continue traversing independently.
- Cycle safety is enforced per root via a visited set; a UUID seen once is
  never added again in the same root's BFS.
- Effective depth in the final result is the shortest depth from any root.
- Tier 1 and Tier 2 edges come from the gateway's ``get_ticket_relations``
  method (batch-fetched once per depth level). Tier 3 (``ticket_ref``) edges
  come from an optional caller-provided async function so that the traversal
  engine itself does not need fetched ticket content.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from context_sync._config import TRAVERSAL_TIERS, Dimension
from context_sync._gateway import LinearGateway, RelationData

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

type TicketRefProvider = Callable[
    [Sequence[str]],
    Awaitable[dict[str, list[tuple[str, str]]]],
]
"""
Async provider for Tier 3 (``ticket_ref``) edge discovery.

Receives a sequence of issue UUIDs whose fetched content is available; returns
a mapping from each UUID to the ``(target_issue_id, target_issue_key)`` pairs
discovered in that issue's Linear description or comments.

The sync flow (M2-3) supplies this function once per depth level after fetching
ticket content.  When ``None`` is passed to :func:`build_reachable_graph`,
``ticket_ref`` edges are silently skipped.
"""

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TraversedTicket:
    """
    A single ticket in the reachable graph after traversal completes.

    Attributes
    ----------
    issue_id:
        Stable Linear issue UUID.
    issue_key:
        Human-facing key recorded when this ticket was first encountered
        during traversal.  Stable for the duration of one traversal run;
        may differ from the live key if the ticket was renamed after
        traversal began.
    effective_depth:
        Shortest total hops from any root to this ticket across all roots
        processed in the same :func:`build_reachable_graph` call.
    root_ids:
        Immutable set of root UUIDs that can reach this ticket under the
        active traversal configuration and per-root caps.
    """

    issue_id: str
    issue_key: str
    effective_depth: int
    root_ids: frozenset[str]


@dataclass(frozen=True)
class TraversalResult:
    """
    Result of :func:`build_reachable_graph`.

    Attributes
    ----------
    per_root_tickets:
        Mapping from root UUID to the frozenset of issue UUIDs reachable from
        that root (including the root itself).
    tickets:
        Union of all reachable tickets across every root, keyed by issue UUID.
        Each entry records the shortest effective depth and the complete set of
        root UUIDs that can reach it.
    roots_at_cap:
        Frozenset of root UUIDs that hit the per-root ticket cap during
        traversal.  Lower-priority tiers and deeper depths may have been
        excluded for those roots.
    """

    per_root_tickets: dict[str, frozenset[str]]
    tickets: dict[str, TraversedTicket]
    roots_at_cap: frozenset[str]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _active_dims_for_tier(
    tier: frozenset[str],
    dimensions: dict[str, int],
    current_depth: int,
) -> frozenset[str]:
    """
    Return the subset of *tier* dimensions still eligible at *current_depth*.

    An edge in dimension ``d`` is followed from a ticket at depth ``N``
    only when ``dimensions[d] > N`` (ADR §1.2: total-hops depth model).

    Parameters
    ----------
    tier:
        Full set of dimension names for one traversal tier.
    dimensions:
        Active dimension-depth configuration (dimension → max total hops).
    current_depth:
        Depth of the frontier tickets being expanded.

    Returns
    -------
    frozenset[str]
        Dimension names within *tier* that are active at *current_depth*.
    """
    return frozenset(d for d in tier if dimensions.get(d, 0) > current_depth)


async def _traverse_single_root(
    *,
    root_id: str,
    root_key: str,
    dimensions: dict[str, int],
    max_tickets_per_root: int,
    gateway: LinearGateway,
    ticket_ref_fn: TicketRefProvider | None,
) -> tuple[dict[str, int], dict[str, str], bool]:
    """
    BFS traversal from a single root with tiered cap enforcement.

    At each depth level, tiers are processed in priority order
    (Tier 1 → Tier 2 → Tier 3).  Relation edges (Tier 1 and Tier 2) are
    batch-fetched once per depth level and filtered per tier.  If the
    per-root cap is hit mid-tier, expansion stops immediately for the root
    without processing lower-priority tiers or deeper depths.

    Parameters
    ----------
    root_id:
        Stable issue UUID of the traversal root.
    root_key:
        Human-facing key of the root at traversal time.
    dimensions:
        Active dimension-depth configuration.
    max_tickets_per_root:
        Maximum tickets in this root's reachable set, including the root.
    gateway:
        Gateway used to batch-fetch relation edges (Tier 1 and Tier 2).
    ticket_ref_fn:
        Async provider for Tier 3 edge discovery, or ``None`` to skip
        ``ticket_ref`` expansion.

    Returns
    -------
    tuple[dict[str, int], dict[str, str], bool]
        A 3-tuple of:

        * ``visited_depth`` — issue UUID → depth from this root.
        * ``visited_keys`` — issue UUID → key at first discovery.
        * ``at_cap`` — ``True`` if the per-root cap was reached and at
          least one candidate ticket could not be added.
    """
    # Depth from this root for each visited issue UUID.
    visited_depth: dict[str, int] = {root_id: 0}
    # Key recorded when the issue was first discovered.
    visited_keys: dict[str, str] = {root_id: root_key}
    # BFS frontier: list of (issue_id, issue_key, depth_from_root).
    frontier: list[tuple[str, str, int]] = [(root_id, root_key, 0)]
    # Remaining capacity after the root itself occupies one slot.
    cap_remaining: int = max_tickets_per_root - 1
    at_cap: bool = False

    while frontier and not at_cap:
        current_depth: int = frontier[0][2]
        frontier_ids: list[str] = [t[0] for t in frontier]
        next_frontier: list[tuple[str, str, int]] = []

        # Batch-fetch relations once for Tier 1 + Tier 2 at this depth level.
        # Tier 3 (ticket_ref) uses a separate provider path below.
        tier12_active = frozenset(
            d
            for tier in TRAVERSAL_TIERS
            if Dimension.TICKET_REF not in tier
            for d in tier
            if dimensions.get(d, 0) > current_depth
        )
        relation_map: dict[str, list[RelationData]] = (
            await gateway.get_ticket_relations(frontier_ids) if tier12_active else {}
        )

        # Process each tier in priority order.
        for tier_dims in TRAVERSAL_TIERS:
            if at_cap:
                break

            if Dimension.TICKET_REF in tier_dims:
                # Tier 3: ticket_ref via caller-supplied async function.
                if ticket_ref_fn is None:
                    continue
                active_dims = _active_dims_for_tier(tier_dims, dimensions, current_depth)
                if not active_dims:
                    continue

                ref_map = await ticket_ref_fn(frontier_ids)
                for fid in frontier_ids:
                    for target_id, target_key in ref_map.get(fid, []):
                        if target_id in visited_depth:
                            continue
                        if cap_remaining > 0:
                            visited_depth[target_id] = current_depth + 1
                            visited_keys[target_id] = target_key
                            next_frontier.append((target_id, target_key, current_depth + 1))
                            cap_remaining -= 1
                        else:
                            logger.debug(
                                "Root %s hit per-root cap of %d (ticket_ref, depth %d)",
                                root_id,
                                max_tickets_per_root,
                                current_depth,
                            )
                            at_cap = True
                            break
                    if at_cap:
                        break

            else:
                # Tier 1 or Tier 2: filter relation_map by this tier's dims.
                active_dims = _active_dims_for_tier(tier_dims, dimensions, current_depth)
                if not active_dims:
                    continue

                for fid in frontier_ids:
                    for rel in relation_map.get(fid, []):
                        if rel.dimension not in active_dims:
                            continue
                        if rel.target_issue_id in visited_depth:
                            continue
                        if cap_remaining > 0:
                            visited_depth[rel.target_issue_id] = current_depth + 1
                            visited_keys[rel.target_issue_id] = rel.target_issue_key
                            next_frontier.append(
                                (
                                    rel.target_issue_id,
                                    rel.target_issue_key,
                                    current_depth + 1,
                                )
                            )
                            cap_remaining -= 1
                        else:
                            logger.debug(
                                "Root %s hit per-root cap of %d (%s, depth %d)",
                                root_id,
                                max_tickets_per_root,
                                tier_dims,
                                current_depth,
                            )
                            at_cap = True
                            break
                    if at_cap:
                        break

        frontier = next_frontier

    return visited_depth, visited_keys, at_cap


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def build_reachable_graph(
    *,
    roots: dict[str, str],
    dimensions: dict[str, int],
    max_tickets_per_root: int,
    gateway: LinearGateway,
    ticket_ref_fn: TicketRefProvider | None = None,
) -> TraversalResult:
    """
    Build the union reachable graph for a set of roots.

    Each root is traversed independently with its own BFS and per-root ticket
    cap.  The final result is the union of all per-root reachable sets.
    Tickets reachable from multiple roots carry the shortest effective depth
    and the complete set of root UUIDs that can reach them.

    Parameters
    ----------
    roots:
        Mapping from root issue UUID to its current human-facing key.  Every
        UUID in this mapping is treated as a traversal root.
    dimensions:
        Active dimension-depth configuration (dimension name → max total hops
        from any root).
    max_tickets_per_root:
        Maximum number of tickets (including the root itself) in any single
        root's reachable set.
    gateway:
        Gateway used to batch-read relation edges for Tier 1 and Tier 2.
    ticket_ref_fn:
        Optional async provider for Tier 3 (``ticket_ref``) edge discovery.
        Receives a list of issue UUIDs and returns
        ``{issue_id: [(target_id, target_key), ...]}``.  When ``None``,
        ``ticket_ref`` edges are not expanded.

    Returns
    -------
    TraversalResult
        Per-root reachable sets, the global union ticket map, and the set of
        roots that hit their per-root cap.

    Raises
    ------
    Exception
        Any exception raised by *gateway* or *ticket_ref_fn* propagates
        unchanged to the caller.
    """
    per_root_tickets: dict[str, frozenset[str]] = {}
    roots_at_cap: set[str] = set()

    # Global union tracking across all roots.
    global_depth: dict[str, int] = {}  # issue_id → shortest depth from any root
    global_keys: dict[str, str] = {}  # issue_id → key at first discovery
    global_root_ids: dict[str, set[str]] = {}  # issue_id → set of root UUIDs

    for root_id, root_key in roots.items():
        logger.debug("Traversing root %s (%s)", root_id, root_key)

        depth_map, key_map, at_cap = await _traverse_single_root(
            root_id=root_id,
            root_key=root_key,
            dimensions=dimensions,
            max_tickets_per_root=max_tickets_per_root,
            gateway=gateway,
            ticket_ref_fn=ticket_ref_fn,
        )

        per_root_tickets[root_id] = frozenset(depth_map)
        if at_cap:
            roots_at_cap.add(root_id)

        # Merge into global union, tracking minimum effective depth per ticket.
        for issue_id, depth in depth_map.items():
            if issue_id not in global_depth or depth < global_depth[issue_id]:
                global_depth[issue_id] = depth
                global_keys[issue_id] = key_map[issue_id]
            if issue_id not in global_root_ids:
                global_root_ids[issue_id] = set()
            global_root_ids[issue_id].add(root_id)

    tickets: dict[str, TraversedTicket] = {
        issue_id: TraversedTicket(
            issue_id=issue_id,
            issue_key=global_keys[issue_id],
            effective_depth=global_depth[issue_id],
            root_ids=frozenset(global_root_ids[issue_id]),
        )
        for issue_id in global_depth
    }

    return TraversalResult(
        per_root_tickets=per_root_tickets,
        tickets=tickets,
        roots_at_cap=frozenset(roots_at_cap),
    )
