"""
Tests for the ticket fetch normalization and render pipeline.

Covers the plan-required scenarios for M2-2: refresh cursor computation,
alias retention, issue-key rename behavior, comment-thread ordering,
concurrency-limit behavior, verification mismatch handling, and
ticket-ref URL scanning.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from context_sync._errors import RootNotFoundError, WriteError
from context_sync._gateway import (
    CommentData,
    RelationData,
    ThreadData,
    TicketBundle,
)
from context_sync._manifest import ManifestTicketEntry, initialize_manifest
from context_sync._pipeline import (
    _bundle_content_texts,
    _extract_issue_keys,
    compute_refresh_cursor,
    fetch_tickets,
    make_ticket_ref_provider,
    write_ticket,
)
from context_sync._signatures import compute_comments_signature, compute_relations_signature
from context_sync._testing import DEFAULT_FAKE_WORKSPACE, FakeLinearGateway, make_issue

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rel(
    dimension: str,
    target_id: str,
    target_key: str,
    relation_type: str | None = None,
) -> RelationData:
    """Build a :class:`RelationData` with a default ``relation_type``."""
    return RelationData(
        dimension=dimension,
        relation_type=relation_type or dimension,
        target_issue_id=target_id,
        target_issue_key=target_key,
    )


def _comment(
    comment_id: str,
    body: str,
    *,
    parent_comment_id: str | None = None,
    updated_at: str | None = None,
) -> CommentData:
    """Build a :class:`CommentData` with sensible defaults."""
    return CommentData(
        comment_id=comment_id,
        body=body,
        author="test-user",
        created_at="2026-01-01T00:00:00Z",
        updated_at=updated_at,
        parent_comment_id=parent_comment_id,
    )


def _thread(root_id: str, *, resolved: bool = False) -> ThreadData:
    """Build a :class:`ThreadData`."""
    return ThreadData(root_comment_id=root_id, resolved=resolved)


def _make_manifest(
    *,
    tickets: dict[str, ManifestTicketEntry] | None = None,
    aliases: dict[str, str] | None = None,
) -> object:
    """Build an in-memory Manifest with pre-populated tickets/aliases."""
    m = initialize_manifest(
        workspace=DEFAULT_FAKE_WORKSPACE,
        dimensions={"blocks": 3},
        max_tickets_per_root=200,
    )
    if tickets:
        m.tickets.update(tickets)
    if aliases:
        m.aliases.update(aliases)
    return m


# ---------------------------------------------------------------------------
# compute_refresh_cursor
# ---------------------------------------------------------------------------


class TestComputeRefreshCursor:
    def test_no_comments_returns_correct_keys(self) -> None:
        bundle = make_issue(issue_id="i1", updated_at="2026-03-01T10:00:00Z")
        cursor = compute_refresh_cursor(bundle)
        assert set(cursor) == {"issue_updated_at", "comments_signature", "relations_signature"}

    def test_issue_updated_at_matches_bundle(self) -> None:
        bundle = make_issue(issue_id="i1", updated_at="2026-03-01T10:00:00Z")
        cursor = compute_refresh_cursor(bundle)
        assert cursor["issue_updated_at"] == "2026-03-01T10:00:00Z"

    def test_signatures_are_prefixed(self) -> None:
        bundle = make_issue(issue_id="i1")
        cursor = compute_refresh_cursor(bundle)
        assert cursor["comments_signature"].startswith("v1:")
        assert cursor["relations_signature"].startswith("v1:")

    def test_comments_signature_matches_direct_computation(self) -> None:
        from context_sync._gateway import RefreshCommentMeta, RefreshThreadMeta

        bundle = make_issue(
            issue_id="i1",
            comments=[
                _comment("c1", "hello"),
                _comment("c2", "reply", parent_comment_id="c1"),
            ],
            threads=[_thread("c1")],
        )
        cursor = compute_refresh_cursor(bundle)

        # Build expected metas the same way _pipeline does.
        expected_comments = [
            RefreshCommentMeta(
                comment_id="c1",
                root_comment_id="c1",
                parent_comment_id=None,
                updated_at=None,
                deleted=False,
            ),
            RefreshCommentMeta(
                comment_id="c2",
                root_comment_id="c1",
                parent_comment_id="c1",
                updated_at=None,
                deleted=False,
            ),
        ]
        expected_threads = [RefreshThreadMeta(root_comment_id="c1", resolved=False)]
        expected_sig = compute_comments_signature(expected_comments, expected_threads)
        assert cursor["comments_signature"] == expected_sig

    def test_relations_signature_matches_direct_computation(self) -> None:
        rels = [_rel("blocks", "t2", "T-2"), _rel("parent", "t3", "T-3")]
        bundle = make_issue(issue_id="i1", relations=rels)
        cursor = compute_refresh_cursor(bundle)
        assert cursor["relations_signature"] == compute_relations_signature(rels)

    def test_different_updated_at_produces_different_cursor(self) -> None:
        b1 = make_issue(issue_id="i1", updated_at="2026-01-01T00:00:00Z")
        b2 = make_issue(issue_id="i1", updated_at="2026-01-02T00:00:00Z")
        assert compute_refresh_cursor(b1) != compute_refresh_cursor(b2)


# ---------------------------------------------------------------------------
# fetch_tickets
# ---------------------------------------------------------------------------


class TestFetchTickets:
    async def test_fetches_all_requested_ids(self) -> None:
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="a1", issue_key="T-1"))
        gw.add_issue(make_issue(issue_id="a2", issue_key="T-2"))
        gw.add_issue(make_issue(issue_id="a3", issue_key="T-3"))
        sem = asyncio.Semaphore(10)

        result = await fetch_tickets(["a1", "a2", "a3"], gateway=gw, semaphore=sem)
        assert set(result) == {"a1", "a2", "a3"}
        assert result["a1"].issue.issue_key == "T-1"

    async def test_empty_list_returns_empty_dict(self) -> None:
        gw = FakeLinearGateway()
        result = await fetch_tickets([], gateway=gw, semaphore=asyncio.Semaphore(5))
        assert result == {}

    async def test_propagates_gateway_exception(self) -> None:
        gw = FakeLinearGateway()
        # "x1" is not loaded, so fetch_issue raises RootNotFoundError.
        sem = asyncio.Semaphore(5)
        with pytest.raises(ExceptionGroup) as exc_info:
            await fetch_tickets(["x1"], gateway=gw, semaphore=sem)
        exceptions = exc_info.value.exceptions
        assert any(isinstance(e, RootNotFoundError) for e in exceptions)

    async def test_concurrency_limit_respected(self) -> None:
        """Peak concurrent in-flight calls must not exceed the semaphore limit."""
        concurrency_limit = 2
        num_tickets = 6

        peak_concurrent: list[int] = [0]
        current_concurrent: list[int] = [0]

        class _CountingGateway(FakeLinearGateway):
            async def fetch_issue(self, issue_id_or_key: str) -> TicketBundle:
                current_concurrent[0] += 1
                peak_concurrent[0] = max(peak_concurrent[0], current_concurrent[0])
                await asyncio.sleep(0)  # yield so other tasks can start
                current_concurrent[0] -= 1
                return await super().fetch_issue(issue_id_or_key)

        gw = _CountingGateway()
        issue_ids: list[str] = []
        for i in range(num_tickets):
            uid = f"id{i}"
            gw.add_issue(make_issue(issue_id=uid, issue_key=f"T-{i}"))
            issue_ids.append(uid)

        await fetch_tickets(issue_ids, gateway=gw, semaphore=asyncio.Semaphore(concurrency_limit))
        assert peak_concurrent[0] <= concurrency_limit


# ---------------------------------------------------------------------------
# write_ticket
# ---------------------------------------------------------------------------


class TestWriteTicket:
    def test_new_ticket_writes_file(self, tmp_path: Path) -> None:
        bundle = make_issue(issue_id="n1", issue_key="NEW-1")
        manifest = _make_manifest()

        result = write_ticket(
            bundle,
            root_state=None,
            last_synced_at="2026-03-01T00:00:00Z",
            context_dir=tmp_path,
            manifest=manifest,
        )

        assert result.issue_id == "n1"
        assert result.issue_key == "NEW-1"
        assert result.previous_key is None
        assert result.file_path == "NEW-1.md"
        assert (tmp_path / "NEW-1.md").is_file()

    def test_new_ticket_updates_manifest_entry(self, tmp_path: Path) -> None:
        bundle = make_issue(issue_id="n1", issue_key="NEW-1")
        manifest = _make_manifest()

        write_ticket(
            bundle,
            root_state=None,
            last_synced_at="2026-03-01T00:00:00Z",
            context_dir=tmp_path,
            manifest=manifest,
        )

        entry = manifest.tickets.get("n1")
        assert entry is not None
        assert entry.current_key == "NEW-1"
        assert entry.current_path == "NEW-1.md"

    def test_same_key_no_alias_added(self, tmp_path: Path) -> None:
        """Alias retention: re-writing the same key must not create aliases."""
        bundle = make_issue(issue_id="s1", issue_key="SAME-1")
        manifest = _make_manifest(
            tickets={"s1": ManifestTicketEntry(current_key="SAME-1", current_path="SAME-1.md")}
        )

        write_ticket(
            bundle,
            root_state=None,
            last_synced_at="2026-03-01T00:00:00Z",
            context_dir=tmp_path,
            manifest=manifest,
        )

        assert "SAME-1" not in manifest.aliases
        result_entry = manifest.tickets["s1"]
        assert result_entry.current_key == "SAME-1"

    def test_key_rename_records_alias(self, tmp_path: Path) -> None:
        """Issue-key rename: old key must appear in manifest.aliases."""
        # Pre-create the old file so rename can operate on it.
        old_file = tmp_path / "OLD-1.md"
        old_file.write_text("old content", encoding="utf-8")

        bundle = make_issue(issue_id="r1", issue_key="NEW-1")
        manifest = _make_manifest(
            tickets={"r1": ManifestTicketEntry(current_key="OLD-1", current_path="OLD-1.md")}
        )

        result = write_ticket(
            bundle,
            root_state=None,
            last_synced_at="2026-03-01T00:00:00Z",
            context_dir=tmp_path,
            manifest=manifest,
        )

        assert result.previous_key == "OLD-1"
        assert manifest.aliases.get("OLD-1") == "r1"
        assert manifest.tickets["r1"].current_key == "NEW-1"
        assert manifest.tickets["r1"].current_path == "NEW-1.md"

    def test_key_rename_renames_file(self, tmp_path: Path) -> None:
        """Issue-key rename: old file must be absent and new file must exist."""
        old_file = tmp_path / "OLD-2.md"
        old_file.write_text("old content", encoding="utf-8")

        bundle = make_issue(issue_id="r2", issue_key="NEW-2")
        manifest = _make_manifest(
            tickets={"r2": ManifestTicketEntry(current_key="OLD-2", current_path="OLD-2.md")}
        )

        write_ticket(
            bundle,
            root_state=None,
            last_synced_at="2026-03-01T00:00:00Z",
            context_dir=tmp_path,
            manifest=manifest,
        )

        assert not old_file.exists()
        assert (tmp_path / "NEW-2.md").is_file()

    def test_key_rename_no_existing_file_is_safe(self, tmp_path: Path) -> None:
        """Rename when the old file is absent must not raise."""
        bundle = make_issue(issue_id="r3", issue_key="NEW-3")
        manifest = _make_manifest(
            tickets={"r3": ManifestTicketEntry(current_key="OLD-3", current_path="OLD-3.md")}
        )
        # OLD-3.md does not exist.
        write_ticket(
            bundle,
            root_state=None,
            last_synced_at="2026-03-01T00:00:00Z",
            context_dir=tmp_path,
            manifest=manifest,
        )
        assert (tmp_path / "NEW-3.md").is_file()
        assert manifest.aliases.get("OLD-3") == "r3"

    def test_root_ticket_writes_root_state(self, tmp_path: Path) -> None:
        """Written file must include root_state frontmatter for root tickets."""
        bundle = make_issue(issue_id="root1", issue_key="ROOT-1")
        manifest = _make_manifest()

        write_ticket(
            bundle,
            root_state="active",
            last_synced_at="2026-03-01T00:00:00Z",
            context_dir=tmp_path,
            manifest=manifest,
        )

        content = (tmp_path / "ROOT-1.md").read_text()
        assert "root_state: active" in content

    def test_comment_thread_ordering_in_written_file(self, tmp_path: Path) -> None:
        """Threaded comments must appear with the newer thread first."""
        comments = [
            _comment("c1", "older thread", updated_at="2026-01-01T00:00:00Z"),
            _comment("c2", "newer thread", updated_at="2026-01-02T00:00:00Z"),
        ]
        threads = [_thread("c1"), _thread("c2")]
        bundle = make_issue(issue_id="th1", issue_key="TH-1", comments=comments, threads=threads)
        manifest = _make_manifest()

        write_ticket(
            bundle,
            root_state=None,
            last_synced_at="2026-03-01T00:00:00Z",
            context_dir=tmp_path,
            manifest=manifest,
        )

        content = (tmp_path / "TH-1.md").read_text()
        pos_c1 = content.index("<!-- context-sync:thread id=c1")
        pos_c2 = content.index("<!-- context-sync:thread id=c2")
        # newer thread (c2) must appear before older thread (c1).
        assert pos_c2 < pos_c1

    def test_write_error_propagates(self, tmp_path: Path) -> None:
        """WriteError from write_and_verify_ticket must propagate unchanged."""
        bundle = make_issue(issue_id="e1", issue_key="ERR-1")
        manifest = _make_manifest()

        with patch(
            "context_sync._pipeline.write_and_verify_ticket",
            side_effect=WriteError("simulated write failure"),
        ):
            with pytest.raises(WriteError, match="simulated write failure"):
                write_ticket(
                    bundle,
                    root_state=None,
                    last_synced_at="2026-03-01T00:00:00Z",
                    context_dir=tmp_path,
                    manifest=manifest,
                )


# ---------------------------------------------------------------------------
# _extract_issue_keys and _bundle_content_texts
# ---------------------------------------------------------------------------


class TestUrlHelpers:
    def test_extracts_single_key(self) -> None:
        text = "See https://linear.app/myteam/issue/ACP-123 for details."
        assert _extract_issue_keys(text) == ["ACP-123"]

    def test_extracts_multiple_keys(self) -> None:
        text = (
            "Blocked by https://linear.app/myteam/issue/ACP-1 "
            "and https://linear.app/myteam/issue/ACP-2"
        )
        assert _extract_issue_keys(text) == ["ACP-1", "ACP-2"]

    def test_no_urls_returns_empty(self) -> None:
        assert _extract_issue_keys("No URLs here.") == []

    def test_different_workspace_slug_matched(self) -> None:
        text = "https://linear.app/other-team/issue/XYZ-99"
        assert _extract_issue_keys(text) == ["XYZ-99"]

    def test_bundle_includes_description_and_comments(self) -> None:
        bundle = make_issue(
            issue_id="b1",
            description="desc text",
            comments=[_comment("c1", "comment body")],
        )
        texts = _bundle_content_texts(bundle)
        assert "desc text" in texts
        assert "comment body" in texts

    def test_bundle_no_description_omitted(self) -> None:
        bundle = make_issue(issue_id="b1", description=None)
        texts = _bundle_content_texts(bundle)
        assert all(t is not None for t in texts)
        # Description must not appear as None string.
        assert "None" not in texts


# ---------------------------------------------------------------------------
# make_ticket_ref_provider
# ---------------------------------------------------------------------------


class TestMakeTicketRefProvider:
    async def test_returns_refs_for_known_key(self) -> None:
        """Provider must return refs for keys already present in fetched."""
        b_root = make_issue(
            issue_id="p1",
            issue_key="P-1",
            description="See https://linear.app/team/issue/P-2",
        )
        b_ref = make_issue(issue_id="p2", issue_key="P-2")
        fetched = {"p1": b_root, "p2": b_ref}

        provider = make_ticket_ref_provider(
            fetched,
            gateway=FakeLinearGateway(),
            semaphore=asyncio.Semaphore(5),
        )
        result = await provider(["p1"])
        assert result == {"p1": [("p2", "P-2")]}

    async def test_resolves_unknown_key_via_gateway(self) -> None:
        """Provider must resolve unknown keys via gateway.fetch_issue."""
        gw = FakeLinearGateway()
        gw.add_issue(make_issue(issue_id="q2", issue_key="Q-2"))

        b_root = make_issue(
            issue_id="q1",
            issue_key="Q-1",
            description="See https://linear.app/team/issue/Q-2",
        )
        fetched: dict[str, TicketBundle] = {"q1": b_root}

        provider = make_ticket_ref_provider(fetched, gateway=gw, semaphore=asyncio.Semaphore(5))
        result = await provider(["q1"])

        assert result == {"q1": [("q2", "Q-2")]}
        # Newly resolved bundle must be added to fetched.
        assert "q2" in fetched

    async def test_skips_unresolvable_key(self) -> None:
        """Provider must silently skip keys the gateway cannot resolve."""
        gw = FakeLinearGateway()  # empty, no issues loaded

        b_root = make_issue(
            issue_id="s1",
            issue_key="S-1",
            description="See https://linear.app/team/issue/MISSING-99",
        )
        fetched: dict[str, TicketBundle] = {"s1": b_root}

        provider = make_ticket_ref_provider(fetched, gateway=gw, semaphore=asyncio.Semaphore(5))
        result = await provider(["s1"])

        # MISSING-99 cannot be resolved, so no refs returned.
        assert result == {}

    async def test_excludes_self_references(self) -> None:
        """A ticket referencing its own key must be excluded."""
        b_root = make_issue(
            issue_id="self1",
            issue_key="SELF-1",
            description="See https://linear.app/team/issue/SELF-1 here.",
        )
        fetched = {"self1": b_root}

        provider = make_ticket_ref_provider(
            fetched,
            gateway=FakeLinearGateway(),
            semaphore=asyncio.Semaphore(5),
        )
        result = await provider(["self1"])
        assert result == {}

    async def test_deduplicates_repeated_urls(self) -> None:
        """The same target appearing multiple times must appear only once."""
        b_ref = make_issue(issue_id="d2", issue_key="D-2")
        b_root = make_issue(
            issue_id="d1",
            issue_key="D-1",
            description=(
                "https://linear.app/team/issue/D-2 and again https://linear.app/team/issue/D-2"
            ),
        )
        fetched = {"d1": b_root, "d2": b_ref}

        provider = make_ticket_ref_provider(
            fetched,
            gateway=FakeLinearGateway(),
            semaphore=asyncio.Semaphore(5),
        )
        result = await provider(["d1"])
        assert result == {"d1": [("d2", "D-2")]}

    async def test_issue_not_in_fetched_skipped(self) -> None:
        """If an issue_id is not in fetched the provider must skip it silently."""
        fetched: dict[str, TicketBundle] = {}
        provider = make_ticket_ref_provider(
            fetched,
            gateway=FakeLinearGateway(),
            semaphore=asyncio.Semaphore(5),
        )
        result = await provider(["not-in-fetched"])
        assert result == {}

    async def test_scans_comment_bodies(self) -> None:
        """Provider must scan comment bodies, not only the description."""
        b_ref = make_issue(issue_id="cb2", issue_key="CB-2")
        b_root = make_issue(
            issue_id="cb1",
            issue_key="CB-1",
            description=None,
            comments=[_comment("c1", "Check https://linear.app/team/issue/CB-2")],
        )
        fetched = {"cb1": b_root, "cb2": b_ref}

        provider = make_ticket_ref_provider(
            fetched,
            gateway=FakeLinearGateway(),
            semaphore=asyncio.Semaphore(5),
        )
        result = await provider(["cb1"])
        assert result == {"cb1": [("cb2", "CB-2")]}
