"""
Reusable fake-client test harness and fixture builders.

This module establishes the testing contract that later integration tests
extend instead of inventing one-off mocks per ticket.  It provides:

* :class:`FakeLinearGateway` — an in-memory ``LinearGateway`` implementation
  backed by pre-loaded :class:`TicketBundle` objects.
* :func:`make_issue` — a builder that constructs a :class:`TicketBundle` with
  sensible defaults so tests only specify the fields they care about.
* :func:`make_context_sync` — a factory that wires a :class:`FakeLinearGateway`
  into a :class:`ContextSync` for use in integration tests.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from context_sync._config import (
    DEFAULT_CONCURRENCY_LIMIT,
    DEFAULT_DIMENSIONS,
    DEFAULT_MAX_TICKETS_PER_ROOT,
)
from context_sync._errors import RootNotFoundError
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
from context_sync._manifest import Manifest, ManifestSnapshot, initialize_manifest
from context_sync._renderer import resolve_root_comment
from context_sync._sync import ContextSync
from context_sync._types import (
    CommentId,
    IssueId,
    IssueKey,
    Timestamp,
    WorkspaceId,
    WorkspaceSlug,
)

# ---------------------------------------------------------------------------
# Default workspace used by the fake
# ---------------------------------------------------------------------------

DEFAULT_FAKE_WORKSPACE = WorkspaceIdentity(
    workspace_id=WorkspaceId("ws-fake-00000000"),
    workspace_slug=WorkspaceSlug("fake-workspace"),
)

_DEFAULT_ISSUE_ID: IssueId = IssueId("00000000-0000-0000-0000-000000000001")
_DEFAULT_ISSUE_KEY: IssueKey = IssueKey("TEST-1")
_DEFAULT_TIMESTAMP: Timestamp = Timestamp("2026-01-01T00:00:00Z")


# ---------------------------------------------------------------------------
# Ticket bundle builder
# ---------------------------------------------------------------------------


def make_issue(
    *,
    issue_id: IssueId = _DEFAULT_ISSUE_ID,
    issue_key: IssueKey = _DEFAULT_ISSUE_KEY,
    title: str = "Test issue",
    status: str | None = "Todo",
    assignee: str | None = None,
    creator: str | None = "test-user",
    priority: int | None = None,
    description: str | None = "Test description.",
    created_at: Timestamp = _DEFAULT_TIMESTAMP,
    updated_at: Timestamp = _DEFAULT_TIMESTAMP,
    parent_issue_id: IssueId | None = None,
    parent_issue_key: IssueKey | None = None,
    labels: list[str] | None = None,
    workspace: WorkspaceIdentity | None = None,
    comments: list[CommentData] | None = None,
    threads: list[ThreadData] | None = None,
    attachments: list[AttachmentData] | None = None,
    relations: list[RelationData] | None = None,
) -> TicketBundle:
    """
    Build a :class:`TicketBundle` with sensible defaults.

    Callers only need to supply the fields relevant to their test scenario;
    everything else gets a safe default.  This is the canonical fixture
    builder that later tickets should extend rather than constructing raw
    ``TicketBundle`` objects directly.

    Returns
    -------
    TicketBundle
    """
    return TicketBundle(
        issue=IssueData(
            issue_id=issue_id,
            issue_key=issue_key,
            title=title,
            status=status,
            assignee=assignee,
            creator=creator,
            priority=priority,
            description=description,
            created_at=created_at,
            updated_at=updated_at,
            parent_issue_id=parent_issue_id,
            parent_issue_key=parent_issue_key,
            labels=labels or [],
        ),
        workspace=workspace or DEFAULT_FAKE_WORKSPACE,
        comments=comments or [],
        threads=threads or [],
        attachments=attachments or [],
        relations=relations or [],
    )


# ---------------------------------------------------------------------------
# Fake gateway
# ---------------------------------------------------------------------------


class FakeLinearGateway:
    """
    In-memory :class:`LinearGateway` for testing without live Linear access.

    Pre-load issues with :meth:`add_issue`, then pass this gateway to
    :func:`make_context_sync` or directly to ``ContextSync(...,
    _gateway_override=...)``.

    The fake resolves issue lookups by both UUID and issue key.  All batch
    methods return data only for issues that have been pre-loaded.
    """

    def __init__(self) -> None:
        self._bundles: dict[IssueId, TicketBundle] = {}  # keyed by issue UUID
        self._key_index: dict[IssueKey, IssueId] = {}  # issue_key → issue UUID
        self._hidden: set[IssueId] = set()  # issue UUIDs marked as not visible

    def add_issue(self, bundle: TicketBundle) -> None:
        """
        Register a :class:`TicketBundle` for later lookup.

        Parameters
        ----------
        bundle:
            The ticket data to store.  Indexed by both ``issue_id`` and
            ``issue_key``.
        """
        uid = bundle.issue.issue_id
        self._bundles[uid] = bundle
        self._key_index[bundle.issue.issue_key] = uid

    def hide_issue(self, issue_id: IssueId) -> None:
        """
        Mark a pre-loaded issue as not visible to the caller.

        The issue remains known to the fake (preserving its identity and
        metadata) but :meth:`get_refresh_issue_metadata` will return
        ``visible=False`` for it.  This models the quarantine/recovery
        scenarios required by `M3-1`_.
        """
        self._hidden.add(issue_id)

    def unhide_issue(self, issue_id: IssueId) -> None:
        """Restore visibility for a previously hidden issue."""
        self._hidden.discard(issue_id)

    # -- LinearGateway protocol methods ------------------------------------

    async def fetch_issue(self, issue_id_or_key: str) -> TicketBundle:
        """Return the pre-loaded bundle, or raise :class:`RootNotFoundError`."""
        resolved_id = self._key_index.get(IssueKey(issue_id_or_key), IssueId(issue_id_or_key))
        bundle = self._bundles.get(resolved_id)
        if bundle is None or resolved_id in self._hidden:
            raise RootNotFoundError(f"Fake issue not found: {issue_id_or_key!r}")
        return bundle

    async def get_workspace_identity(self, issue_id: IssueId) -> WorkspaceIdentity:
        """Return workspace identity for a pre-loaded issue."""
        bundle = self._bundles.get(issue_id)
        if bundle is None:
            raise RootNotFoundError(f"Fake issue not found: {issue_id!r}")
        return bundle.workspace

    async def get_ticket_relations(
        self, issue_ids: Sequence[IssueId]
    ) -> dict[IssueId, list[RelationData]]:
        """Return relations for pre-loaded issues."""
        result: dict[IssueId, list[RelationData]] = {}
        for uid in issue_ids:
            bundle = self._bundles.get(uid)
            if bundle is not None:
                result[uid] = list(bundle.relations)
        return result

    async def get_refresh_issue_metadata(
        self, issue_ids: Sequence[IssueId]
    ) -> dict[IssueId, RefreshIssueMeta]:
        """Return minimal issue metadata for freshness checks."""
        result: dict[IssueId, RefreshIssueMeta] = {}
        for uid in issue_ids:
            bundle = self._bundles.get(uid)
            if bundle is not None:
                result[uid] = RefreshIssueMeta(
                    issue_id=bundle.issue.issue_id,
                    issue_key=bundle.issue.issue_key,
                    updated_at=bundle.issue.updated_at,
                    visible=uid not in self._hidden,
                )
        return result

    async def get_refresh_comment_metadata(
        self, issue_ids: Sequence[IssueId]
    ) -> dict[IssueId, tuple[list[RefreshCommentMeta], list[RefreshThreadMeta]]]:
        """Return comment/thread metadata for pre-loaded issues."""
        result: dict[IssueId, tuple[list[RefreshCommentMeta], list[RefreshThreadMeta]]] = {}
        for uid in issue_ids:
            bundle = self._bundles.get(uid)
            if bundle is None:
                continue
            # Build a parent→root lookup by walking parent chains.
            parent_map: dict[CommentId, CommentId | None] = {
                c.comment_id: c.parent_comment_id for c in bundle.comments
            }
            comment_metas = [
                RefreshCommentMeta(
                    comment_id=c.comment_id,
                    root_comment_id=resolve_root_comment(c.comment_id, parent_map),
                    parent_comment_id=c.parent_comment_id,
                    updated_at=c.updated_at,
                    deleted=False,
                )
                for c in bundle.comments
            ]
            thread_metas = [
                RefreshThreadMeta(
                    root_comment_id=t.root_comment_id,
                    resolved=t.resolved,
                )
                for t in bundle.threads
            ]
            result[uid] = (comment_metas, thread_metas)
        return result

    async def get_refresh_relation_metadata(
        self, issue_ids: Sequence[IssueId]
    ) -> dict[IssueId, list[RelationData]]:
        """Delegates to :meth:`get_ticket_relations` (same data in the fake)."""
        return await self.get_ticket_relations(issue_ids)


# ---------------------------------------------------------------------------
# Manifest factory for tests
# ---------------------------------------------------------------------------


def make_manifest(
    *,
    workspace: WorkspaceIdentity | None = None,
    dimensions: dict[str, int] | None = None,
    max_tickets_per_root: int = 200,
    snapshot: ManifestSnapshot | None = None,
) -> Manifest:
    """
    Build a :class:`Manifest` with sensible defaults for testing.

    Returns
    -------
    Manifest
    """
    ws = workspace or DEFAULT_FAKE_WORKSPACE
    m = initialize_manifest(
        workspace=ws,
        dimensions=dimensions or dict(DEFAULT_DIMENSIONS),
        max_tickets_per_root=max_tickets_per_root,
    )
    if snapshot is not None:
        m = m.model_copy(update={"snapshot": snapshot})
    return m


# ---------------------------------------------------------------------------
# ContextSync factory for tests
# ---------------------------------------------------------------------------


def make_context_sync(
    *,
    context_dir: Path | str | None = None,
    gateway: FakeLinearGateway | None = None,
    dimensions: dict[str, int] | None = None,
    max_tickets_per_root: int = DEFAULT_MAX_TICKETS_PER_ROOT,
    concurrency_limit: int = DEFAULT_CONCURRENCY_LIMIT,
) -> ContextSync:
    """
    Create a :class:`ContextSync` backed by a :class:`FakeLinearGateway`.

    This is the canonical factory for integration tests.  Later tickets should
    use this rather than constructing ``ContextSync`` directly in test code.

    Parameters
    ----------
    context_dir:
        Target directory for the snapshot.  Defaults to a ``"test-context"``
        subdirectory that tests should place inside a ``tmp_path`` fixture.
    gateway:
        Pre-configured :class:`FakeLinearGateway`.  Defaults to an empty one.
    dimensions:
        Dimension overrides, or ``None`` for defaults.
    max_tickets_per_root:
        Per-root ticket cap.
    concurrency_limit:
        Semaphore limit.

    Returns
    -------
    ContextSync
    """
    return ContextSync(
        context_dir=context_dir or Path("test-context"),
        dimensions=dimensions,
        max_tickets_per_root=max_tickets_per_root,
        concurrency_limit=concurrency_limit,
        _gateway_override=gateway or FakeLinearGateway(),
    )
