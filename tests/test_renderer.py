"""Tests for context_sync._renderer deterministic ticket-file rendering."""

from __future__ import annotations

from context_sync._config import FORMAT_VERSION
from context_sync._gateway import AttachmentData, CommentData, RelationData, ThreadData
from context_sync._renderer import (
    expected_frontmatter_fields,
    expected_markers,
    render_ticket_file,
    resolve_root_comment,
)
from context_sync._testing import make_issue
from context_sync._yaml import parse_frontmatter

# ---------------------------------------------------------------------------
# Shared rendering defaults
# ---------------------------------------------------------------------------

_DEFAULT_SYNCED_AT = "2026-01-15T12:00:00Z"
_DEFAULT_CURSOR: dict[str, str] = {
    "issue_updated_at": "2026-01-01T00:00:00Z",
    "comments_signature": "abc123",
    "relations_signature": "def456",
}


def _render(
    bundle: object,
    *,
    root_state: str | None = None,
    quarantined_reason: str | None = None,
    last_synced_at: str = _DEFAULT_SYNCED_AT,
    refresh_cursor: dict[str, str] | None = None,
) -> str:
    """Convenience wrapper around render_ticket_file with sensible defaults."""
    return render_ticket_file(
        bundle,  # type: ignore[arg-type]
        root_state=root_state,
        quarantined_reason=quarantined_reason,
        last_synced_at=last_synced_at,
        refresh_cursor=refresh_cursor or _DEFAULT_CURSOR,
    )


# =========================================================================
# 1. TestRenderTicketFile
# =========================================================================


class TestRenderTicketFile:
    def test_minimal_ticket_renders_without_error(self) -> None:
        bundle = make_issue()
        result = _render(bundle)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_frontmatter_delimiters(self) -> None:
        bundle = make_issue()
        result = _render(bundle)
        assert result.startswith("---\n")
        assert "\n---\n" in result

    def test_contains_description_section_markers(self) -> None:
        bundle = make_issue()
        uid = bundle.issue.issue_id
        result = _render(bundle)
        assert f"<!-- context-sync:section id=description-{uid} start -->" in result
        assert f"<!-- context-sync:section id=description-{uid} end -->" in result

    def test_contains_comments_section_markers(self) -> None:
        bundle = make_issue()
        uid = bundle.issue.issue_id
        result = _render(bundle)
        assert f"<!-- context-sync:section id=comments-{uid} start -->" in result
        assert f"<!-- context-sync:section id=comments-{uid} end -->" in result

    def test_derived_ticket_has_root_false(self) -> None:
        bundle = make_issue()
        result = _render(bundle, root_state=None)
        fm = parse_frontmatter(result)
        assert fm["root"] is False

    def test_root_ticket_has_root_true_and_state_active(self) -> None:
        bundle = make_issue()
        result = _render(bundle, root_state="active")
        fm = parse_frontmatter(result)
        assert fm["root"] is True
        assert fm["root_state"] == "active"

    def test_quarantined_root_has_warning_preamble(self) -> None:
        bundle = make_issue()
        result = _render(
            bundle,
            root_state="quarantined",
            quarantined_reason="not_visible",
        )
        assert "> **Warning:**" in result

    def test_quarantined_root_has_quarantined_reason_in_frontmatter(self) -> None:
        bundle = make_issue()
        result = _render(
            bundle,
            root_state="quarantined",
            quarantined_reason="not_visible",
        )
        fm = parse_frontmatter(result)
        assert fm["quarantined_reason"] == "not_visible"
        assert fm["root_state"] == "quarantined"

    def test_description_body_rendered(self) -> None:
        bundle = make_issue(description="Hello **world**.")
        result = _render(bundle)
        assert "Hello **world**." in result

    def test_no_description_renders_empty(self) -> None:
        bundle = make_issue(description=None)
        result = _render(bundle)
        uid = bundle.issue.issue_id
        start = f"<!-- context-sync:section id=description-{uid} start -->"
        end = f"<!-- context-sync:section id=description-{uid} end -->"
        assert start in result
        assert end in result


# =========================================================================
# 2. TestFrontmatter
# =========================================================================


class TestFrontmatter:
    def test_labels_sorted_lexicographically(self) -> None:
        bundle = make_issue(labels=["Zzz", "Aaa", "Mmm"])
        result = _render(bundle)
        fm = parse_frontmatter(result)
        assert fm["labels"] == ["Aaa", "Mmm", "Zzz"]

    def test_attachments_sorted_by_url_then_title(self) -> None:
        attachments = [
            AttachmentData(
                attachment_id="att-2",
                title="Beta",
                url="https://example.com/z",
                created_at="2026-01-01T00:00:00Z",
                creator=None,
            ),
            AttachmentData(
                attachment_id="att-1",
                title="Alpha",
                url="https://example.com/a",
                created_at="2026-01-01T00:00:00Z",
                creator=None,
            ),
            AttachmentData(
                attachment_id="att-3",
                title="Aardvark",
                url="https://example.com/a",
                created_at="2026-01-01T00:00:00Z",
                creator=None,
            ),
        ]
        bundle = make_issue(attachments=attachments)
        result = _render(bundle)
        fm = parse_frontmatter(result)
        rendered_att = fm["attachments"]
        urls = [a["url"] for a in rendered_att]
        assert urls[0] == "https://example.com/a"
        assert urls[1] == "https://example.com/a"
        assert urls[2] == "https://example.com/z"
        # Same URL: tie-break by title.
        names = [a["name"] for a in rendered_att[:2]]
        assert names == ["Aardvark", "Alpha"]

    def test_relations_sorted_by_dimension_type_target(self) -> None:
        relations = [
            RelationData(
                dimension="relates_to",
                relation_type="relates_to",
                target_issue_id="uuid-z",
                target_issue_key="TEST-99",
            ),
            RelationData(
                dimension="blocks",
                relation_type="blocks",
                target_issue_id="uuid-a",
                target_issue_key="TEST-1",
            ),
            RelationData(
                dimension="blocks",
                relation_type="blocks",
                target_issue_id="uuid-b",
                target_issue_key="TEST-2",
            ),
        ]
        bundle = make_issue(relations=relations)
        result = _render(bundle)
        fm = parse_frontmatter(result)
        rendered_rels = fm["relations"]
        dims = [r["dimension"] for r in rendered_rels]
        assert dims == ["blocks", "blocks", "relates_to"]
        # Within same dimension+type, sorted by target_issue_id (uuid-a < uuid-b).
        keys = [r["ticket_key"] for r in rendered_rels[:2]]
        assert keys == ["TEST-1", "TEST-2"]

    def test_optional_none_fields_omitted(self) -> None:
        bundle = make_issue(assignee=None, priority=None)
        result = _render(bundle)
        fm = parse_frontmatter(result)
        assert "assignee" not in fm
        assert "priority" not in fm

    def test_refresh_cursor_fields_present(self) -> None:
        cursor: dict[str, str] = {
            "issue_updated_at": "2026-02-01T00:00:00Z",
            "comments_signature": "sig1",
            "relations_signature": "sig2",
        }
        bundle = make_issue()
        result = _render(bundle, refresh_cursor=cursor)
        fm = parse_frontmatter(result)
        assert fm["refresh_cursor"] == cursor

    def test_format_version_matches_config(self) -> None:
        bundle = make_issue()
        result = _render(bundle)
        fm = parse_frontmatter(result)
        assert fm["format_version"] == FORMAT_VERSION

    def test_parent_ticket_key_present_when_set(self) -> None:
        bundle = make_issue(
            parent_issue_id="parent-uuid",
            parent_issue_key="PARENT-1",
        )
        result = _render(bundle)
        fm = parse_frontmatter(result)
        assert fm["parent_ticket_key"] == "PARENT-1"

    def test_parent_ticket_key_absent_when_unset(self) -> None:
        bundle = make_issue(parent_issue_key=None)
        result = _render(bundle)
        fm = parse_frontmatter(result)
        assert "parent_ticket_key" not in fm

    def test_last_synced_at_present(self) -> None:
        bundle = make_issue()
        ts = "2026-03-01T06:00:00Z"
        result = _render(bundle, last_synced_at=ts)
        fm = parse_frontmatter(result)
        assert fm["last_synced_at"] == ts


# =========================================================================
# 3. TestCommentRendering
# =========================================================================


class TestCommentRendering:
    def test_single_thread_one_comment_has_thread_markers(self) -> None:
        comment = CommentData(
            comment_id="c-root",
            body="First comment body.",
            author="Alice",
            created_at="2026-01-01T10:00:00Z",
            updated_at=None,
            parent_comment_id=None,
        )
        thread = ThreadData(root_comment_id="c-root", resolved=False)
        bundle = make_issue(comments=[comment], threads=[thread])
        result = _render(bundle)
        assert "<!-- context-sync:thread id=c-root" in result
        assert "resolved=false" in result
        assert "Thread by Alice" in result
        assert "First comment body." in result

    def test_thread_with_root_and_reply(self) -> None:
        root = CommentData(
            comment_id="c-root",
            body="Root body.",
            author="Alice",
            created_at="2026-01-01T10:00:00Z",
            updated_at=None,
            parent_comment_id=None,
        )
        reply = CommentData(
            comment_id="c-reply",
            body="Reply body.",
            author="Bob",
            created_at="2026-01-01T11:00:00Z",
            updated_at=None,
            parent_comment_id="c-root",
        )
        thread = ThreadData(root_comment_id="c-root", resolved=False)
        bundle = make_issue(comments=[root, reply], threads=[thread])
        result = _render(bundle)
        # Root is inline in thread, not wrapped with comment markers.
        assert "<!-- context-sync:comment id=c-root" not in result
        assert "Root body." in result
        # Reply has comment markers.
        assert "<!-- context-sync:comment id=c-reply parent=c-root start -->" in result
        assert "<!-- context-sync:comment id=c-reply end -->" in result
        assert "Reply body." in result

    def test_multiple_threads_newest_first(self) -> None:
        c_old = CommentData(
            comment_id="c-old",
            body="Older thread.",
            author="Alice",
            created_at="2026-01-01T08:00:00Z",
            updated_at=None,
            parent_comment_id=None,
        )
        c_new = CommentData(
            comment_id="c-new",
            body="Newer thread.",
            author="Bob",
            created_at="2026-01-01T12:00:00Z",
            updated_at=None,
            parent_comment_id=None,
        )
        thread_old = ThreadData(root_comment_id="c-old", resolved=False)
        thread_new = ThreadData(root_comment_id="c-new", resolved=False)
        bundle = make_issue(
            comments=[c_old, c_new],
            threads=[thread_old, thread_new],
        )
        result = _render(bundle)
        # Newer thread appears before older thread.
        pos_new = result.index("Newer thread.")
        pos_old = result.index("Older thread.")
        assert pos_new < pos_old

    def test_nested_replies_chronological_within_thread(self) -> None:
        root = CommentData(
            comment_id="c-root",
            body="Root.",
            author="Alice",
            created_at="2026-01-01T10:00:00Z",
            updated_at=None,
            parent_comment_id=None,
        )
        reply_late = CommentData(
            comment_id="c-late",
            body="Late reply.",
            author="Charlie",
            created_at="2026-01-01T14:00:00Z",
            updated_at=None,
            parent_comment_id="c-root",
        )
        reply_early = CommentData(
            comment_id="c-early",
            body="Early reply.",
            author="Bob",
            created_at="2026-01-01T11:00:00Z",
            updated_at=None,
            parent_comment_id="c-root",
        )
        thread = ThreadData(root_comment_id="c-root", resolved=False)
        bundle = make_issue(
            comments=[root, reply_late, reply_early],
            threads=[thread],
        )
        result = _render(bundle)
        pos_early = result.index("Early reply.")
        pos_late = result.index("Late reply.")
        assert pos_early < pos_late

    def test_no_comments_section_still_present(self) -> None:
        bundle = make_issue(comments=[], threads=[])
        uid = bundle.issue.issue_id
        result = _render(bundle)
        assert f"<!-- context-sync:section id=comments-{uid} start -->" in result
        assert "## Comments" in result
        assert f"<!-- context-sync:section id=comments-{uid} end -->" in result

    def test_resolved_thread_marker(self) -> None:
        comment = CommentData(
            comment_id="c-root",
            body="Resolved thread body.",
            author="Alice",
            created_at="2026-01-01T10:00:00Z",
            updated_at=None,
            parent_comment_id=None,
        )
        thread = ThreadData(root_comment_id="c-root", resolved=True)
        bundle = make_issue(comments=[comment], threads=[thread])
        result = _render(bundle)
        assert "resolved=true" in result

    def test_unknown_author_uses_fallback(self) -> None:
        comment = CommentData(
            comment_id="c-root",
            body="Anonymous body.",
            author=None,
            created_at="2026-01-01T10:00:00Z",
            updated_at=None,
            parent_comment_id=None,
        )
        thread = ThreadData(root_comment_id="c-root", resolved=False)
        bundle = make_issue(comments=[comment], threads=[thread])
        result = _render(bundle)
        assert "Thread by Unknown" in result


# =========================================================================
# 4. TestQuarantineWarning
# =========================================================================


class TestQuarantineWarning:
    def test_warning_present_when_quarantined(self) -> None:
        bundle = make_issue()
        result = _render(
            bundle,
            root_state="quarantined",
            quarantined_reason="not_visible",
        )
        assert "> **Warning:**" in result
        assert "stale or no longer visible" in result

    def test_warning_absent_for_active_root(self) -> None:
        bundle = make_issue()
        result = _render(bundle, root_state="active")
        assert "> **Warning:**" not in result

    def test_warning_absent_for_derived_ticket(self) -> None:
        bundle = make_issue()
        result = _render(bundle, root_state=None)
        assert "> **Warning:**" not in result


# =========================================================================
# 5. TestExpectedFields
# =========================================================================


class TestExpectedFields:
    def test_expected_frontmatter_fields_for_root(self) -> None:
        bundle = make_issue(
            issue_id="uuid-abc",
            issue_key="TEST-42",
        )
        fields = expected_frontmatter_fields(bundle, root_state="active")
        assert fields == {
            "format_version": FORMAT_VERSION,
            "ticket_uuid": "uuid-abc",
            "ticket_key": "TEST-42",
            "root": True,
        }

    def test_expected_frontmatter_fields_for_derived(self) -> None:
        bundle = make_issue(
            issue_id="uuid-def",
            issue_key="TEST-99",
        )
        fields = expected_frontmatter_fields(bundle, root_state=None)
        assert fields == {
            "format_version": FORMAT_VERSION,
            "ticket_uuid": "uuid-def",
            "ticket_key": "TEST-99",
            "root": False,
        }

    def test_expected_markers_returns_four_markers(self) -> None:
        bundle = make_issue(issue_id="uuid-markers")
        markers = expected_markers(bundle)
        assert len(markers) == 4

    def test_expected_markers_description_and_comments(self) -> None:
        bundle = make_issue(issue_id="uuid-markers")
        markers = expected_markers(bundle)
        assert markers[0] == "<!-- context-sync:section id=description-uuid-markers start -->"
        assert markers[1] == "<!-- context-sync:section id=description-uuid-markers end -->"
        assert markers[2] == "<!-- context-sync:section id=comments-uuid-markers start -->"
        assert markers[3] == "<!-- context-sync:section id=comments-uuid-markers end -->"


# =========================================================================
# 6. TestResolveRootComment
# =========================================================================


class TestResolveRootComment:
    def test_root_comment_returns_itself(self) -> None:
        parent_map: dict[str, str | None] = {"c-root": None}
        assert resolve_root_comment("c-root", parent_map) == "c-root"

    def test_reply_returns_root(self) -> None:
        parent_map: dict[str, str | None] = {
            "c-root": None,
            "c-reply": "c-root",
        }
        assert resolve_root_comment("c-reply", parent_map) == "c-root"

    def test_deeply_nested_reply_returns_root(self) -> None:
        parent_map: dict[str, str | None] = {
            "c-root": None,
            "c-mid": "c-root",
            "c-deep": "c-mid",
            "c-deeper": "c-deep",
        }
        assert resolve_root_comment("c-deeper", parent_map) == "c-root"

    def test_cycle_safety_does_not_infinite_loop(self) -> None:
        parent_map: dict[str, str | None] = {
            "c-a": "c-b",
            "c-b": "c-a",
        }
        # Should terminate without hanging; result is one of the cycle members.
        result = resolve_root_comment("c-a", parent_map)
        assert result in ("c-a", "c-b")

    def test_unknown_parent_treated_as_root(self) -> None:
        parent_map: dict[str, str | None] = {
            "c-orphan": "c-missing",
        }
        # c-missing is not in parent_map, so .get returns None => c-missing is root.
        assert resolve_root_comment("c-orphan", parent_map) == "c-missing"
