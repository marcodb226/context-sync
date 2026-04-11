"""
Semantic type aliases for domain concepts.

Provides ``NewType`` aliases so that Pyright can distinguish between
identifiers that share the same ``str`` runtime representation but
represent distinct domain concepts.  Passing an ``IssueKey`` where an
``IssueId`` is expected (or vice-versa) is caught at static analysis time.

All aliases are ``NewType`` over ``str``; they impose zero runtime cost.

``IssueId``, ``IssueKey``, ``CommentId``, and ``AttachmentId`` are the
authoritative types from ``linear_client.types``.  Under ``TYPE_CHECKING``
the real imports are used so Pyright sees shared type identity across the
gateway boundary.  At runtime, equivalent ``NewType`` aliases are defined
locally so that ``linear-client`` remains an optional dependency.

``WriterId``, ``Timestamp``, ``WorkspaceId``, and ``WorkspaceSlug`` are
context-sync-only concepts and are always defined locally.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NewType

# ---------------------------------------------------------------------------
# Shared types — authoritative definitions live in linear_client.types.
#
# TYPE_CHECKING import gives Pyright shared type identity with the library,
# eliminating the bridge-import workaround previously needed at the gateway
# boundary.  The runtime fallback keeps linear-client as an optional
# dependency.
# ---------------------------------------------------------------------------

if TYPE_CHECKING:
    from linear_client.types import AttachmentId as AttachmentId
    from linear_client.types import CommentId as CommentId
    from linear_client.types import IssueId as IssueId
    from linear_client.types import IssueKey as IssueKey
else:
    IssueId = NewType("IssueId", str)
    """Stable Linear issue UUID (e.g. ``"00000000-0000-0000-0000-000000000001"``)."""

    IssueKey = NewType("IssueKey", str)
    """Human-facing issue key (e.g. ``"ACP-123"``)."""

    CommentId = NewType("CommentId", str)
    """Stable Linear comment UUID."""

    AttachmentId = NewType("AttachmentId", str)
    """Stable Linear attachment UUID."""

# ---------------------------------------------------------------------------
# Context-sync-only types — not shared with linear-client.
# ---------------------------------------------------------------------------

WorkspaceId = NewType("WorkspaceId", str)
"""Immutable Linear workspace UUID."""

WorkspaceSlug = NewType("WorkspaceSlug", str)
"""Human-readable workspace slug (e.g. ``"myteam"``)."""

WriterId = NewType("WriterId", str)
"""Unique identifier for a writer-lock invocation."""

Timestamp = NewType("Timestamp", str)
"""UTC RFC 3339 timestamp (e.g. ``"2026-01-15T09:30:00Z"``)."""
