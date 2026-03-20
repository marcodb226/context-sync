"""
Tests for configuration parsing, dimension validation, and runtime defaults.
"""

from __future__ import annotations

import pytest

from context_sync._config import (
    DEFAULT_CONCURRENCY_LIMIT,
    DEFAULT_DIMENSIONS,
    DEFAULT_MAX_TICKETS_PER_ROOT,
    TIER_1_DIMENSIONS,
    TIER_2_DIMENSIONS,
    TIER_3_DIMENSIONS,
    TRAVERSAL_TIERS,
    Dimension,
    resolve_dimensions,
)


class TestDimensionEnum:
    """Dimension enum values match the ADR §1.1 built-in dimension names."""

    def test_all_dimensions_present(self) -> None:
        expected = {
            "blocks",
            "is_blocked_by",
            "parent",
            "child",
            "relates_to",
            "ticket_ref",
        }
        assert {d.value for d in Dimension} == expected

    def test_string_coercion(self) -> None:
        assert str(Dimension.BLOCKS) == "blocks"
        assert f"{Dimension.TICKET_REF}" == "ticket_ref"


class TestDefaultDimensions:
    """Default depths match ADR §1.1."""

    def test_default_depths(self) -> None:
        assert DEFAULT_DIMENSIONS["blocks"] == 3
        assert DEFAULT_DIMENSIONS["is_blocked_by"] == 2
        assert DEFAULT_DIMENSIONS["parent"] == 2
        assert DEFAULT_DIMENSIONS["child"] == 2
        assert DEFAULT_DIMENSIONS["relates_to"] == 1
        assert DEFAULT_DIMENSIONS["ticket_ref"] == 1

    def test_every_dimension_has_a_default(self) -> None:
        for d in Dimension:
            assert d.value in DEFAULT_DIMENSIONS


class TestResolveDimensions:
    """resolve_dimensions merges overrides with defaults and validates."""

    def test_none_returns_defaults(self) -> None:
        result = resolve_dimensions(None)
        assert result == DEFAULT_DIMENSIONS
        # Must be a new dict, not the module-level constant itself.
        assert result is not DEFAULT_DIMENSIONS

    def test_partial_override_merges(self) -> None:
        result = resolve_dimensions({"blocks": 5})
        assert result["blocks"] == 5
        assert result["relates_to"] == 1  # unchanged default

    def test_zero_depth_disables(self) -> None:
        result = resolve_dimensions({"ticket_ref": 0})
        assert result["ticket_ref"] == 0

    def test_unknown_dimension_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown dimension"):
            resolve_dimensions({"bogus": 1})

    def test_negative_depth_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            resolve_dimensions({"blocks": -1})

    def test_full_override(self) -> None:
        overrides = {d.value: 0 for d in Dimension}
        result = resolve_dimensions(overrides)
        assert all(v == 0 for v in result.values())


class TestTraversalTiers:
    """Tier groupings match ADR §1.3 and are disjoint."""

    def test_tier_count(self) -> None:
        assert len(TRAVERSAL_TIERS) == 3

    def test_tiers_are_disjoint(self) -> None:
        all_dims = TIER_1_DIMENSIONS | TIER_2_DIMENSIONS | TIER_3_DIMENSIONS
        assert len(all_dims) == (
            len(TIER_1_DIMENSIONS) + len(TIER_2_DIMENSIONS) + len(TIER_3_DIMENSIONS)
        )

    def test_tiers_cover_all_dimensions(self) -> None:
        all_dims = TIER_1_DIMENSIONS | TIER_2_DIMENSIONS | TIER_3_DIMENSIONS
        assert all_dims == {d.value for d in Dimension}

    def test_structural_in_tier_1(self) -> None:
        assert "blocks" in TIER_1_DIMENSIONS
        assert "is_blocked_by" in TIER_1_DIMENSIONS
        assert "parent" in TIER_1_DIMENSIONS
        assert "child" in TIER_1_DIMENSIONS

    def test_informational_in_tier_2(self) -> None:
        assert "relates_to" in TIER_2_DIMENSIONS

    def test_url_refs_in_tier_3(self) -> None:
        assert "ticket_ref" in TIER_3_DIMENSIONS


class TestRuntimeDefaults:
    """Sanity checks for runtime constants."""

    def test_max_tickets_per_root(self) -> None:
        assert DEFAULT_MAX_TICKETS_PER_ROOT == 200

    def test_concurrency_limit_positive(self) -> None:
        assert DEFAULT_CONCURRENCY_LIMIT > 0
