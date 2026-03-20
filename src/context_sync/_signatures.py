"""
Refresh-cursor signature computation.

Computes the ``comments_signature`` and ``relations_signature`` digests
used by the v1 composite refresh cursor defined in
`docs/adr.md §6.1 <../../docs/adr.md>`_ and
`docs/design/0-top-level-design.md §6.2 <../../docs/design/0-top-level-design.md>`_.

Both signatures use SHA-256 over canonical UTF-8 records, encoded as
lowercase hexadecimal with a mandatory ``v1:`` prefix.  The ``v1:``
prefix versions the canonicalization contract independently from the
on-disk ``format_version``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from context_sync._gateway import (
    RefreshCommentMeta,
    RefreshThreadMeta,
    RelationData,
)

SIGNATURE_PREFIX: str = "v1:"


def compute_comments_signature(
    comments: Sequence[RefreshCommentMeta],
    threads: Sequence[RefreshThreadMeta],
) -> str:
    """
    Compute the v1 ``comments_signature``.

    Canonical record formats (one line per record, UTF-8)::

        thread|<root_comment_id>|resolved=<true|false>
        comment|<comment_id>|root=<root_id>|parent=<parent_or_none>|updated_at=<ts_or_none>|deleted=<true|false|unknown>

    Thread records are sorted lexicographically by ``root_comment_id``.
    Comment records are sorted lexicographically by ``comment_id``.
    All records are joined with newlines, then SHA-256 hashed.

    Parameters
    ----------
    comments:
        Per-comment metadata from the refresh adapter.
    threads:
        Per-thread metadata from the refresh adapter.

    Returns
    -------
    str
        Hex digest prefixed with ``v1:``.
    """
    thread_records = sorted(
        (f"thread|{t.root_comment_id}|resolved={_canonical_bool(t.resolved)}" for t in threads),
    )
    comment_records = sorted(
        (
            f"comment|{c.comment_id}"
            f"|root={c.root_comment_id}"
            f"|parent={_canonical_optional(c.parent_comment_id)}"
            f"|updated_at={_canonical_optional(c.updated_at)}"
            f"|deleted={_canonical_deleted(c.deleted)}"
            for c in comments
        ),
    )
    canonical = "\n".join(thread_records + comment_records)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


def compute_relations_signature(
    relations: Sequence[RelationData],
) -> str:
    """
    Compute the v1 ``relations_signature``.

    Canonical record format (one line per record, UTF-8)::

        relation|<dimension>|<relation_type>|<target_issue_id>|<target_issue_key>

    Records are sorted lexicographically by the full tuple
    ``(dimension, relation_type, target_issue_id, target_issue_key)``.

    Parameters
    ----------
    relations:
        Relation edges from the refresh adapter or ticket bundle.

    Returns
    -------
    str
        Hex digest prefixed with ``v1:``.
    """
    records = sorted(
        (
            f"relation|{r.dimension}|{r.relation_type}|{r.target_issue_id}|{r.target_issue_key}"
            for r in relations
        ),
    )
    canonical = "\n".join(records)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


# ---------------------------------------------------------------------------
# Canonical value helpers
# ---------------------------------------------------------------------------


def _canonical_bool(value: bool) -> str:
    """Return ``'true'`` or ``'false'`` for canonical serialization."""
    return "true" if value else "false"


def _canonical_deleted(value: bool | None) -> str:
    """Return ``'true'``, ``'false'``, or ``'unknown'`` for the deleted field."""
    if value is None:
        return "unknown"
    return "true" if value else "false"


def _canonical_optional(value: str | None) -> str:
    """Return *value* or ``'none'`` for canonical serialization."""
    return value if value is not None else "none"
