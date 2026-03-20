"""
Tests for the LinearGateway protocol and FakeLinearGateway contract.

These tests verify that the fake gateway implements the protocol correctly
and that the fixture builders produce valid objects.  Later tickets should
extend this file as they add gateway operations.
"""

from __future__ import annotations

import pytest

from context_sync._errors import RootNotFoundError
from context_sync._gateway import (
    AttachmentData,
    CommentData,
    IssueData,
    LinearGateway,
    RelationData,
    ThreadData,
    TicketBundle,
    WorkspaceIdentity,
)
from context_sync._testing import (
    DEFAULT_FAKE_WORKSPACE,
    FakeLinearGateway,
    make_issue,
)

# ---------------------------------------------------------------------------
# Data type construction
# ---------------------------------------------------------------------------


class TestWorkspaceIdentity:
    def test_fields(self) -> None:
        ws = WorkspaceIdentity(workspace_id="ws-1", workspace_slug="myteam")
        assert ws.workspace_id == "ws-1"
        assert ws.workspace_slug == "myteam"

    def test_frozen(self) -> None:
        ws = WorkspaceIdentity("ws-1", "myteam")
        with pytest.raises(AttributeError):
            ws.workspace_id = "ws-2"  # type: ignore[misc]


class TestIssueData:
    def test_minimal(self) -> None:
        issue = IssueData(
            issue_id="uid",
            issue_key="T-1",
            title="Test",
            status=None,
            assignee=None,
            creator=None,
            priority=None,
            description=None,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            parent_issue_id=None,
            parent_issue_key=None,
        )
        assert issue.issue_id == "uid"
        assert issue.labels == []

    def test_labels_default(self) -> None:
        issue = IssueData(
            issue_id="uid",
            issue_key="T-1",
            title="Test",
            status=None,
            assignee=None,
            creator=None,
            priority=None,
            description=None,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            parent_issue_id=None,
            parent_issue_key=None,
            labels=["Bug", "Priority / High"],
        )
        assert issue.labels == ["Bug", "Priority / High"]


class TestCommentData:
    def test_fields(self) -> None:
        c = CommentData(
            comment_id="c-1",
            body="Hello",
            author="alice",
            created_at="2026-01-01T00:00:00Z",
            updated_at=None,
            parent_comment_id=None,
        )
        assert c.comment_id == "c-1"
        assert c.parent_comment_id is None


class TestRelationData:
    def test_fields(self) -> None:
        r = RelationData(
            dimension="blocks",
            relation_type="blocks",
            target_issue_id="uid-2",
            target_issue_key="T-2",
        )
        assert r.dimension == "blocks"
        assert r.target_issue_key == "T-2"


class TestTicketBundle:
    def test_defaults(self) -> None:
        bundle = TicketBundle(
            issue=IssueData(
                issue_id="uid",
                issue_key="T-1",
                title="Test",
                status=None,
                assignee=None,
                creator=None,
                priority=None,
                description=None,
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
                parent_issue_id=None,
                parent_issue_key=None,
            ),
            workspace=WorkspaceIdentity("ws-1", "test"),
        )
        assert bundle.comments == []
        assert bundle.threads == []
        assert bundle.attachments == []
        assert bundle.relations == []


# ---------------------------------------------------------------------------
# make_issue builder
# ---------------------------------------------------------------------------


class TestMakeIssue:
    def test_defaults(self) -> None:
        bundle = make_issue()
        assert bundle.issue.issue_key == "TEST-1"
        assert bundle.issue.title == "Test issue"
        assert bundle.workspace == DEFAULT_FAKE_WORKSPACE

    def test_override_fields(self) -> None:
        bundle = make_issue(issue_key="PROJ-42", title="Custom title")
        assert bundle.issue.issue_key == "PROJ-42"
        assert bundle.issue.title == "Custom title"

    def test_custom_workspace(self) -> None:
        ws = WorkspaceIdentity("ws-custom", "custom")
        bundle = make_issue(workspace=ws)
        assert bundle.workspace.workspace_id == "ws-custom"

    def test_with_relations(self) -> None:
        rel = RelationData("blocks", "blocks", "uid-other", "OTHER-1")
        bundle = make_issue(relations=[rel])
        assert len(bundle.relations) == 1
        assert bundle.relations[0].target_issue_key == "OTHER-1"

    def test_with_comments(self) -> None:
        c = CommentData("c-1", "body", "alice", "2026-01-01T00:00:00Z", None, None)
        t = ThreadData("c-1", resolved=False)
        bundle = make_issue(comments=[c], threads=[t])
        assert len(bundle.comments) == 1
        assert len(bundle.threads) == 1

    def test_with_attachments(self) -> None:
        a = AttachmentData(
            "a-1",
            "spec.pdf",
            "https://example.com/f",
            "2026-01-01T00:00:00Z",
            None,
        )
        bundle = make_issue(attachments=[a])
        assert len(bundle.attachments) == 1


# ---------------------------------------------------------------------------
# FakeLinearGateway protocol conformance
# ---------------------------------------------------------------------------


class TestFakeLinearGatewayProtocol:
    """The fake must satisfy the LinearGateway protocol structurally."""

    def test_satisfies_protocol(self) -> None:
        gw: LinearGateway = FakeLinearGateway()
        assert gw is not None  # structural check passed at type level


class TestFakeLinearGatewayFetchIssue:
    async def test_fetch_by_id(self, populated_gateway: FakeLinearGateway) -> None:
        bundle = await populated_gateway.fetch_issue("uuid-1")
        assert bundle.issue.issue_key == "TEST-1"

    async def test_fetch_by_key(self, populated_gateway: FakeLinearGateway) -> None:
        bundle = await populated_gateway.fetch_issue("TEST-2")
        assert bundle.issue.issue_id == "uuid-2"

    async def test_fetch_missing_raises(self, fake_gateway: FakeLinearGateway) -> None:
        with pytest.raises(RootNotFoundError):
            await fake_gateway.fetch_issue("MISSING-1")


class TestFakeLinearGatewayWorkspace:
    async def test_workspace_identity(
        self, populated_gateway: FakeLinearGateway
    ) -> None:
        ws = await populated_gateway.get_workspace_identity("uuid-1")
        assert ws == DEFAULT_FAKE_WORKSPACE

    async def test_workspace_missing_raises(
        self, fake_gateway: FakeLinearGateway
    ) -> None:
        with pytest.raises(RootNotFoundError):
            await fake_gateway.get_workspace_identity("missing")


class TestFakeLinearGatewayRelations:
    async def test_returns_empty_for_no_relations(
        self, populated_gateway: FakeLinearGateway
    ) -> None:
        result = await populated_gateway.get_ticket_relations(["uuid-1"])
        assert result["uuid-1"] == []

    async def test_returns_relations(self) -> None:
        gw = FakeLinearGateway()
        rel = RelationData("blocks", "blocks", "uid-target", "TARGET-1")
        gw.add_issue(make_issue(issue_id="uid-src", relations=[rel]))

        result = await gw.get_ticket_relations(["uid-src"])
        assert len(result["uid-src"]) == 1
        assert result["uid-src"][0].target_issue_key == "TARGET-1"

    async def test_missing_issues_omitted(
        self, fake_gateway: FakeLinearGateway
    ) -> None:
        result = await fake_gateway.get_ticket_relations(["no-such-id"])
        assert "no-such-id" not in result


class TestFakeLinearGatewayRefreshMeta:
    async def test_issue_metadata(self, populated_gateway: FakeLinearGateway) -> None:
        result = await populated_gateway.get_refresh_issue_metadata(
            ["uuid-1", "uuid-2"]
        )
        assert "uuid-1" in result
        assert result["uuid-1"].visible is True
        assert result["uuid-1"].issue_key == "TEST-1"

    async def test_comment_metadata(self) -> None:
        c = CommentData(
            "c-1",
            "body",
            "alice",
            "2026-01-01T00:00:00Z",
            "2026-01-02T00:00:00Z",
            None,
        )
        t = ThreadData("c-1", resolved=True)
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="uid-x", comments=[c], threads=[t]))

        result = await gw.get_refresh_comment_metadata(["uid-x"])
        comments, threads = result["uid-x"]
        assert len(comments) == 1
        assert comments[0].comment_id == "c-1"
        assert comments[0].updated_at == "2026-01-02T00:00:00Z"
        assert len(threads) == 1
        assert threads[0].resolved is True

    async def test_relation_metadata_delegates(
        self, populated_gateway: FakeLinearGateway
    ) -> None:
        result = await populated_gateway.get_refresh_relation_metadata(["uuid-1"])
        assert result["uuid-1"] == []
