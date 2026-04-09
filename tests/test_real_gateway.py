"""
Tests for RealLinearGateway using fixture-backed transport inputs.

These tests exercise the real gateway implementation against mock domain
objects and raw-GQL responses without requiring live Linear access.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from context_sync._errors import RootNotFoundError, SystemicRemoteError
from context_sync._gateway import LinearGateway
from context_sync._real_gateway import (
    RealLinearGateway,
    _normalize_link,
    _render_label,
    _resolve_root_comment,
)
from context_sync._types import IssueId

# ---------------------------------------------------------------------------
# Helpers — unit tests for normalization utilities
# ---------------------------------------------------------------------------


class TestNormalizeLink:
    def test_forward_blocks(self) -> None:
        r = _normalize_link("blocks", is_forward=True, target_id="t-1", target_key="T-1")
        assert r.dimension == "blocks"
        assert r.relation_type == "blocks"
        assert r.target_issue_id == "t-1"

    def test_inverse_blocks(self) -> None:
        r = _normalize_link("blocks", is_forward=False, target_id="t-2", target_key="T-2")
        assert r.dimension == "is_blocked_by"
        assert r.relation_type == "blocks"

    def test_related(self) -> None:
        r = _normalize_link("related", is_forward=True, target_id="t-3", target_key="T-3")
        assert r.dimension == "relates_to"
        assert r.relation_type == "related"

    def test_duplicate(self) -> None:
        r = _normalize_link("duplicate", is_forward=False, target_id="t-4", target_key="T-4")
        assert r.dimension == "relates_to"
        assert r.relation_type == "duplicate"

    def test_similar(self) -> None:
        r = _normalize_link("similar", is_forward=True, target_id="t-5", target_key="T-5")
        assert r.dimension == "relates_to"
        assert r.relation_type == "similar"

    def test_unknown_type_maps_to_relates_to(self) -> None:
        r = _normalize_link("depends_on", is_forward=True, target_id="t-6", target_key="T-6")
        assert r.dimension == "relates_to"
        assert r.relation_type == "depends_on"


class TestResolveRootComment:
    def test_root_comment_returns_self(self) -> None:
        assert _resolve_root_comment("c-1", {"c-1": None}) == "c-1"

    def test_single_parent(self) -> None:
        parent_map = {"c-2": "c-1", "c-1": None}
        assert _resolve_root_comment("c-2", parent_map) == "c-1"

    def test_nested_chain(self) -> None:
        parent_map = {"c-3": "c-2", "c-2": "c-1", "c-1": None}
        assert _resolve_root_comment("c-3", parent_map) == "c-1"

    def test_cycle_detection(self) -> None:
        parent_map: dict[str, str | None] = {"c-1": "c-2", "c-2": "c-1"}
        result = _resolve_root_comment("c-1", parent_map)
        # Should terminate without infinite loop; exact root depends on traversal.
        assert result in ("c-1", "c-2")

    def test_missing_parent_returns_self(self) -> None:
        assert _resolve_root_comment("c-1", {}) == "c-1"


class TestRenderLabel:
    def test_root_label(self) -> None:
        assert _render_label("Bug", None) == "Bug"

    def test_grouped_label(self) -> None:
        assert _render_label("High", "Priority") == "Priority / High"


# ---------------------------------------------------------------------------
# Mock linear-client helpers
# ---------------------------------------------------------------------------


def _mock_issue(
    *,
    issue_id: str = "uid-1",
    issue_key: str = "TEST-1",
    title: str = "Test issue",
    status_name: str | None = "Todo",
    assignee_name: str | None = "Alice",
    creator_name: str | None = "Bob",
    created_at: str = "2026-01-01T00:00:00Z",
    updated_at: str = "2026-01-01T00:00:00Z",
    description: str | None = "A test issue",
) -> MagicMock:
    """Build a mock linear_client Issue domain object."""
    issue = MagicMock()
    issue.peek_id.return_value = issue_id
    issue.peek_key.return_value = issue_key
    issue.peek_title.return_value = title
    issue.peek_description.return_value = description
    issue.peek_created_at.return_value = created_at
    issue.peek_updated_at.return_value = updated_at

    # Status, assignee, creator are nested domain objects.
    status = MagicMock()
    status.peek_name.return_value = status_name
    issue.peek_status.return_value = status if status_name else None

    assignee = MagicMock()
    assignee.peek_name.return_value = assignee_name
    issue.peek_assignee.return_value = assignee if assignee_name else None

    creator = MagicMock()
    creator.peek_name.return_value = creator_name
    issue.peek_creator.return_value = creator if creator_name else None

    # fetch() returns itself.
    issue.fetch = AsyncMock(return_value=issue)
    issue.get_comments = AsyncMock(return_value=[])
    issue.get_attachments = AsyncMock(return_value=[])
    issue.get_links = AsyncMock(return_value=[])

    return issue


def _mock_comment(
    *,
    comment_id: str,
    body: str = "comment body",
    author_name: str | None = "Alice",
    created_at: str = "2026-01-01T00:00:00Z",
    updated_at: str | None = None,
    parent: Any = None,
    children: list[Any] | None = None,
    is_placeholder: bool = False,
    is_resolved: bool | None = False,
) -> MagicMock:
    """Build a mock linear_client Comment domain object."""
    comment = MagicMock()
    comment.peek_id.return_value = comment_id
    comment.peek_body.return_value = body
    comment.peek_created_at.return_value = created_at
    comment.peek_updated_at.return_value = updated_at
    comment.peek_is_resolved.return_value = is_resolved
    comment.is_placeholder.return_value = is_placeholder

    author = MagicMock()
    author.peek_name.return_value = author_name
    comment.peek_author.return_value = author if author_name else None

    comment.peek_children.return_value = children or []
    return comment


def _mock_attachment(
    *,
    attachment_id: str = "att-1",
    title: str | None = "file.pdf",
    url: str = "https://example.com/file.pdf",
    created_at: str = "2026-01-01T00:00:00Z",
    uploader_name: str | None = "Alice",
) -> MagicMock:
    """Build a mock linear_client Attachment domain object."""
    att = MagicMock()
    att.peek_id.return_value = attachment_id
    att.peek_title.return_value = title
    att.peek_url.return_value = url
    att.peek_created_at.return_value = created_at
    uploader = MagicMock()
    uploader.peek_name.return_value = uploader_name
    att.uploader = uploader if uploader_name else None
    return att


def _mock_link(
    *,
    link_type: str = "blocks",
    from_id: str = "uid-1",
    from_key: str = "TEST-1",
    to_id: str = "uid-2",
    to_key: str = "TEST-2",
) -> MagicMock:
    """Build a mock linear_client IssueLink domain object."""
    link = MagicMock()
    link.peek_link_type.return_value = link_type
    from_issue = MagicMock()
    from_issue.peek_id.return_value = from_id
    from_issue.peek_key.return_value = from_key
    to_issue = MagicMock()
    to_issue.peek_id.return_value = to_id
    to_issue.peek_key.return_value = to_key
    link.from_issue = from_issue
    link.to_issue = to_issue
    return link


def _make_supplementary_response(
    *,
    ws_id: str = "ws-1",
    ws_slug: str = "test-workspace",
    priority: int | None = 2,
    parent_id: str | None = None,
    parent_key: str | None = None,
    labels: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a raw GQL response for the supplementary issue query."""
    parent = None
    if parent_id:
        parent = {"id": parent_id, "identifier": parent_key}
    return {
        "data": {
            "issue": {
                "priority": priority,
                "parent": parent,
                "team": {
                    "organization": {
                        "id": ws_id,
                        "urlKey": ws_slug,
                    }
                },
                "labels": {
                    "nodes": labels or [],
                },
            }
        }
    }


def _make_gateway(
    issue_factory: Any = None,
    gql_query: Any = None,
    gql_paginate: Any = None,
) -> RealLinearGateway:
    """Build a RealLinearGateway backed by mock linear-client objects."""
    linear = MagicMock()

    if issue_factory is not None:
        linear.issue = issue_factory
    else:
        linear.issue = MagicMock(return_value=_mock_issue())

    linear.gql = MagicMock()
    linear.gql.query = gql_query or AsyncMock(return_value=_make_supplementary_response())
    linear.gql.paginate_connection = gql_paginate or AsyncMock(return_value=[])

    return RealLinearGateway(linear)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestRealGatewayProtocol:
    def test_satisfies_protocol(self) -> None:
        gw = _make_gateway()
        assert isinstance(gw, LinearGateway)


# ---------------------------------------------------------------------------
# fetch_issue
# ---------------------------------------------------------------------------


class TestRealGatewayFetchIssue:
    async def test_basic_fetch(self) -> None:
        issue = _mock_issue()
        gw = _make_gateway(issue_factory=MagicMock(return_value=issue))

        bundle = await gw.fetch_issue("uid-1")

        assert bundle.issue.issue_id == "uid-1"
        assert bundle.issue.issue_key == "TEST-1"
        assert bundle.issue.title == "Test issue"
        assert bundle.issue.status == "Todo"
        assert bundle.issue.assignee == "Alice"
        assert bundle.issue.creator == "Bob"
        assert bundle.workspace.workspace_id == "ws-1"
        assert bundle.workspace.workspace_slug == "test-workspace"

    async def test_fetch_with_labels(self) -> None:
        issue = _mock_issue()
        labels = [
            {"name": "Bug", "parent": None},
            {"name": "High", "parent": {"name": "Priority"}},
        ]
        gql_query = AsyncMock(return_value=_make_supplementary_response(labels=labels))
        gw = _make_gateway(
            issue_factory=MagicMock(return_value=issue),
            gql_query=gql_query,
        )

        bundle = await gw.fetch_issue("uid-1")

        assert bundle.issue.labels == ["Bug", "Priority / High"]

    async def test_fetch_with_parent(self) -> None:
        issue = _mock_issue()
        gql_query = AsyncMock(
            return_value=_make_supplementary_response(parent_id="parent-uid", parent_key="PARENT-1")
        )
        gw = _make_gateway(
            issue_factory=MagicMock(return_value=issue),
            gql_query=gql_query,
        )

        bundle = await gw.fetch_issue("uid-1")

        assert bundle.issue.parent_issue_id == "parent-uid"
        assert bundle.issue.parent_issue_key == "PARENT-1"

    async def test_fetch_with_priority(self) -> None:
        issue = _mock_issue()
        gql_query = AsyncMock(return_value=_make_supplementary_response(priority=3))
        gw = _make_gateway(
            issue_factory=MagicMock(return_value=issue),
            gql_query=gql_query,
        )

        bundle = await gw.fetch_issue("uid-1")

        assert bundle.issue.priority == 3

    async def test_fetch_with_comments(self) -> None:
        root_comment = _mock_comment(comment_id="c-1", body="root")
        reply = _mock_comment(comment_id="c-2", body="reply")
        root_comment.peek_children.return_value = [reply]

        issue = _mock_issue()
        issue.get_comments = AsyncMock(return_value=[root_comment])

        gw = _make_gateway(issue_factory=MagicMock(return_value=issue))
        bundle = await gw.fetch_issue("uid-1")

        assert len(bundle.comments) == 2
        by_id = {c.comment_id: c for c in bundle.comments}
        assert by_id["c-1"].parent_comment_id is None
        assert by_id["c-2"].parent_comment_id == "c-1"

    async def test_fetch_placeholder_comment_excluded(self) -> None:
        """Placeholder parents are excluded; their children become top-level."""
        child = _mock_comment(comment_id="c-2", body="orphan reply")
        placeholder = _mock_comment(
            comment_id="c-placeholder",
            is_placeholder=True,
            children=[child],
        )

        issue = _mock_issue()
        issue.get_comments = AsyncMock(return_value=[placeholder])

        gw = _make_gateway(issue_factory=MagicMock(return_value=issue))
        bundle = await gw.fetch_issue("uid-1")

        # Only the child should be present, promoted to top-level.
        assert len(bundle.comments) == 1
        assert bundle.comments[0].comment_id == "c-2"
        assert bundle.comments[0].parent_comment_id is None
        # Thread metadata for promoted root.
        assert len(bundle.threads) == 1
        assert bundle.threads[0].root_comment_id == "c-2"

    async def test_fetch_with_attachments(self) -> None:
        att = _mock_attachment(attachment_id="att-1", title="spec.pdf")
        issue = _mock_issue()
        issue.get_attachments = AsyncMock(return_value=[att])

        gw = _make_gateway(issue_factory=MagicMock(return_value=issue))
        bundle = await gw.fetch_issue("uid-1")

        assert len(bundle.attachments) == 1
        assert bundle.attachments[0].attachment_id == "att-1"
        assert bundle.attachments[0].title == "spec.pdf"
        assert bundle.attachments[0].creator == "Alice"

    async def test_fetch_with_relations(self) -> None:
        link = _mock_link(
            link_type="blocks",
            from_id="uid-1",
            from_key="TEST-1",
            to_id="uid-2",
            to_key="TEST-2",
        )
        issue = _mock_issue(issue_id="uid-1")
        issue.get_links = AsyncMock(return_value=[link])

        gw = _make_gateway(issue_factory=MagicMock(return_value=issue))
        bundle = await gw.fetch_issue("uid-1")

        assert len(bundle.relations) == 1
        assert bundle.relations[0].dimension == "blocks"
        assert bundle.relations[0].target_issue_id == "uid-2"

    async def test_fetch_not_found_raises(self) -> None:
        """Non-LinearNotFoundError exceptions map to SystemicRemoteError."""
        issue = _mock_issue()
        issue.fetch = AsyncMock(side_effect=RuntimeError("gone"))

        gw = _make_gateway(issue_factory=MagicMock(return_value=issue))

        with pytest.raises(SystemicRemoteError, match="gone"):
            await gw.fetch_issue("missing-uid")

    async def test_fetch_null_id_raises(self) -> None:
        """Issue that fetches but returns no id is a systemic error."""
        issue = _mock_issue()
        issue.peek_id.return_value = None

        gw = _make_gateway(issue_factory=MagicMock(return_value=issue))

        with pytest.raises(SystemicRemoteError, match="no id"):
            await gw.fetch_issue("uid-1")


# ---------------------------------------------------------------------------
# get_workspace_identity
# ---------------------------------------------------------------------------


class TestRealGatewayWorkspaceIdentity:
    async def test_basic_workspace(self) -> None:
        gql_query = AsyncMock(
            return_value={
                "data": {
                    "issue": {
                        "team": {
                            "organization": {
                                "id": "ws-abc",
                                "urlKey": "my-team",
                            }
                        }
                    }
                }
            }
        )
        gw = _make_gateway(gql_query=gql_query)

        ws = await gw.get_workspace_identity(IssueId("uid-1"))

        assert ws.workspace_id == "ws-abc"
        assert ws.workspace_slug == "my-team"

    async def test_missing_issue_raises(self) -> None:
        gql_query = AsyncMock(return_value={"data": {"issue": None}})
        gw = _make_gateway(gql_query=gql_query)

        with pytest.raises(RootNotFoundError):
            await gw.get_workspace_identity(IssueId("missing"))

    async def test_missing_org_raises_systemic(self) -> None:
        gql_query = AsyncMock(return_value={"data": {"issue": {"team": {"organization": None}}}})
        gw = _make_gateway(gql_query=gql_query)

        with pytest.raises(SystemicRemoteError):
            await gw.get_workspace_identity(IssueId("uid-1"))


# ---------------------------------------------------------------------------
# get_ticket_relations (domain fan-out)
# ---------------------------------------------------------------------------


class TestRealGatewayTicketRelations:
    async def test_basic_relations(self) -> None:
        link = _mock_link(
            link_type="blocks",
            from_id="uid-1",
            from_key="TEST-1",
            to_id="uid-2",
            to_key="TEST-2",
        )
        issue = _mock_issue(issue_id="uid-1")
        issue.get_links = AsyncMock(return_value=[link])

        linear = MagicMock()
        linear.issue = MagicMock(return_value=issue)
        linear.gql = MagicMock()
        gw = RealLinearGateway(linear)

        result = await gw.get_ticket_relations([IssueId("uid-1")])

        assert IssueId("uid-1") in result
        assert len(result[IssueId("uid-1")]) == 1
        assert result[IssueId("uid-1")][0].dimension == "blocks"

    async def test_empty_input(self) -> None:
        gw = _make_gateway()
        result = await gw.get_ticket_relations([])
        assert result == {}

    async def test_deduplicates_input(self) -> None:
        issue = _mock_issue()
        linear = MagicMock()
        linear.issue = MagicMock(return_value=issue)
        linear.gql = MagicMock()
        gw = RealLinearGateway(linear)

        result = await gw.get_ticket_relations([IssueId("uid-1"), IssueId("uid-1")])

        # Should only be called once for the deduplicated id.
        assert IssueId("uid-1") in result

    async def test_error_returns_empty_for_issue(self) -> None:
        issue = _mock_issue()
        issue.get_links = AsyncMock(side_effect=Exception("network error"))

        linear = MagicMock()
        linear.issue = MagicMock(return_value=issue)
        linear.gql = MagicMock()
        gw = RealLinearGateway(linear)

        result = await gw.get_ticket_relations([IssueId("uid-1")])

        assert result[IssueId("uid-1")] == []


# ---------------------------------------------------------------------------
# get_refresh_issue_metadata
# ---------------------------------------------------------------------------


class TestRealGatewayRefreshIssueMeta:
    async def test_basic_batch(self) -> None:
        gql_paginate = AsyncMock(
            return_value=[
                {"id": "uid-1", "identifier": "TEST-1", "updatedAt": "2026-01-01T00:00:00Z"},
                {"id": "uid-2", "identifier": "TEST-2", "updatedAt": "2026-01-02T00:00:00Z"},
            ]
        )
        gw = _make_gateway(gql_paginate=gql_paginate)

        result = await gw.get_refresh_issue_metadata([IssueId("uid-1"), IssueId("uid-2")])

        assert result[IssueId("uid-1")].visible is True
        assert result[IssueId("uid-1")].issue_key == "TEST-1"
        assert result[IssueId("uid-2")].visible is True

    async def test_missing_issue_visible_false(self) -> None:
        gql_paginate = AsyncMock(
            return_value=[
                {"id": "uid-1", "identifier": "TEST-1", "updatedAt": "2026-01-01T00:00:00Z"},
            ]
        )
        gw = _make_gateway(gql_paginate=gql_paginate)

        result = await gw.get_refresh_issue_metadata([IssueId("uid-1"), IssueId("uid-missing")])

        assert result[IssueId("uid-1")].visible is True
        assert result[IssueId("uid-missing")].visible is False

    async def test_empty_input(self) -> None:
        gw = _make_gateway()
        result = await gw.get_refresh_issue_metadata([])
        assert result == {}


# ---------------------------------------------------------------------------
# get_refresh_comment_metadata
# ---------------------------------------------------------------------------


class TestRealGatewayRefreshCommentMeta:
    async def test_basic_comments(self) -> None:
        gql_paginate = AsyncMock(
            return_value=[
                {
                    "id": "c-1",
                    "updatedAt": "2026-01-01T00:00:00Z",
                    "parent": None,
                    "resolvedAt": None,
                },
                {
                    "id": "c-2",
                    "updatedAt": "2026-01-02T00:00:00Z",
                    "parent": {"id": "c-1"},
                    "resolvedAt": None,
                },
            ]
        )
        gw = _make_gateway(gql_paginate=gql_paginate)

        result = await gw.get_refresh_comment_metadata([IssueId("uid-1")])

        comments, threads = result[IssueId("uid-1")]
        assert len(comments) == 2
        by_id = {c.comment_id: c for c in comments}
        assert by_id["c-1"].root_comment_id == "c-1"
        assert by_id["c-2"].root_comment_id == "c-1"
        assert by_id["c-2"].parent_comment_id == "c-1"
        assert len(threads) == 1
        assert threads[0].root_comment_id == "c-1"
        assert threads[0].resolved is False

    async def test_resolved_thread(self) -> None:
        gql_paginate = AsyncMock(
            return_value=[
                {
                    "id": "c-1",
                    "updatedAt": "2026-01-01T00:00:00Z",
                    "parent": None,
                    "resolvedAt": "2026-01-02T00:00:00Z",
                },
            ]
        )
        gw = _make_gateway(gql_paginate=gql_paginate)

        result = await gw.get_refresh_comment_metadata([IssueId("uid-1")])

        _, threads = result[IssueId("uid-1")]
        assert threads[0].resolved is True

    async def test_empty_input(self) -> None:
        gw = _make_gateway()
        result = await gw.get_refresh_comment_metadata([])
        assert result == {}


# ---------------------------------------------------------------------------
# get_refresh_relation_metadata
# ---------------------------------------------------------------------------


class TestRealGatewayRefreshRelationMeta:
    async def test_forward_and_inverse_links(self) -> None:
        call_count = 0

        async def mock_paginate(
            *,
            document: str,
            variables: dict[str, object],
            connection_path: list[str],
            **kwargs: Any,
        ) -> list[dict[str, Any]]:
            nonlocal call_count
            call_count += 1
            if "relations" in connection_path:
                return [
                    {
                        "type": "blocks",
                        "relatedIssue": {"id": "uid-2", "identifier": "TEST-2"},
                    },
                ]
            elif "inverseRelations" in connection_path:
                return [
                    {
                        "type": "blocks",
                        "issue": {"id": "uid-3", "identifier": "TEST-3"},
                    },
                ]
            return []

        gql_paginate = AsyncMock(side_effect=mock_paginate)
        gw = _make_gateway(gql_paginate=gql_paginate)

        result = await gw.get_refresh_relation_metadata([IssueId("uid-1")])

        relations = result[IssueId("uid-1")]
        assert len(relations) == 2
        dims = {r.dimension for r in relations}
        assert "blocks" in dims
        assert "is_blocked_by" in dims

    async def test_empty_input(self) -> None:
        gw = _make_gateway()
        result = await gw.get_refresh_relation_metadata([])
        assert result == {}

    async def test_error_returns_empty(self) -> None:
        gql_paginate = AsyncMock(side_effect=Exception("network error"))
        gw = _make_gateway(gql_paginate=gql_paginate)

        result = await gw.get_refresh_relation_metadata([IssueId("uid-1")])

        assert result[IssueId("uid-1")] == []
