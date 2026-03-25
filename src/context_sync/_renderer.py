"""
Deterministic ticket-file rendering.

Transforms a :class:`TicketBundle` into the complete Markdown file content
(YAML frontmatter + body) that context-sync persists to disk.  The output
is fully deterministic: re-rendering the same bundle produces identical
content, so unchanged tickets do not cause spurious file rewrites.

Rendering rules come from the ADR §2/§2.2 and the top-level design §2.2.
"""

from __future__ import annotations

from typing import Any

from context_sync._config import FORMAT_VERSION
from context_sync._gateway import (
    AttachmentData,
    CommentData,
    RelationData,
    ThreadData,
    TicketBundle,
)
from context_sync._types import CommentId
from context_sync._yaml import serialize_frontmatter

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render_ticket_file(
    bundle: TicketBundle,
    *,
    root_state: str | None = None,
    quarantined_reason: str | None = None,
    last_synced_at: str,
    refresh_cursor: dict[str, str],
) -> str:
    """
    Render a complete ticket Markdown file from a :class:`TicketBundle`.

    Returns the full file content: YAML frontmatter delimited by ``---``
    followed by the Markdown body.

    Parameters
    ----------
    bundle:
        All data needed to render one ticket file.
    root_state:
        ``"active"`` or ``"quarantined"`` for root tickets; ``None``
        for derived tickets.
    quarantined_reason:
        Machine-readable quarantine reason (only when
        ``root_state == "quarantined"``).
    last_synced_at:
        UTC RFC 3339 timestamp of the current sync pass.
    refresh_cursor:
        The composite cursor mapping with keys ``issue_updated_at``,
        ``comments_signature``, ``relations_signature``.
    """
    fm = _build_frontmatter(
        bundle,
        root_state=root_state,
        quarantined_reason=quarantined_reason,
        last_synced_at=last_synced_at,
        refresh_cursor=refresh_cursor,
    )
    header = serialize_frontmatter(fm)
    body = _render_body(
        bundle,
        quarantined=root_state == "quarantined",
    )
    return header + body


# ---------------------------------------------------------------------------
# Expected verification data
# ---------------------------------------------------------------------------


def expected_frontmatter_fields(
    bundle: TicketBundle,
    *,
    root_state: str | None,
) -> dict[str, Any]:
    """
    Return the critical frontmatter fields for post-write verification.

    These are the fields checked by :func:`_io.write_and_verify_ticket`.
    """
    return {
        "format_version": FORMAT_VERSION,
        "ticket_uuid": bundle.issue.issue_id,
        "ticket_key": bundle.issue.issue_key,
        "root": root_state is not None,
    }


def expected_markers(bundle: TicketBundle) -> list[str]:
    """
    Return the structural HTML comment markers for post-write verification.

    Includes section markers for description and comments, plus thread and
    comment markers for every thread/comment in the bundle.
    """
    uid = bundle.issue.issue_id
    markers = [
        f"<!-- context-sync:section id=description-{uid} start -->",
        f"<!-- context-sync:section id=description-{uid} end -->",
        f"<!-- context-sync:section id=comments-{uid} start -->",
        f"<!-- context-sync:section id=comments-{uid} end -->",
    ]
    for thread in bundle.threads:
        rid = thread.root_comment_id
        resolved_str = "true" if thread.resolved else "false"
        markers.append(f"<!-- context-sync:thread id={rid} resolved={resolved_str} start -->")
        markers.append(f"<!-- context-sync:thread id={rid} end -->")
    for comment in bundle.comments:
        if comment.parent_comment_id is not None:
            markers.append(
                f"<!-- context-sync:comment id={comment.comment_id} "
                f"parent={comment.parent_comment_id} start -->"
            )
            markers.append(f"<!-- context-sync:comment id={comment.comment_id} end -->")
    return markers


# ---------------------------------------------------------------------------
# Frontmatter construction
# ---------------------------------------------------------------------------


def _build_frontmatter(
    bundle: TicketBundle,
    *,
    root_state: str | None,
    quarantined_reason: str | None,
    last_synced_at: str,
    refresh_cursor: dict[str, str],
) -> dict[str, Any]:
    """
    Build the frontmatter dict from a :class:`TicketBundle`.

    Keys use their natural names; lexicographic sorting happens during
    YAML serialization.  Optional fields set to ``None`` or empty are
    excluded by :func:`_yaml.strip_empty` at serialization time.
    """
    issue = bundle.issue

    fm: dict[str, Any] = {
        "assignee": issue.assignee,
        "created_at": issue.created_at,
        "creator": issue.creator,
        "format_version": FORMAT_VERSION,
        "last_synced_at": last_synced_at,
        "priority": issue.priority,
        "refresh_cursor": refresh_cursor,
        "root": root_state is not None,
        "status": issue.status,
        "ticket_key": issue.issue_key,
        "ticket_uuid": issue.issue_id,
        "title": issue.title,
        "updated_at": issue.updated_at,
    }

    if issue.parent_issue_key:
        fm["parent_ticket_key"] = issue.parent_issue_key

    if root_state is not None:
        fm["root_state"] = root_state
    if quarantined_reason is not None:
        fm["quarantined_reason"] = quarantined_reason

    if issue.labels:
        fm["labels"] = sorted(issue.labels)

    if bundle.attachments:
        fm["attachments"] = _render_attachments(bundle.attachments)

    if bundle.relations:
        fm["relations"] = _render_relations(bundle.relations)

    return fm


def _render_attachments(attachments: list[AttachmentData]) -> list[dict[str, str]]:
    """
    Render attachment metadata for frontmatter.

    Sorted by URL, then title as tie-breaker.
    """
    sorted_att = sorted(attachments, key=lambda a: (a.url, a.title or ""))
    return [{"name": a.title or "", "url": a.url} for a in sorted_att]


def _render_relations(relations: list[RelationData]) -> list[dict[str, str]]:
    """
    Render relation entries for frontmatter.

    Sorted by dimension, relation type, target UUID (for determinism),
    then rendered target key.
    """
    sorted_rels = sorted(
        relations,
        key=lambda r: (r.dimension, r.relation_type, r.target_issue_id, r.target_issue_key),
    )
    return [
        {
            "dimension": r.dimension,
            "ticket_key": r.target_issue_key,
            "type": r.relation_type,
        }
        for r in sorted_rels
    ]


# ---------------------------------------------------------------------------
# Body rendering
# ---------------------------------------------------------------------------


def _render_body(
    bundle: TicketBundle,
    *,
    quarantined: bool = False,
) -> str:
    """
    Render the Markdown body: optional quarantine warning, description
    section, then comments section.
    """
    parts: list[str] = []
    uid = bundle.issue.issue_id

    if quarantined:
        parts.append(_render_quarantine_warning())

    parts.append(_render_description_section(uid, bundle.issue.description))
    parts.append(_render_comments_section(uid, bundle.comments, bundle.threads))

    return "\n".join(parts)


def _render_quarantine_warning() -> str:
    """
    Render the quarantine warning preamble.

    This is local snapshot metadata, not fetched Linear content.
    """
    return (
        "> **Warning:** This root ticket was not available during the last "
        "refresh.\n"
        "> The content below may be stale or no longer visible to the current "
        "caller.\n"
    )


def _render_description_section(ticket_uuid: str, description: str | None) -> str:
    """Render the description section with ``context-sync`` markers."""
    desc = description or ""
    return (
        f"<!-- context-sync:section id=description-{ticket_uuid} start -->\n"
        f"## Description\n\n"
        f"{desc}\n"
        f"<!-- context-sync:section id=description-{ticket_uuid} end -->\n"
    )


def _render_comments_section(
    ticket_uuid: str,
    comments: list[CommentData],
    threads: list[ThreadData],
) -> str:
    """
    Render the comments section with threaded layout.

    Thread ordering: top-level threads newest-first by activity.
    Within each thread: root comment first, replies chronological.
    """
    header = f"<!-- context-sync:section id=comments-{ticket_uuid} start -->\n## Comments\n"
    footer = f"<!-- context-sync:section id=comments-{ticket_uuid} end -->\n"

    if not comments:
        return f"{header}\n{footer}"

    thread_map: dict[str, ThreadData] = {t.root_comment_id: t for t in threads}
    grouped = _group_comments_by_thread(comments)

    # Sort threads newest-first by thread activity.
    sorted_roots = sorted(
        grouped.keys(),
        key=lambda root_id: _thread_activity(grouped[root_id]),
        reverse=True,
    )

    thread_blocks: list[str] = []
    for root_id in sorted_roots:
        thread_comments = grouped[root_id]
        thread_meta = thread_map.get(root_id)
        thread_blocks.append(_render_thread(root_id, thread_comments, thread_meta))

    return header + "\n".join(thread_blocks) + "\n" + footer


def _group_comments_by_thread(
    comments: list[CommentData],
) -> dict[CommentId, list[CommentData]]:
    """
    Group comments by their thread root comment ID.

    Walks the parent chain to find each comment's thread root.
    """
    parent_map: dict[CommentId, CommentId | None] = {
        c.comment_id: c.parent_comment_id for c in comments
    }
    groups: dict[CommentId, list[CommentData]] = {}
    for comment in comments:
        root_id = resolve_root_comment(comment.comment_id, parent_map)
        groups.setdefault(root_id, []).append(comment)
    return groups


def _thread_activity(comments: list[CommentData]) -> str:
    """
    Return the most recent timestamp across all comments in a thread.

    Uses ``updated_at`` when available, falls back to ``created_at``.
    """
    return max(c.updated_at or c.created_at for c in comments)


def _render_thread(
    root_id: str,
    comments: list[CommentData],
    thread_meta: ThreadData | None,
) -> str:
    """
    Render one thread with nested reply structure.

    The root comment is rendered inline inside thread markers.  Replies
    are nested under their parent comment, preserving chronological order
    within each sibling set.
    """
    resolved = thread_meta.resolved if thread_meta else False
    resolved_str = "true" if resolved else "false"

    children: dict[str, list[CommentData]] = {}
    root_comment: CommentData | None = None
    for c in comments:
        if c.comment_id == root_id:
            root_comment = c
        else:
            parent = c.parent_comment_id or root_id
            children.setdefault(parent, []).append(c)

    # Sort each sibling set chronologically.
    for siblings in children.values():
        siblings.sort(key=lambda c: c.created_at)

    parts: list[str] = []
    parts.append(f"<!-- context-sync:thread id={root_id} resolved={resolved_str} start -->")

    if root_comment:
        author = root_comment.author or "Unknown"
        parts.append(f"### Thread by {author} at {root_comment.created_at}\n")
        parts.append(root_comment.body)
        # Render children of root recursively.
        _render_children(root_id, children, parts)

    parts.append(f"<!-- context-sync:thread id={root_id} end -->")
    return "\n".join(parts)


def _render_children(
    parent_id: str,
    children: dict[str, list[CommentData]],
    parts: list[str],
) -> None:
    """Recursively render child comments nested under *parent_id*."""
    for child in children.get(parent_id, []):
        parts.append(
            f"<!-- context-sync:comment id={child.comment_id} "
            f"parent={child.parent_comment_id or parent_id} start -->"
        )
        author = child.author or "Unknown"
        parts.append(f"**{author}** at {child.created_at}\n")
        parts.append(child.body)
        # Recurse into this child's replies before closing the marker.
        _render_children(child.comment_id, children, parts)
        parts.append(f"<!-- context-sync:comment id={child.comment_id} end -->")


# ---------------------------------------------------------------------------
# Thread-root resolution (shared with _testing.py)
# ---------------------------------------------------------------------------


def resolve_root_comment(
    comment_id: CommentId,
    parent_map: dict[CommentId, CommentId | None],
) -> CommentId:
    """
    Walk the parent chain to find the thread root comment.

    Parameters
    ----------
    comment_id:
        Starting comment ID.
    parent_map:
        Mapping from comment ID to parent comment ID (``None`` for roots).

    Returns
    -------
    str
        The root comment ID of the thread.
    """
    current = comment_id
    seen: set[CommentId] = set()
    while True:
        parent = parent_map.get(current)
        if parent is None:
            return current
        if parent in seen:
            return current  # cycle safety
        seen.add(current)
        current = parent
