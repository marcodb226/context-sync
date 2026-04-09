"""
LinearGateway protocol and associated data types.

This module defines the adapter boundary between context-sync and the Linear
integration layer.  The ``LinearGateway`` protocol captures the exact read
operations that context-sync requires, as audited by
`docs/design/linear-domain-coverage-audit-v1.1.0.md
<../../docs/design/linear-domain-coverage-audit-v1.1.0.md>`_.

Implementations must stay **read-only** with respect to Linear.

Two implementations are expected:

* ``RealLinearGateway`` — wraps a ``linear-client`` ``Linear`` instance,
  using the domain layer by default and the narrow raw-GraphQL adapter
  helpers for relation reads and composite refresh-metadata passes.
  Created by later implementation tickets.

* ``FakeLinearGateway`` (in ``_testing.py``) — an in-memory test double
  established by M1-1 so that later integration tests extend one reusable
  fixture pattern instead of inventing one-off mocks per ticket.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from context_sync._types import (
    AttachmentId,
    CommentId,
    IssueId,
    IssueKey,
    Timestamp,
    WorkspaceId,
    WorkspaceSlug,
)

# ---------------------------------------------------------------------------
# Gateway data types
#
# These are internal state containers constructed from trusted data inside the
# adapter layer, so they use frozen dataclasses per the data-modeling policy.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkspaceIdentity:
    """
    Stable workspace identity for manifest binding.

    Attributes
    ----------
    workspace_id:
        Immutable Linear workspace UUID.
    workspace_slug:
        Human-readable workspace slug (e.g. ``"myteam"``).
    """

    workspace_id: WorkspaceId
    workspace_slug: WorkspaceSlug


@dataclass(frozen=True)
class IssueData:
    """
    Core issue scalar fields needed for rendering and traversal.

    Attributes
    ----------
    issue_id:
        Stable Linear issue UUID — the authoritative identity for
        deduplication, root membership, and issue-key-change handling.
    issue_key:
        Current human-facing key (e.g. ``"ACP-123"``).
    title:
        Issue title.
    status:
        Current workflow status name, or ``None`` if unset.
    assignee:
        Display name of the current assignee, or ``None``.
    creator:
        Display name of the issue creator, or ``None``.
    priority:
        Numeric priority (Linear uses 0–4), or ``None``.
    description:
        Markdown description body, or ``None`` if empty.
    created_at:
        UTC RFC 3339 creation timestamp.
    updated_at:
        UTC RFC 3339 last-updated timestamp.
    parent_issue_id:
        Stable UUID of the parent issue, or ``None``.
    parent_issue_key:
        Current human-facing key of the parent, or ``None``.
    labels:
        Rendered label strings, each in ``"Group / Label"`` or ``"Label"``
        form, sorted lexicographically.
    """

    issue_id: IssueId
    issue_key: IssueKey
    title: str
    status: str | None
    assignee: str | None
    creator: str | None
    priority: int | None
    description: str | None
    created_at: Timestamp
    updated_at: Timestamp
    parent_issue_id: IssueId | None
    parent_issue_key: IssueKey | None
    labels: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CommentData:
    """
    A single comment from a ticket.

    Attributes
    ----------
    comment_id:
        Stable Linear comment UUID.
    body:
        Markdown comment body.
    author:
        Display name of the comment author, or ``None``.
    created_at:
        UTC RFC 3339 creation timestamp.
    updated_at:
        UTC RFC 3339 last-edit timestamp, or ``None`` if never edited or
        if the field is unavailable.
    parent_comment_id:
        Stable UUID of the parent comment for threaded replies, or
        ``None`` for top-level comments.
    """

    comment_id: CommentId
    body: str
    author: str | None
    created_at: Timestamp
    updated_at: Timestamp | None
    parent_comment_id: CommentId | None


@dataclass(frozen=True)
class ThreadData:
    """
    Thread-level metadata.

    Attributes
    ----------
    root_comment_id:
        Stable UUID of the thread's root comment.
    resolved:
        Whether the thread has been marked resolved.
    """

    root_comment_id: CommentId
    resolved: bool


@dataclass(frozen=True)
class AttachmentData:
    """
    Attachment metadata (content not downloaded in v1).

    Attributes
    ----------
    attachment_id:
        Stable Linear attachment UUID.
    title:
        Human-readable title, or ``None``.
    url:
        Attachment URL.
    created_at:
        UTC RFC 3339 creation timestamp.
    creator:
        Display name of the attachment creator, or ``None``.
    """

    attachment_id: AttachmentId
    title: str | None
    url: str
    created_at: Timestamp
    creator: str | None


@dataclass(frozen=True)
class RelationData:
    """
    A single issue-relation edge.

    Attributes
    ----------
    dimension:
        Traversal dimension name (maps to :class:`_config.Dimension` values).
    relation_type:
        Linear relation type string (e.g. ``"blocks"``, ``"is_blocked_by"``).
    target_issue_id:
        Stable UUID of the related issue.
    target_issue_key:
        Current human-facing key of the related issue.
    """

    dimension: str
    relation_type: str
    target_issue_id: IssueId
    target_issue_key: IssueKey


@dataclass(frozen=True)
class TicketBundle:
    """
    All data needed to render and persist one ticket file.

    Assembled by the gateway from domain-layer and adapter-helper results
    so that downstream rendering code receives a single coherent object.
    """

    issue: IssueData
    workspace: WorkspaceIdentity
    comments: list[CommentData] = field(default_factory=list)
    threads: list[ThreadData] = field(default_factory=list)
    attachments: list[AttachmentData] = field(default_factory=list)
    relations: list[RelationData] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Refresh-specific metadata types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RefreshIssueMeta:
    """
    Minimal issue metadata for the composite freshness check.

    Attributes
    ----------
    issue_id:
        Stable UUID.
    issue_key:
        Current human-facing key.
    updated_at:
        UTC RFC 3339 issue-level ``updated_at``.
    visible:
        Whether the issue is visible in the current caller's view.
    """

    issue_id: IssueId
    issue_key: IssueKey
    updated_at: Timestamp
    visible: bool


@dataclass(frozen=True)
class RefreshCommentMeta:
    """
    Per-comment metadata for ``comments_signature`` computation.

    Attributes
    ----------
    comment_id:
        Stable Linear comment UUID.
    root_comment_id:
        UUID of the thread's root comment.
    parent_comment_id:
        UUID of the direct parent, or ``None`` for root comments.
    updated_at:
        UTC RFC 3339 last-edit timestamp, or ``None`` if unavailable.
    deleted:
        Deletion state — ``True`` if deleted/tombstoned, ``False`` if live,
        ``None`` if the signal is unavailable.
    """

    comment_id: CommentId
    root_comment_id: CommentId
    parent_comment_id: CommentId | None
    updated_at: Timestamp | None
    deleted: bool | None


@dataclass(frozen=True)
class RefreshThreadMeta:
    """
    Per-thread metadata for ``comments_signature`` computation.

    Attributes
    ----------
    root_comment_id:
        UUID of the thread's root comment.
    resolved:
        Whether the thread has been marked resolved.
    """

    root_comment_id: CommentId
    resolved: bool


# ---------------------------------------------------------------------------
# Gateway protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LinearGateway(Protocol):
    """
    Contract for the subset of Linear operations that context-sync requires.

    The six methods below correspond to the narrow adapter helpers defined in
    `docs/design/linear-domain-coverage-audit-v1.1.0.md
    <../../docs/design/linear-domain-coverage-audit-v1.1.0.md>`_:

    * :meth:`fetch_issue` — domain-layer single-ticket fetch (comments,
      attachments, relations) plus raw-GraphQL supplementary data (workspace,
      labels, parent, priority), assembled into a :class:`TicketBundle`.
    * :meth:`get_workspace_identity` — raw-GraphQL workspace identity lookup.
    * :meth:`get_ticket_relations` — domain-layer fan-out via
      ``Issue.get_links()`` for traversal and rendered relations.
    * :meth:`get_refresh_issue_metadata` — raw-GraphQL batched issue freshness.
    * :meth:`get_refresh_comment_metadata` — raw-GraphQL batched comment
      metadata for ``comments_signature``.
    * :meth:`get_refresh_relation_metadata` — raw-GraphQL batched relation
      metadata for ``relations_signature``.

    Implementations must be **read-only** with respect to Linear.  Raw-GraphQL
    helpers must use ``query(...)`` or ``paginate_connection(...)`` and must
    never call ``gql(...)`` or ``mutate(...)``.
    """

    async def fetch_issue(self, issue_id_or_key: str) -> TicketBundle:
        """
        Fetch a complete ticket bundle for a single issue.

        The parameter is typed as bare ``str`` intentionally: this is the
        polymorphic entry point where untyped external input (CLI arguments,
        URL-extracted keys, raw UUIDs) enters the typed domain layer.
        Callers genuinely do not know whether the value is an ``IssueId``
        or an ``IssueKey``; the implementation resolves the ambiguity.

        Parameters
        ----------
        issue_id_or_key:
            A stable issue UUID, human-facing issue key (e.g. ``"ACP-123"``),
            or any string that the implementation can resolve to a single
            issue.  Typed as bare ``str`` because the caller does not know
            which form it holds.

        Returns
        -------
        TicketBundle
            All data needed to render and persist one ticket file, including
            scalar fields, comments, attachments, and relations.

        Raises
        ------
        RootNotFoundError
            If the issue is not available in the current visible view and
            is being fetched as an explicit root.
        """
        ...

    async def get_workspace_identity(self, issue_id: IssueId) -> WorkspaceIdentity:
        """
        Read stable workspace identity for manifest validation.

        Used by ``sync`` and ``add`` to verify that a root ticket belongs to
        the same workspace as the context directory.

        Parameters
        ----------
        issue_id:
            Stable UUID of the issue whose workspace to look up.

        Returns
        -------
        WorkspaceIdentity
            The workspace UUID and human-readable slug for the issue's
            workspace.

        Raises
        ------
        RootNotFoundError
            If the issue is not available in the current visible view.
        """
        ...

    async def get_ticket_relations(
        self, issue_ids: Sequence[IssueId]
    ) -> dict[IssueId, list[RelationData]]:
        """
        Batch-read issue relations for traversal and rendered frontmatter.

        Returns a mapping from issue UUID to that issue's outgoing relation
        edges.  Issues that are not visible or have no relations may be
        absent from the returned dict or present with an empty list.

        Parameters
        ----------
        issue_ids:
            Sequence of stable issue UUIDs to query.  Duplicates are
            tolerated; the implementation deduplicates internally.

        Returns
        -------
        dict[IssueId, list[RelationData]]
            Mapping from issue UUID to outgoing relation edges.  Missing
            keys indicate no visible relations; an empty list indicates
            the issue was found but has no outgoing edges.

        Raises
        ------
        SystemicRemoteError
            If a systemic upstream failure prevents the batch read.
        """
        ...

    async def get_refresh_issue_metadata(
        self, issue_ids: Sequence[IssueId]
    ) -> dict[IssueId, RefreshIssueMeta]:
        """
        Batch-read issue identity + ``updated_at`` for freshness checks.

        Returns a mapping from issue UUID to issue-level metadata.  Issues
        not visible in the current view should still appear with
        ``visible=False`` when possible.

        Parameters
        ----------
        issue_ids:
            Sequence of stable issue UUIDs to query.  Duplicates are
            tolerated.

        Returns
        -------
        dict[IssueId, RefreshIssueMeta]
            Mapping from issue UUID to issue-level metadata including
            ``updated_at`` and ``visible``.  Issues entirely absent from
            the upstream response may be missing from the returned dict.

        Raises
        ------
        SystemicRemoteError
            If a systemic upstream failure prevents the batch read.
        """
        ...

    async def get_refresh_comment_metadata(
        self, issue_ids: Sequence[IssueId]
    ) -> dict[IssueId, tuple[list[RefreshCommentMeta], list[RefreshThreadMeta]]]:
        """
        Batch-read comment/thread metadata for ``comments_signature``.

        Returns a mapping from issue UUID to a ``(comments, threads)`` pair
        containing the per-comment and per-thread metadata needed to compute
        the canonical ``comments_signature`` digest without downloading full
        comment bodies.

        Parameters
        ----------
        issue_ids:
            Sequence of stable issue UUIDs to query.  Duplicates are
            tolerated.

        Returns
        -------
        dict[IssueId, tuple[list[RefreshCommentMeta], list[RefreshThreadMeta]]]
            Mapping from issue UUID to a ``(comments, threads)`` pair.
            Issues with no comments return ``([], [])``.  Issues absent
            from the upstream response may be missing from the dict.

        Raises
        ------
        SystemicRemoteError
            If a systemic upstream failure prevents the batch read.
        """
        ...

    async def get_refresh_relation_metadata(
        self, issue_ids: Sequence[IssueId]
    ) -> dict[IssueId, list[RelationData]]:
        """
        Batch-read relation metadata for ``relations_signature``.

        Returns a mapping from issue UUID to relation edges, in the same
        shape as :meth:`get_ticket_relations`.  The implementation may
        share the underlying query with :meth:`get_ticket_relations` or
        use a separate batched path.

        Parameters
        ----------
        issue_ids:
            Sequence of stable issue UUIDs to query.  Duplicates are
            tolerated.

        Returns
        -------
        dict[IssueId, list[RelationData]]
            Mapping from issue UUID to relation edges, in the same shape
            as :meth:`get_ticket_relations`.

        Raises
        ------
        SystemicRemoteError
            If a systemic upstream failure prevents the batch read.
        """
        ...
