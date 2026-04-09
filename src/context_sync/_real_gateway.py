"""
Production adapter between context-sync and ``linear-client``.

Wraps a ``linear_client.Linear`` instance, using the domain layer by default
and narrow raw-GraphQL helpers for workspace identity, labels, and composite
refresh-metadata passes.  Implements the :class:`LinearGateway` protocol
defined in :mod:`_gateway`.

The adapter boundary is governed by
`docs/design/linear-domain-coverage-audit-v1.1.0.md
<../../docs/design/linear-domain-coverage-audit-v1.1.0.md>`_.
Raw ``linear.gql.*`` usage is restricted to five approved helper categories:

* workspace identity (``get_workspace_identity``)
* issue labels (internal helper for ``fetch_issue``)
* refresh issue metadata (``get_refresh_issue_metadata``)
* refresh comment metadata (``get_refresh_comment_metadata``)
* refresh relation metadata (``get_refresh_relation_metadata``)

All raw helpers are read-only and use ``query(...)`` or
``paginate_connection(...)``; they never call ``gql(...)`` or ``mutate(...)``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from context_sync._errors import RootNotFoundError, SystemicRemoteError
from context_sync._gateway import (
    AttachmentData,
    CommentData,
    IssueData,
    RefreshCommentMeta,
    RefreshIssueMeta,
    RefreshThreadMeta,
    RelationData,
    ThreadData,
    TicketBundle,
    WorkspaceIdentity,
)
from context_sync._types import (
    AttachmentId,
    CommentId,
    IssueId,
    IssueKey,
    Timestamp,
    WorkspaceId,
    WorkspaceSlug,
)

if TYPE_CHECKING:
    from linear_client import Linear

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Relation-normalization constants
#
# Directional "blocks" links are dimension-specific; informational link types
# ("related", "duplicate", "similar") all map to the ``relates_to`` dimension
# while preserving the upstream ``link_type`` in ``RelationData.relation_type``.
# ---------------------------------------------------------------------------

_INFORMATIONAL_LINK_TYPES: frozenset[str] = frozenset({"related", "duplicate", "similar"})

# ---------------------------------------------------------------------------
# Raw GraphQL queries — approved helpers per M5-D1 boundary audit
# ---------------------------------------------------------------------------

_ISSUE_SUPPLEMENTARY_QUERY = """\
query IssueSupplement($issueId: String!) {
  issue(id: $issueId) {
    priority
    parent { id identifier }
    team { organization { id urlKey } }
    labels { nodes { name parent { name } } }
  }
}"""

_WORKSPACE_IDENTITY_QUERY = """\
query WorkspaceIdentity($issueId: String!) {
  issue(id: $issueId) {
    team { organization { id urlKey } }
  }
}"""

_REFRESH_ISSUES_QUERY = """\
query RefreshIssueMeta($issueIds: [UUID!]!, $first: Int, $after: String) {
  issues(
    filter: { id: { in: $issueIds } }
    first: $first
    after: $after
  ) {
    edges { node { id identifier updatedAt } }
    pageInfo { hasNextPage endCursor }
  }
}"""

_REFRESH_COMMENTS_QUERY = """\
query RefreshCommentMeta($issueId: ID!, $first: Int, $after: String) {
  comments(
    filter: { issue: { id: { eq: $issueId } } }
    first: $first
    after: $after
  ) {
    edges {
      node {
        id
        updatedAt
        parent { id }
        resolvedAt
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}"""

_REFRESH_FORWARD_LINKS_QUERY = """\
query RefreshForwardLinks($issueId: String!, $first: Int, $after: String) {
  issue(id: $issueId) {
    relations(first: $first, after: $after) {
      edges {
        node {
          type
          relatedIssue { id identifier }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}"""

_REFRESH_INVERSE_LINKS_QUERY = """\
query RefreshInverseLinks($issueId: String!, $first: Int, $after: String) {
  issue(id: $issueId) {
    inverseRelations(first: $first, after: $after) {
      edges {
        node {
          type
          issue { id identifier }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_link(
    link_type: str,
    *,
    is_forward: bool,
    target_id: str,
    target_key: str,
) -> RelationData:
    """
    Convert one IssueLink record into a ``RelationData`` value.

    Normalization rules are from the M5-D1 audit type-mapping table:

    * Forward ``"blocks"`` → dimension ``blocks``, relation_type ``"blocks"``
    * Inverse ``"blocks"`` → dimension ``is_blocked_by``, relation_type ``"blocks"``
    * Informational types (``"related"``, ``"duplicate"``, ``"similar"``) →
      dimension ``relates_to``, relation_type preserves upstream value
    * Unknown types → dimension ``relates_to``, relation_type preserves value

    Parent/child hierarchy is never inferred from IssueLink records.
    """
    if link_type == "blocks":
        dimension = "blocks" if is_forward else "is_blocked_by"
    elif link_type in _INFORMATIONAL_LINK_TYPES:
        dimension = "relates_to"
    else:
        dimension = "relates_to"
    return RelationData(
        dimension=dimension,
        relation_type=link_type,
        target_issue_id=IssueId(target_id),
        target_issue_key=IssueKey(target_key),
    )


def _resolve_root_comment(
    comment_id: str,
    parent_map: dict[str, str | None],
) -> str:
    """
    Walk the parent chain to find the thread root comment id.

    Provides cycle detection to avoid infinite loops on malformed data.
    """
    current = comment_id
    visited: set[str] = set()
    while True:
        parent = parent_map.get(current)
        if parent is None or parent in visited:
            return current
        visited.add(current)
        current = parent


def _render_label(name: str, parent_name: str | None) -> str:
    """
    Format a label as ``"Group / Label"`` when a parent group exists,
    or as ``"Label"`` for root-level labels.
    """
    if parent_name:
        return f"{parent_name} / {name}"
    return name


# ---------------------------------------------------------------------------
# RealLinearGateway
# ---------------------------------------------------------------------------


class RealLinearGateway:
    """
    Production :class:`LinearGateway` backed by a ``linear_client.Linear``
    instance.

    The gateway is **read-only** with respect to Linear.  Domain-layer
    reads (``Issue.fetch()``, ``Issue.get_comments()``,
    ``Issue.get_attachments()``, ``Issue.get_links()``) are preferred
    wherever the packaged surface covers the required operation.  Raw
    ``linear.gql.query()`` and ``linear.gql.paginate_connection()`` are
    used only for the five audited helper categories.

    Parameters
    ----------
    linear:
        An authenticated ``linear_client.Linear`` instance.  The caller is
        responsible for creating and (optionally) closing this client.

    Example
    -------
    ::

        from linear_client import Linear
        from context_sync._real_gateway import RealLinearGateway
        from context_sync._sync import ContextSync

        async with Linear() as client:
            gateway = RealLinearGateway(client)
            ctx = ContextSync(context_dir=".", _gateway_override=gateway)
            result = await ctx.sync(key="ENG-42")
    """

    def __init__(self, linear: Linear) -> None:
        self._linear = linear

    # -- Protocol methods: domain-layer paths --------------------------------

    async def fetch_issue(self, issue_id_or_key: str) -> TicketBundle:
        """
        Fetch a complete ticket bundle for a single issue.

        Uses the domain-layer ``Issue.fetch()`` for scalar metadata,
        ``Issue.get_comments()`` for comment threads,
        ``Issue.get_attachments()`` for attachment metadata, and
        ``Issue.get_links()`` for per-issue relations.  Workspace identity,
        labels, parent issue, and priority come from a single supplementary
        raw-GraphQL helper.

        Parameters
        ----------
        issue_id_or_key:
            Stable issue UUID, human-facing key, or resolvable string.

        Returns
        -------
        TicketBundle

        Raises
        ------
        RootNotFoundError
            If the issue is not available.
        SystemicRemoteError
            If a systemic upstream failure prevents the fetch.
        """
        try:
            from linear_client.errors import LinearNotFoundError
            from linear_client.types import IssueId as UpstreamIssueId
        except ImportError as exc:
            raise SystemicRemoteError("linear-client is not installed") from exc

        try:
            issue = self._linear.issue(id=UpstreamIssueId(issue_id_or_key))
            issue = await issue.fetch()
        except LinearNotFoundError as exc:
            raise RootNotFoundError(f"Issue not found: {issue_id_or_key!r}") from exc
        except Exception as exc:
            raise SystemicRemoteError(f"Failed to fetch issue {issue_id_or_key!r}: {exc}") from exc

        issue_id_val = issue.peek_id()
        if issue_id_val is None:
            raise SystemicRemoteError(f"Issue fetch returned no id for {issue_id_or_key!r}")
        issue_id_str = str(issue_id_val)

        # Concurrently fetch: comments, attachments, links, supplementary data.
        try:
            comments_result, attachments_result, links_result, supp = await asyncio.gather(
                issue.get_comments(),
                issue.get_attachments(),
                issue.get_links(),
                self._fetch_issue_supplementary(issue_id_str),
            )
        except LinearNotFoundError as exc:
            raise RootNotFoundError(
                f"Issue not found during detail fetch: {issue_id_or_key!r}"
            ) from exc
        except Exception as exc:
            raise SystemicRemoteError(
                f"Failed to fetch issue details for {issue_id_or_key!r}: {exc}"
            ) from exc

        # Build IssueData from domain-layer + supplementary fields.
        issue_key_val = issue.peek_key()
        status_obj = issue.peek_status()
        status_name = status_obj.peek_name() if status_obj else None
        assignee_obj = issue.peek_assignee()
        assignee_name: str | None = None
        if assignee_obj is not None:
            assignee_name = assignee_obj.peek_name()
        creator_obj = issue.peek_creator()
        creator_name: str | None = None
        if creator_obj is not None:
            creator_name = creator_obj.peek_name()

        workspace, labels, parent_id, parent_key, priority = supp

        issue_data = IssueData(
            issue_id=IssueId(issue_id_str),
            issue_key=IssueKey(str(issue_key_val)) if issue_key_val else IssueKey(""),
            title=issue.peek_title() or "",
            status=status_name,
            assignee=assignee_name,
            creator=creator_name,
            priority=priority,
            description=issue.peek_description(),
            created_at=Timestamp(str(issue.peek_created_at() or "")),
            updated_at=Timestamp(str(issue.peek_updated_at() or "")),
            parent_issue_id=parent_id,
            parent_issue_key=parent_key,
            labels=labels,
        )

        # Build comments and threads from domain-layer comment tree.
        comments_data, threads_data = self._flatten_comments(comments_result or [])

        # Build attachments from domain-layer attachment list.
        attachments_data = self._convert_attachments(attachments_result or [])

        # Build relations from domain-layer link list.
        relations_data = self._normalize_links(links_result or [], issue_id_str)

        return TicketBundle(
            issue=issue_data,
            workspace=workspace,
            comments=comments_data,
            threads=threads_data,
            attachments=attachments_data,
            relations=relations_data,
        )

    async def get_workspace_identity(self, issue_id: IssueId) -> WorkspaceIdentity:
        """
        Read stable workspace identity for manifest validation.

        Uses a single raw-GraphQL query to fetch the workspace UUID and slug
        through the issue's team → organization path.

        Parameters
        ----------
        issue_id:
            Stable UUID of the issue whose workspace to look up.

        Returns
        -------
        WorkspaceIdentity

        Raises
        ------
        RootNotFoundError
            If the issue is not available.
        SystemicRemoteError
            If a systemic upstream failure prevents the lookup.
        """
        try:
            from linear_client.errors import LinearNotFoundError
        except ImportError as exc:
            raise SystemicRemoteError("linear-client is not installed") from exc

        try:
            result = await self._linear.gql.query(
                _WORKSPACE_IDENTITY_QUERY,
                {"issueId": str(issue_id)},
                operation_name="WorkspaceIdentity",
            )
        except LinearNotFoundError as exc:
            raise RootNotFoundError(f"Issue not found: {issue_id!r}") from exc
        except Exception as exc:
            raise SystemicRemoteError(
                f"Failed to fetch workspace identity for {issue_id!r}: {exc}"
            ) from exc

        return self._extract_workspace(result, issue_id)

    async def get_ticket_relations(
        self, issue_ids: Sequence[IssueId]
    ) -> dict[IssueId, list[RelationData]]:
        """
        Batch-read issue relations for traversal using domain-layer fan-out.

        Uses ``Issue.get_links()`` per issue rather than raw GraphQL, per the
        M5-D1 boundary audit.  Deduplicates input ids and manages concurrency
        through ``asyncio.gather``.

        Parameters
        ----------
        issue_ids:
            Sequence of stable issue UUIDs.  Duplicates are tolerated.

        Returns
        -------
        dict[IssueId, list[RelationData]]

        Raises
        ------
        SystemicRemoteError
            If a systemic upstream failure prevents the batch read.
        """
        from linear_client.types import IssueId as UpstreamIssueId

        unique_ids = list(dict.fromkeys(issue_ids))
        if not unique_ids:
            return {}

        async def fetch_one(uid: IssueId) -> tuple[IssueId, list[RelationData]]:
            try:
                issue = self._linear.issue(id=UpstreamIssueId(str(uid)))
                links = await issue.get_links()
                return uid, self._normalize_links(links, str(uid))
            except Exception:
                logger.debug("get_ticket_relations: skipping issue %s (not visible or error)", uid)
                return uid, []

        try:
            pairs = await asyncio.gather(*(fetch_one(uid) for uid in unique_ids))
        except Exception as exc:
            raise SystemicRemoteError(
                f"Systemic failure during relation batch read: {exc}"
            ) from exc

        return {uid: rels for uid, rels in pairs}

    # -- Protocol methods: raw-GraphQL refresh helpers -----------------------

    async def get_refresh_issue_metadata(
        self, issue_ids: Sequence[IssueId]
    ) -> dict[IssueId, RefreshIssueMeta]:
        """
        Batch-read issue identity + ``updated_at`` for freshness checks.

        Uses a paginated raw-GraphQL query with an ``id: { in: [...] }``
        filter.  Issues absent from the response are omitted from the
        returned dict (they may be invisible or deleted).

        Parameters
        ----------
        issue_ids:
            Sequence of stable issue UUIDs.  Duplicates are tolerated.

        Returns
        -------
        dict[IssueId, RefreshIssueMeta]

        Raises
        ------
        SystemicRemoteError
            If a systemic upstream failure prevents the batch read.
        """
        unique_ids = list(dict.fromkeys(str(uid) for uid in issue_ids))
        if not unique_ids:
            return {}

        try:
            nodes = await self._linear.gql.paginate_connection(
                document=_REFRESH_ISSUES_QUERY,
                variables={"issueIds": unique_ids},
                connection_path=["issues"],
            )
        except Exception as exc:
            raise SystemicRemoteError(f"Failed to batch-read issue metadata: {exc}") from exc

        requested: set[str] = set(unique_ids)
        result: dict[IssueId, RefreshIssueMeta] = {}
        seen_ids: set[str] = set()
        for node in nodes:
            nid = node.get("id")
            nkey = node.get("identifier")
            nupdated = node.get("updatedAt")
            if not isinstance(nid, str):
                continue
            seen_ids.add(nid)
            result[IssueId(nid)] = RefreshIssueMeta(
                issue_id=IssueId(nid),
                issue_key=IssueKey(str(nkey)) if nkey else IssueKey(""),
                updated_at=Timestamp(str(nupdated)) if nupdated else Timestamp(""),
                visible=True,
            )

        # Issues in the request but absent from the response are not visible.
        for uid_str in requested - seen_ids:
            result[IssueId(uid_str)] = RefreshIssueMeta(
                issue_id=IssueId(uid_str),
                issue_key=IssueKey(""),
                updated_at=Timestamp(""),
                visible=False,
            )

        return result

    async def get_refresh_comment_metadata(
        self, issue_ids: Sequence[IssueId]
    ) -> dict[IssueId, tuple[list[RefreshCommentMeta], list[RefreshThreadMeta]]]:
        """
        Batch-read comment/thread metadata for ``comments_signature``.

        Fans out one raw-GraphQL paginated query per issue (the upstream API
        does not support a single multi-issue comment read).

        Parameters
        ----------
        issue_ids:
            Sequence of stable issue UUIDs.  Duplicates are tolerated.

        Returns
        -------
        dict[IssueId, tuple[list[RefreshCommentMeta], list[RefreshThreadMeta]]]

        Raises
        ------
        SystemicRemoteError
            If a systemic upstream failure prevents the batch read.
        """
        unique_ids = list(dict.fromkeys(issue_ids))
        if not unique_ids:
            return {}

        async def fetch_one(
            uid: IssueId,
        ) -> tuple[IssueId, tuple[list[RefreshCommentMeta], list[RefreshThreadMeta]]]:
            try:
                nodes = await self._linear.gql.paginate_connection(
                    document=_REFRESH_COMMENTS_QUERY,
                    variables={"issueId": str(uid)},
                    connection_path=["comments"],
                )
            except Exception:
                logger.debug("get_refresh_comment_metadata: no comments for %s", uid)
                return uid, ([], [])

            # Build parent map for root resolution.
            parent_map: dict[str, str | None] = {}
            for node in nodes:
                cid = node.get("id")
                parent_obj = node.get("parent")
                pid = parent_obj.get("id") if isinstance(parent_obj, dict) else None
                if isinstance(cid, str):
                    parent_map[cid] = pid if isinstance(pid, str) else None

            comment_metas: list[RefreshCommentMeta] = []
            thread_metas: list[RefreshThreadMeta] = []
            seen_roots: set[str] = set()

            for node in nodes:
                cid = node.get("id")
                if not isinstance(cid, str):
                    continue
                parent_obj = node.get("parent")
                pid = parent_obj.get("id") if isinstance(parent_obj, dict) else None
                updated = node.get("updatedAt")
                resolved_at = node.get("resolvedAt")

                root_cid = _resolve_root_comment(cid, parent_map)

                comment_metas.append(
                    RefreshCommentMeta(
                        comment_id=CommentId(cid),
                        root_comment_id=CommentId(root_cid),
                        parent_comment_id=CommentId(pid) if isinstance(pid, str) else None,
                        updated_at=Timestamp(str(updated)) if updated else None,
                        deleted=False,
                    )
                )

                # Record thread resolution for root comments.
                if root_cid == cid and cid not in seen_roots:
                    seen_roots.add(cid)
                    thread_metas.append(
                        RefreshThreadMeta(
                            root_comment_id=CommentId(cid),
                            resolved=resolved_at is not None,
                        )
                    )

            return uid, (comment_metas, thread_metas)

        try:
            pairs = await asyncio.gather(*(fetch_one(uid) for uid in unique_ids))
        except Exception as exc:
            raise SystemicRemoteError(
                f"Systemic failure during comment metadata batch read: {exc}"
            ) from exc

        return dict(pairs)

    async def get_refresh_relation_metadata(
        self, issue_ids: Sequence[IssueId]
    ) -> dict[IssueId, list[RelationData]]:
        """
        Batch-read relation metadata for ``relations_signature``.

        Fans out raw-GraphQL paginated queries for forward and inverse links
        per issue.  The result shape matches :meth:`get_ticket_relations`.

        Parameters
        ----------
        issue_ids:
            Sequence of stable issue UUIDs.  Duplicates are tolerated.

        Returns
        -------
        dict[IssueId, list[RelationData]]

        Raises
        ------
        SystemicRemoteError
            If a systemic upstream failure prevents the batch read.
        """
        unique_ids = list(dict.fromkeys(issue_ids))
        if not unique_ids:
            return {}

        async def fetch_one(uid: IssueId) -> tuple[IssueId, list[RelationData]]:
            uid_str = str(uid)
            try:
                forward_nodes, inverse_nodes = await asyncio.gather(
                    self._linear.gql.paginate_connection(
                        document=_REFRESH_FORWARD_LINKS_QUERY,
                        variables={"issueId": uid_str},
                        connection_path=["issue", "relations"],
                    ),
                    self._linear.gql.paginate_connection(
                        document=_REFRESH_INVERSE_LINKS_QUERY,
                        variables={"issueId": uid_str},
                        connection_path=["issue", "inverseRelations"],
                    ),
                )
            except Exception:
                logger.debug("get_refresh_relation_metadata: skipping %s (error)", uid)
                return uid, []

            relations: list[RelationData] = []

            for node in forward_nodes:
                link_type = node.get("type")
                target = node.get("relatedIssue")
                if not isinstance(link_type, str) or not isinstance(target, dict):
                    continue
                tid = target.get("id")
                tkey = target.get("identifier")
                if isinstance(tid, str) and isinstance(tkey, str):
                    relations.append(
                        _normalize_link(link_type, is_forward=True, target_id=tid, target_key=tkey)
                    )

            for node in inverse_nodes:
                link_type = node.get("type")
                source = node.get("issue")
                if not isinstance(link_type, str) or not isinstance(source, dict):
                    continue
                sid = source.get("id")
                skey = source.get("identifier")
                if isinstance(sid, str) and isinstance(skey, str):
                    relations.append(
                        _normalize_link(link_type, is_forward=False, target_id=sid, target_key=skey)
                    )

            return uid, relations

        try:
            pairs = await asyncio.gather(*(fetch_one(uid) for uid in unique_ids))
        except Exception as exc:
            raise SystemicRemoteError(
                f"Systemic failure during relation metadata batch read: {exc}"
            ) from exc

        return dict(pairs)

    # -- Internal helpers ----------------------------------------------------

    async def _fetch_issue_supplementary(
        self, issue_id: str
    ) -> tuple[WorkspaceIdentity, list[str], IssueId | None, IssueKey | None, int | None]:
        """
        Fetch workspace identity, labels, parent, and priority for one issue.

        Returns
        -------
        tuple
            ``(workspace, labels, parent_issue_id, parent_issue_key, priority)``
        """
        result = await self._linear.gql.query(
            _ISSUE_SUPPLEMENTARY_QUERY,
            {"issueId": issue_id},
            operation_name="IssueSupplement",
        )
        data = result.get("data", {})
        if not isinstance(data, dict):
            data = {}
        issue_obj = data.get("issue", {})
        if not isinstance(issue_obj, dict):
            issue_obj = {}

        workspace = self._extract_workspace(result, IssueId(issue_id))

        # Labels: normalize to "Group / Label" sorted strings.
        labels_conn = issue_obj.get("labels", {})
        label_nodes = labels_conn.get("nodes", []) if isinstance(labels_conn, dict) else []
        labels: list[str] = []
        for lnode in label_nodes:
            if not isinstance(lnode, dict):
                continue
            name = lnode.get("name")
            if not isinstance(name, str):
                continue
            parent_obj = lnode.get("parent")
            parent_name: str | None = None
            if isinstance(parent_obj, dict):
                pn = parent_obj.get("name")
                parent_name = pn if isinstance(pn, str) else None
            labels.append(_render_label(name, parent_name))
        labels.sort()

        # Parent issue.
        parent_obj = issue_obj.get("parent")
        parent_issue_id: IssueId | None = None
        parent_issue_key: IssueKey | None = None
        if isinstance(parent_obj, dict):
            pid = parent_obj.get("id")
            pkey = parent_obj.get("identifier")
            if isinstance(pid, str):
                parent_issue_id = IssueId(pid)
            if isinstance(pkey, str):
                parent_issue_key = IssueKey(pkey)

        # Priority.
        raw_priority = issue_obj.get("priority")
        priority: int | None = raw_priority if isinstance(raw_priority, int) else None

        return workspace, labels, parent_issue_id, parent_issue_key, priority

    def _extract_workspace(
        self, gql_result: dict[str, Any], issue_id: IssueId
    ) -> WorkspaceIdentity:
        """
        Extract ``WorkspaceIdentity`` from a raw GraphQL result that includes
        ``issue { team { organization { id urlKey } } }``.
        """
        data = gql_result.get("data", {})
        if not isinstance(data, dict):
            data = {}
        issue_obj = data.get("issue", {})
        if not isinstance(issue_obj, dict):
            raise RootNotFoundError(f"Issue not found: {issue_id!r}")
        team_obj = issue_obj.get("team", {})
        if not isinstance(team_obj, dict):
            raise SystemicRemoteError(
                f"Issue {issue_id!r} has no team — cannot determine workspace"
            )
        org_obj = team_obj.get("organization", {})
        if not isinstance(org_obj, dict):
            raise SystemicRemoteError(
                f"Issue {issue_id!r} team has no organization — cannot determine workspace"
            )
        ws_id = org_obj.get("id")
        ws_slug = org_obj.get("urlKey")
        if not isinstance(ws_id, str) or not isinstance(ws_slug, str):
            raise SystemicRemoteError(f"Workspace identity incomplete for issue {issue_id!r}")
        return WorkspaceIdentity(
            workspace_id=WorkspaceId(ws_id),
            workspace_slug=WorkspaceSlug(ws_slug),
        )

    def _flatten_comments(
        self, root_comments: list[Any]
    ) -> tuple[list[CommentData], list[ThreadData]]:
        """
        Flatten the domain-layer root-thread comment tree into
        ``(comments, threads)`` lists suitable for ``TicketBundle``.

        Handles ``Comment.is_placeholder()`` synthetic parents by promoting
        each visible child of a placeholder into its own top-level thread root.
        """
        comments: list[CommentData] = []
        threads: list[ThreadData] = []

        def walk(comment: Any, effective_parent_id: CommentId | None) -> None:  # noqa: ANN401
            """Recursively walk a comment and its children."""
            is_placeholder = comment.is_placeholder()
            cid_raw = comment.peek_id()
            if cid_raw is None:
                return
            cid = CommentId(str(cid_raw))

            if not is_placeholder:
                body = comment.peek_body() or ""
                author_obj = comment.peek_author()
                author_name: str | None = None
                if author_obj is not None:
                    author_name = author_obj.peek_name()
                created = comment.peek_created_at()
                updated = comment.peek_updated_at()

                comments.append(
                    CommentData(
                        comment_id=cid,
                        body=body,
                        author=author_name,
                        created_at=Timestamp(str(created)) if created else Timestamp(""),
                        updated_at=Timestamp(str(updated)) if updated else None,
                        parent_comment_id=effective_parent_id,
                    )
                )

                # Record thread metadata for root-level comments.
                if effective_parent_id is None:
                    resolved_at = comment.peek_is_resolved()
                    threads.append(
                        ThreadData(
                            root_comment_id=cid,
                            resolved=bool(resolved_at),
                        )
                    )

            # Walk children.
            children = comment.peek_children() or []
            for child in children:
                if is_placeholder:
                    # Promote visible children of placeholders to top-level roots.
                    walk(child, None)
                else:
                    walk(child, cid)

        for root in root_comments:
            walk(root, None)

        return comments, threads

    def _convert_attachments(self, attachments: list[Any]) -> list[AttachmentData]:  # noqa: ANN401
        """Convert domain-layer ``Attachment`` objects to ``AttachmentData``."""
        result: list[AttachmentData] = []
        for att in attachments:
            aid = att.peek_id()
            if aid is None:
                continue
            url = att.peek_url()
            created = att.peek_created_at()
            title = att.peek_title()
            uploader = getattr(att, "uploader", None)
            creator_name: str | None = None
            if uploader is not None:
                creator_name = uploader.peek_name()
            result.append(
                AttachmentData(
                    attachment_id=AttachmentId(str(aid)),
                    title=title,
                    url=str(url) if url else "",
                    created_at=Timestamp(str(created)) if created else Timestamp(""),
                    creator=creator_name,
                )
            )
        return result

    def _normalize_links(
        self,
        links: list[Any],
        current_issue_id: str,  # noqa: ANN401
    ) -> list[RelationData]:
        """
        Normalize ``IssueLink`` domain objects into ``RelationData`` values.

        Determines forward/inverse direction by comparing the link's
        ``from_issue.id`` against the current issue id.
        """
        result: list[RelationData] = []
        for link in links:
            link_type_val = link.peek_link_type()
            if link_type_val is None:
                continue
            link_type = str(link_type_val)

            from_issue = link.from_issue
            to_issue = link.to_issue
            if from_issue is None or to_issue is None:
                continue

            from_id = from_issue.peek_id()
            to_id = to_issue.peek_id()
            if from_id is None or to_id is None:
                continue

            is_forward = str(from_id) == current_issue_id
            if is_forward:
                target_id = str(to_id)
                target_key_val = to_issue.peek_key()
            else:
                target_id = str(from_id)
                target_key_val = from_issue.peek_key()

            target_key = str(target_key_val) if target_key_val else ""
            result.append(
                _normalize_link(
                    link_type, is_forward=is_forward, target_id=target_id, target_key=target_key
                )
            )
        return result
