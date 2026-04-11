"""
Semantic type aliases for domain concepts.

Provides named aliases for domain concepts that share the same ``str``
runtime representation but carry different semantics. Passing an
``IssueKey`` where an ``IssueId`` is expected (or vice-versa) is caught at
static analysis time.

When ``linear-client`` is importable, this module re-exports the upstream
aliases for the shared boundary vocabulary so context-sync and
``linear-client`` use one runtime/type-checker identity for the same
concepts. ``Timestamp`` keeps its local public name for ergonomics while
aliasing upstream ``IsoTimestamp``.

When ``linear-client`` is unavailable, local ``NewType`` fallbacks preserve
package importability. ``WriterId``, ``WorkspaceId``, and ``WorkspaceSlug``
remain context-sync-only concepts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NewType

# ---------------------------------------------------------------------------
# Shared types — authoritative definitions live in linear_client.types.
#
# The runtime import path keeps one shared alias identity when the dependency
# is installed. The fallback keeps context-sync importable in environments
# that do not bundle linear-client.
# ---------------------------------------------------------------------------

if TYPE_CHECKING:
    from linear_client.types import (
        AssetUrl,
        AttachmentId,
        CommentId,
        IssueId,
        IssueKey,
        IssueLinkType,
    )
    from linear_client.types import IsoTimestamp as Timestamp

try:
    from linear_client.types import (
        AssetUrl,
        AttachmentId,
        CommentId,
        IssueId,
        IssueKey,
        IssueLinkType,
    )
    from linear_client.types import IsoTimestamp as Timestamp
except ImportError:
    IssueId = NewType("IssueId", str)
    """Stable Linear issue UUID (e.g. ``"00000000-0000-0000-0000-000000000001"``)."""

    IssueKey = NewType("IssueKey", str)
    """Human-facing issue key (e.g. ``"ACP-123"``)."""

    CommentId = NewType("CommentId", str)
    """Stable Linear comment UUID."""

    AttachmentId = NewType("AttachmentId", str)
    """Stable Linear attachment UUID."""

    AssetUrl = NewType("AssetUrl", str)
    """Linear attachment asset URL."""

    IssueLinkType = NewType("IssueLinkType", str)
    """Linear relation type value (e.g. ``"blocks"`` or ``"related"``)."""

    Timestamp = NewType("Timestamp", str)
    """UTC RFC 3339 timestamp (e.g. ``"2026-01-15T09:30:00Z"``)."""

# ---------------------------------------------------------------------------
# Context-sync-only types — not shared with linear-client.
# ---------------------------------------------------------------------------

WorkspaceId = NewType("WorkspaceId", str)
"""Immutable Linear workspace UUID."""

WorkspaceSlug = NewType("WorkspaceSlug", str)
"""Human-readable workspace slug (e.g. ``"myteam"``)."""

WriterId = NewType("WriterId", str)
"""Unique identifier for a writer-lock invocation."""
