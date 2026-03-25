"""
Semantic type aliases for domain concepts.

Provides ``NewType`` aliases so that Pyright can distinguish between
identifiers that share the same ``str`` runtime representation but
represent distinct domain concepts.  Passing an ``IssueKey`` where an
``IssueId`` is expected (or vice-versa) is caught at static analysis time.

All aliases are ``NewType`` over ``str``; they impose zero runtime cost.
"""

from __future__ import annotations

from typing import NewType

IssueId = NewType("IssueId", str)
"""Stable Linear issue UUID (e.g. ``"00000000-0000-0000-0000-000000000001"``)."""

IssueKey = NewType("IssueKey", str)
"""Human-facing issue key (e.g. ``"ACP-123"``)."""

WorkspaceId = NewType("WorkspaceId", str)
"""Immutable Linear workspace UUID."""

WorkspaceSlug = NewType("WorkspaceSlug", str)
"""Human-readable workspace slug (e.g. ``"myteam"``)."""

CommentId = NewType("CommentId", str)
"""Stable Linear comment UUID."""

AttachmentId = NewType("AttachmentId", str)
"""Stable Linear attachment UUID."""

WriterId = NewType("WriterId", str)
"""Unique identifier for a writer-lock invocation."""

Timestamp = NewType("Timestamp", str)
"""UTC RFC 3339 timestamp (e.g. ``"2026-01-15T09:30:00Z"``)."""
