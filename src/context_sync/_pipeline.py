"""
Ticket fetch normalization and render pipeline.

Delivers bounded concurrent ticket fetches, refresh-cursor computation,
deterministic ticket-file writes with post-write verification, and the
Tier 3 (``ticket_ref``) URL provider that links fetched content back into
the traversal engine.

Design notes
------------
* :func:`fetch_tickets` uses ``asyncio.TaskGroup`` with the caller-supplied
  ``asyncio.Semaphore`` so the number of simultaneous in-flight gateway
  requests never exceeds the per-process concurrency limit (ADR §3.1).

* :func:`write_ticket` is synchronous: it calls only synchronous I/O
  helpers (:func:`_io.write_and_verify_ticket`).  The caller (M2-3 sync
  flow) controls the async context and drives the sequential per-ticket
  writes after all fetches complete.  All manifest and filesystem mutations
  are committed only *after* the new file content has been written and
  verified successfully, so a write failure during a key-rename leaves the
  old file and manifest state intact.

* :func:`make_ticket_ref_provider` returns an async callable compatible
  with :class:`_traversal.TicketRefProvider`.  The provider scans already-
  fetched content and resolves unknown keys first via a locally supplied
  alias map (when given) and then via the gateway, mutating the shared
  ``fetched`` dict as a side effect so M2-3 can write newly discovered
  Tier 3 tickets alongside the rest.  Only :class:`RootNotFoundError` is
  caught when a key cannot be resolved; all other gateway exceptions
  propagate unchanged per the traversal contract.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from context_sync._errors import RootNotFoundError
from context_sync._gateway import (
    LinearGateway,
    RefreshCommentMeta,
    RefreshThreadMeta,
    TicketBundle,
)
from context_sync._io import write_and_verify_ticket
from context_sync._manifest import Manifest, ManifestTicketEntry
from context_sync._renderer import (
    expected_frontmatter_fields,
    expected_markers,
    render_ticket_file,
    resolve_root_comment,
)
from context_sync._signatures import compute_comments_signature, compute_relations_signature
from context_sync._traversal import TicketRefProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ticket-ref URL pattern
# ---------------------------------------------------------------------------

_LINEAR_ISSUE_KEY_RE: re.Pattern[str] = re.compile(
    r"https://linear\.app/[^/\s]+/issue/([A-Z][A-Z0-9]*-\d+)"
)

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TicketWriteResult:
    """
    Result of one :func:`write_ticket` call.

    Attributes
    ----------
    issue_id:
        Stable Linear issue UUID.
    issue_key:
        Current human-facing key after the write.  May differ from
        ``previous_key`` when an upstream issue-key rename was detected.
    previous_key:
        The key recorded in the manifest before this write, or ``None``
        if the key is unchanged or the ticket was not previously tracked.
    file_path:
        Relative path of the written ticket file within the context
        directory (e.g. ``"ACP-123.md"``).
    """

    issue_id: str
    issue_key: str
    previous_key: str | None
    file_path: str


# ---------------------------------------------------------------------------
# Refresh cursor
# ---------------------------------------------------------------------------


def compute_refresh_cursor(bundle: TicketBundle) -> dict[str, str]:
    """
    Build the v1 composite refresh cursor for a fetched ticket.

    Derives :class:`RefreshCommentMeta` from :class:`CommentData` using
    :func:`_renderer.resolve_root_comment` and :class:`RefreshThreadMeta`
    from :class:`ThreadData`, then delegates to
    :func:`_signatures.compute_comments_signature` and
    :func:`_signatures.compute_relations_signature`.

    Parameters
    ----------
    bundle:
        Fetched ticket data from :func:`fetch_tickets` or
        :meth:`LinearGateway.fetch_issue`.

    Returns
    -------
    dict[str, str]
        Mapping with keys ``issue_updated_at``, ``comments_signature``,
        and ``relations_signature``.
    """
    parent_map: dict[str, str | None] = {c.comment_id: c.parent_comment_id for c in bundle.comments}
    comment_metas: list[RefreshCommentMeta] = [
        RefreshCommentMeta(
            comment_id=c.comment_id,
            root_comment_id=resolve_root_comment(c.comment_id, parent_map),
            parent_comment_id=c.parent_comment_id,
            updated_at=c.updated_at,
            deleted=False,
        )
        for c in bundle.comments
    ]
    thread_metas: list[RefreshThreadMeta] = [
        RefreshThreadMeta(root_comment_id=t.root_comment_id, resolved=t.resolved)
        for t in bundle.threads
    ]
    return {
        "issue_updated_at": bundle.issue.updated_at,
        "comments_signature": compute_comments_signature(comment_metas, thread_metas),
        "relations_signature": compute_relations_signature(bundle.relations),
    }


# ---------------------------------------------------------------------------
# Bounded concurrent fetch
# ---------------------------------------------------------------------------


async def fetch_tickets(
    issue_ids: list[str],
    *,
    gateway: LinearGateway,
    semaphore: asyncio.Semaphore,
) -> dict[str, TicketBundle]:
    """
    Fetch multiple ticket bundles concurrently under a shared semaphore.

    Each ``fetch_issue`` call acquires the semaphore before starting so
    the number of simultaneous in-flight gateway requests never exceeds
    the configured per-process concurrency limit (ADR §3.1).

    Parameters
    ----------
    issue_ids:
        Stable Linear issue UUIDs to fetch.
    gateway:
        Gateway for single-ticket fetch calls.
    semaphore:
        Shared concurrency limiter (from :attr:`ContextSync._semaphore`
        or a test-provided semaphore).

    Returns
    -------
    dict[str, TicketBundle]
        Mapping from issue UUID to fetched bundle.  Any exception raised
        by the gateway propagates out of the task group to the caller.
    """
    fetched: dict[str, TicketBundle] = {}

    async def _fetch_one(issue_id: str) -> None:
        async with semaphore:
            bundle = await gateway.fetch_issue(issue_id)
        fetched[bundle.issue.issue_id] = bundle

    async with asyncio.TaskGroup() as tg:
        for issue_id in issue_ids:
            tg.create_task(_fetch_one(issue_id))

    return fetched


# ---------------------------------------------------------------------------
# Ticket file write
# ---------------------------------------------------------------------------


def write_ticket(
    bundle: TicketBundle,
    *,
    root_state: str | None,
    quarantined_reason: str | None = None,
    last_synced_at: str,
    context_dir: Path,
    manifest: Manifest,
) -> TicketWriteResult:
    """
    Render and write one ticket file, updating the manifest in-memory.

    Detects issue-key renames by comparing the live bundle key to the
    manifest's tracked ``current_key`` for the same UUID.  When a rename
    is detected, the new file is written and verified first; on success
    the old file is removed and the alias and manifest entries are
    updated.  On write failure the old file and manifest state are left
    intact so no partial rename is visible.

    The manifest is mutated in place; the caller is responsible for
    persisting it after all tickets in the pass are written.

    Parameters
    ----------
    bundle:
        Fetched ticket data to write.
    root_state:
        ``"active"`` or ``"quarantined"`` for root tickets; ``None``
        for derived tickets.
    quarantined_reason:
        Machine-readable quarantine reason string, required only when
        ``root_state == "quarantined"``.
    last_synced_at:
        UTC RFC 3339 timestamp of the current sync pass.
    context_dir:
        Absolute path to the context directory.
    manifest:
        The in-memory manifest to update.  The ``tickets`` and ``aliases``
        dicts are updated in place to reflect the written ticket's current
        key and file path.

    Returns
    -------
    TicketWriteResult

    Raises
    ------
    WriteError
        If the file write or post-write verification fails.  The manifest
        and filesystem state are unchanged when this is raised during a
        key-rename path.
    """
    issue_id = bundle.issue.issue_id
    issue_key = bundle.issue.issue_key
    previous_key: str | None = None
    old_path: Path | None = None

    existing = manifest.tickets.get(issue_id)
    if existing is not None and existing.current_key != issue_key:
        previous_key = existing.current_key
        logger.debug(
            "Issue-key rename detected for %s: %s → %s",
            issue_id,
            previous_key,
            issue_key,
        )
        old_path = context_dir / existing.current_path

    relative_path = f"{issue_key}.md"

    # Write and verify the new content first — no manifest or filesystem
    # state is mutated before this call returns successfully.
    cursor = compute_refresh_cursor(bundle)
    content = render_ticket_file(
        bundle,
        root_state=root_state,
        quarantined_reason=quarantined_reason,
        last_synced_at=last_synced_at,
        refresh_cursor=cursor,
    )
    write_and_verify_ticket(
        context_dir / relative_path,
        content,
        expected_frontmatter_fields(bundle, root_state=root_state),
        expected_markers(bundle),
    )

    # Write succeeded: commit alias recording, old-file removal, and manifest update.
    if previous_key is not None:
        manifest.aliases[previous_key] = issue_id
        if old_path is not None and old_path.is_file():
            old_path.unlink()
            logger.debug("Removed old ticket file: %s", old_path.name)

    manifest.tickets[issue_id] = ManifestTicketEntry(
        current_key=issue_key,
        current_path=relative_path,
    )

    return TicketWriteResult(
        issue_id=issue_id,
        issue_key=issue_key,
        previous_key=previous_key,
        file_path=relative_path,
    )


# ---------------------------------------------------------------------------
# Ticket-ref URL provider (Tier 3)
# ---------------------------------------------------------------------------


def _extract_issue_keys(text: str) -> list[str]:
    """
    Extract Linear issue keys from Linear URL references in *text*.

    Returns
    -------
    list[str]
        Issue keys in order of appearance (may contain duplicates).
    """
    return _LINEAR_ISSUE_KEY_RE.findall(text)


def _bundle_content_texts(bundle: TicketBundle) -> list[str]:
    """
    Collect the text fields from *bundle* that may contain Linear URLs.

    Includes the issue description (when present) and all comment bodies.

    Returns
    -------
    list[str]
        Ordered list of content strings to scan for ticket-ref URLs.
    """
    texts: list[str] = []
    if bundle.issue.description:
        texts.append(bundle.issue.description)
    for comment in bundle.comments:
        texts.append(comment.body)
    return texts


def make_ticket_ref_provider(
    fetched: dict[str, TicketBundle],
    *,
    gateway: LinearGateway,
    semaphore: asyncio.Semaphore,
    aliases: dict[str, str] | None = None,
) -> TicketRefProvider:
    """
    Build a Tier 3 provider that scans already-fetched ticket content.

    The returned provider satisfies the :class:`_traversal.TicketRefProvider`
    contract: it receives a sequence of issue UUIDs whose content is
    present in *fetched*, scans description and comment bodies for Linear
    ticket URLs, resolves unknown keys first via *aliases* (when supplied)
    and then via the gateway (adding resolved bundles to *fetched* as a
    side effect), deduplicates results by target UUID, and returns the
    discovered ``(target_id, target_key)`` pairs.

    Only :class:`RootNotFoundError` is swallowed when a key cannot be
    resolved; all other gateway exceptions propagate unchanged per the
    traversal contract.

    Self-references (a ticket referencing its own key) are skipped.

    Parameters
    ----------
    fetched:
        Shared dict of already-fetched bundles (issue UUID → bundle).
        Mutated in place when unknown keys are resolved via the gateway.
    gateway:
        Gateway used to resolve issue keys not yet in *fetched* or
        *aliases*.
    semaphore:
        Shared concurrency limiter for gateway calls.
    aliases:
        Optional mapping of previously observed issue keys to their stable
        UUIDs (e.g. ``manifest.aliases``).  Consulted before falling back
        to the gateway so that bodies referencing old keys resolve locally
        without a remote call.

    Returns
    -------
    TicketRefProvider
        Async provider callable compatible with
        :func:`_traversal.build_reachable_graph`.
    """

    async def _provider(issue_ids: list[str]) -> dict[str, list[tuple[str, str]]]:
        # Build a current key→UUID reverse index from whatever is in fetched.
        key_to_id: dict[str, str] = {b.issue.issue_key: b.issue.issue_id for b in fetched.values()}

        result: dict[str, list[tuple[str, str]]] = {}
        for issue_id in issue_ids:
            bundle = fetched.get(issue_id)
            if bundle is None:
                continue

            raw_refs: list[tuple[str, str]] = []
            for text in _bundle_content_texts(bundle):
                for key in _extract_issue_keys(text):
                    if key == bundle.issue.issue_key:
                        continue  # skip self-references
                    if key not in key_to_id:
                        # Check locally known aliases before going to the gateway.
                        if aliases and key in aliases:
                            aliased_id = aliases[key]
                            key_to_id[key] = aliased_id
                            # Also index the current key if the bundle is available.
                            if aliased_id in fetched:
                                key_to_id[fetched[aliased_id].issue.issue_key] = aliased_id
                        else:
                            try:
                                async with semaphore:
                                    resolved = await gateway.fetch_issue(key)
                                fetched[resolved.issue.issue_id] = resolved
                                key_to_id[resolved.issue.issue_key] = resolved.issue.issue_id
                                # Also index by the queried key so lookup
                                # succeeds even when the gateway returns a
                                # bundle whose current issue_key differs
                                # from the key that was in the URL.
                                key_to_id[key] = resolved.issue.issue_id
                            except RootNotFoundError:
                                logger.debug(
                                    "ticket_ref: key %r not found or not visible, skipping",
                                    key,
                                )
                                continue
                    target_id = key_to_id[key]
                    raw_refs.append((target_id, key))

            # Deduplicate by target UUID, preserving first-occurrence order.
            seen: set[str] = set()
            unique_refs: list[tuple[str, str]] = []
            for tid, tkey in raw_refs:
                if tid not in seen:
                    seen.add(tid)
                    unique_refs.append((tid, tkey))

            if unique_refs:
                result[issue_id] = unique_refs

        return result

    return _provider
