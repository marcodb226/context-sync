"""
Ticket-reference parsing and resolution helpers.

This module provides stateless helpers for normalizing and resolving ticket
references (issue keys, Linear issue URLs, and raw UUIDs) against manifest
data.  It has no dependency on ``ContextSync`` instance state.

The resolution order in :func:`_resolve_ref_to_uuid` is deliberately
current-key-first so that a recently-reassigned issue key resolves to the
ticket that currently owns it, not to a historical alias that happens to
share the same string.  See ADR §1.6 for the alias-precedence rationale.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from context_sync._types import IssueId, IssueKey

if TYPE_CHECKING:
    from context_sync._manifest import Manifest

# Pattern captures ``https://linear.app/<slug>/issue/<KEY-123>`` with an
# optional trailing title slug.  Issue keys are uppercase letters, a hyphen,
# and one or more digits.
_LINEAR_URL_RE = re.compile(r"^https?://linear\.app/(?P<slug>[^/]+)/issue/(?P<key>[A-Za-z]+-\d+)")


def _parse_linear_url(url: str) -> tuple[str, str] | None:
    """
    Extract ``(workspace_slug, issue_key)`` from a Linear issue URL.

    Returns ``None`` when *url* does not match the expected Linear URL
    pattern.
    """
    m = _LINEAR_URL_RE.match(url)
    if m:
        return m.group("slug"), m.group("key")
    return None


def _normalize_ticket_ref(ticket_ref: str) -> tuple[str | None, str]:
    """
    Normalize a ticket reference to ``(workspace_slug | None, key_or_id)``.

    If *ticket_ref* is a Linear issue URL, the workspace slug and issue key
    are extracted.  Otherwise the reference is returned unchanged with
    ``None`` as the slug.
    """
    parsed = _parse_linear_url(ticket_ref)
    if parsed is not None:
        return parsed
    return None, ticket_ref


def _resolve_ref_to_uuid(ref: str, manifest: Manifest) -> IssueId | None:
    """
    Attempt to resolve a ticket reference to a UUID using manifest data.

    Resolution order:

    1. Ticket entries scanned by ``current_key`` — the key a ticket
       currently owns takes precedence over historical aliases so that a
       recently-reassigned key resolves to its current owner.
    2. Alias table (``manifest.aliases``; maps historical issue keys to
       UUIDs).
    3. Direct UUID match in tracked tickets (roots or derived).

    Returns ``None`` when no match is found.
    """
    # Step 1 — current key (highest priority).
    ref_as_key = IssueKey(ref)
    for uid, entry in manifest.tickets.items():
        if entry.current_key == ref_as_key:
            return uid

    # Step 2 — alias table: historical issue_key → UUID.
    alias_key = IssueKey(ref)
    if manifest.aliases and alias_key in manifest.aliases:
        return manifest.aliases[alias_key]

    # Step 3 — direct UUID match against all tracked tickets (roots and
    # derived), so that callers such as ``remove_root`` can accept raw UUIDs
    # for any tracked ticket and reach the correct downstream error path.
    uid = IssueId(ref)
    if uid in manifest.tickets:
        return uid
    if uid in manifest.roots and uid not in manifest.tickets:
        # Root UUID that has no ticket entry yet (edge case during early
        # bootstrap).
        return uid

    return None
