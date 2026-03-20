"""
Configuration constants and traversal dimension definitions.

This module defines the built-in traversal dimensions, their default depths,
the traversal tier priority order, and the default runtime limits that later
tickets rely on.  All values come from the ADR (§1.1–§1.3) and the top-level
design (§1).
"""

from __future__ import annotations

from enum import StrEnum

# ---------------------------------------------------------------------------
# Traversal dimensions
# ---------------------------------------------------------------------------


class Dimension(StrEnum):
    """
    Built-in graph-traversal dimension names.

    Each dimension corresponds to one relationship type that the traversal
    engine can follow.  Depths are configured per-dimension and measured as
    total hops from the nearest root (ADR §1.2).
    """

    BLOCKS = "blocks"
    IS_BLOCKED_BY = "is_blocked_by"
    PARENT = "parent"
    CHILD = "child"
    RELATES_TO = "relates_to"
    TICKET_REF = "ticket_ref"


DEFAULT_DIMENSIONS: dict[str, int] = {
    Dimension.BLOCKS: 3,
    Dimension.IS_BLOCKED_BY: 2,
    Dimension.PARENT: 2,
    Dimension.CHILD: 2,
    Dimension.RELATES_TO: 1,
    Dimension.TICKET_REF: 1,
}
"""Default traversal-depth configuration (dimension name → max total hops)."""

# ---------------------------------------------------------------------------
# Traversal tiers (ADR §1.3)
#
# When a per-root ticket cap becomes relevant, higher-priority tiers at the
# current depth are processed before lower-priority tiers for that root.
# ---------------------------------------------------------------------------

TIER_1_DIMENSIONS: frozenset[str] = frozenset(
    {Dimension.BLOCKS, Dimension.IS_BLOCKED_BY, Dimension.PARENT, Dimension.CHILD}
)
"""Structural dependency edges — highest traversal priority."""

TIER_2_DIMENSIONS: frozenset[str] = frozenset({Dimension.RELATES_TO})
"""Informational relation edges — medium traversal priority."""

TIER_3_DIMENSIONS: frozenset[str] = frozenset({Dimension.TICKET_REF})
"""URL-discovered ticket references — lowest traversal priority."""

TRAVERSAL_TIERS: tuple[frozenset[str], ...] = (
    TIER_1_DIMENSIONS,
    TIER_2_DIMENSIONS,
    TIER_3_DIMENSIONS,
)
"""Tier groups ordered from highest to lowest traversal priority."""

# ---------------------------------------------------------------------------
# Runtime defaults
# ---------------------------------------------------------------------------

DEFAULT_MAX_TICKETS_PER_ROOT: int = 200
"""Default per-root ticket cap (ADR §1.1, §1.3)."""

DEFAULT_CONCURRENCY_LIMIT: int = 10
"""
Default asyncio.Semaphore limit for concurrent ticket fetches (ADR §3.1).

This is a per-process control.  Cross-process rate-limit coordination is
explicitly out of scope for the first release.
"""

FORMAT_VERSION: int = 1
"""On-disk file-format version written into ticket frontmatter."""


def resolve_dimensions(overrides: dict[str, int] | None) -> dict[str, int]:
    """
    Return a validated dimension-depth mapping.

    Parameters
    ----------
    overrides:
        Caller-provided dimension depths.  ``None`` means use defaults.
        When provided, unknown dimension names are rejected and negative
        depths raise ``ValueError``.

    Returns
    -------
    dict[str, int]
        A new dict with all built-in dimensions present.  Dimensions not
        listed in *overrides* retain their default depths.

    Raises
    ------
    ValueError
        If *overrides* contains an unrecognized dimension name or a
        negative depth value.
    """
    if overrides is None:
        return dict(DEFAULT_DIMENSIONS)

    valid_names = {d.value for d in Dimension}
    unknown = set(overrides) - valid_names
    if unknown:
        raise ValueError(
            f"Unknown dimension(s): {', '.join(sorted(unknown))}. "
            f"Valid dimensions: {', '.join(sorted(valid_names))}"
        )

    for name, depth in overrides.items():
        if depth < 0:
            raise ValueError(f"Dimension depth must be non-negative, got {name}={depth}")

    merged = dict(DEFAULT_DIMENSIONS)
    merged.update(overrides)
    return merged
