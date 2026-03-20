"""
ContextSync — the primary async entry point for context-sync operations.

This module exposes the ``ContextSync`` class whose constructor and method
signatures match the public API defined in the top-level design (§1).  The
async methods are stubs in M1-1; they will be implemented by later tickets
(M2-1 through M3-3).
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from context_sync._config import (
    DEFAULT_CONCURRENCY_LIMIT,
    DEFAULT_MAX_TICKETS_PER_ROOT,
    resolve_dimensions,
)
from context_sync._errors import ContextSyncError
from context_sync._models import DiffResult, SyncResult

if TYPE_CHECKING:
    from context_sync._gateway import LinearGateway

logger = logging.getLogger(__name__)


class ContextSync:
    """
    Deterministic Linear ticket-neighborhood snapshot manager.

    The caller provides an authenticated ``linear-client`` ``Linear`` instance
    (or, for testing, a ``LinearGateway`` via ``_gateway_override``), a target
    directory, and optional traversal configuration.  All mutating and
    read-only operations are async methods.

    Parameters
    ----------
    linear:
        An authenticated ``linear_client.Linear`` instance.  Ignored when
        *_gateway_override* is provided.
    context_dir:
        Path to the context directory that will hold ticket files, the
        manifest, and the lock record.
    dimensions:
        Per-dimension traversal depths.  ``None`` uses the built-in defaults.
        Unknown dimension names and negative depths are rejected.
    max_tickets_per_root:
        Per-root ticket cap for traversal (ADR §1.1).
    concurrency_limit:
        ``asyncio.Semaphore`` limit for concurrent ticket fetches within a
        single invocation (ADR §3.1).  This is a per-process control; the
        tool does not attempt cross-process coordination.
    _gateway_override:
        **Testing hook.**  When provided, this gateway is used directly
        instead of wrapping *linear*.  Production callers should never set
        this parameter.

    Raises
    ------
    ContextSyncError
        If neither *linear* nor *_gateway_override* is provided.
    ValueError
        If *dimensions* contains unknown names or negative depths, or if
        *max_tickets_per_root* or *concurrency_limit* is not positive.
    """

    def __init__(
        self,
        linear: Any = None,
        context_dir: Path | str = ".",
        dimensions: dict[str, int] | None = None,
        *,
        max_tickets_per_root: int = DEFAULT_MAX_TICKETS_PER_ROOT,
        concurrency_limit: int = DEFAULT_CONCURRENCY_LIMIT,
        _gateway_override: LinearGateway | None = None,
    ) -> None:
        if _gateway_override is not None:
            self._gateway: LinearGateway = _gateway_override
        elif linear is not None:
            # The real gateway wrapping linear-client will be created by a
            # later implementation ticket.  For now, store the raw reference.
            self._linear = linear
            self._gateway = None  # type: ignore[assignment]
        else:
            raise ContextSyncError("Either 'linear' or '_gateway_override' must be provided.")

        self._context_dir = Path(context_dir)
        self._dimensions = resolve_dimensions(dimensions)

        if max_tickets_per_root < 1:
            raise ValueError(f"max_tickets_per_root must be positive, got {max_tickets_per_root}")
        self._max_tickets_per_root = max_tickets_per_root

        if concurrency_limit < 1:
            raise ValueError(f"concurrency_limit must be positive, got {concurrency_limit}")
        self._concurrency_limit = concurrency_limit
        self._semaphore = asyncio.Semaphore(concurrency_limit)

    # -- Public properties --------------------------------------------------

    @property
    def context_dir(self) -> Path:
        """The context directory this syncer operates on."""
        return self._context_dir

    @property
    def dimensions(self) -> dict[str, int]:
        """Active traversal-depth configuration (dimension → max hops)."""
        return dict(self._dimensions)

    @property
    def max_tickets_per_root(self) -> int:
        """Per-root ticket cap."""
        return self._max_tickets_per_root

    @property
    def concurrency_limit(self) -> int:
        """Semaphore limit for concurrent ticket fetches."""
        return self._concurrency_limit

    # -- Async entry points -------------------------------------------------
    #
    # Stub implementations.  Each will be filled in by the ticket that owns
    # the corresponding flow:
    #   sync        → M2-3
    #   refresh     → M3-1
    #   add         → M3-2
    #   remove_root → M3-2
    #   diff        → M3-3

    async def sync(
        self,
        root_ticket_id: str,
        max_tickets_per_root: int | None = None,
        dimensions: dict[str, int] | None = None,
    ) -> SyncResult:
        """
        Full-snapshot rebuild from *root_ticket_id* and all existing roots.

        Parameters
        ----------
        root_ticket_id:
            Issue key or Linear issue URL of the root to add/refresh.
        max_tickets_per_root:
            Override the instance-level per-root cap for this call.
        dimensions:
            Override the instance-level dimension depths for this call.

        Returns
        -------
        SyncResult
            Created, updated, unchanged, removed, and errored ticket sets.
        """
        raise NotImplementedError("sync will be implemented by M2-3")

    async def refresh(
        self,
        missing_root_policy: Literal["quarantine", "remove"] = "quarantine",
    ) -> SyncResult:
        """
        Incremental whole-snapshot update from all existing roots.

        Parameters
        ----------
        missing_root_policy:
            How to handle existing manifest roots that are no longer visible.
            ``"quarantine"`` (default) marks them quarantined; ``"remove"``
            deletes them immediately.

        Returns
        -------
        SyncResult
        """
        raise NotImplementedError("refresh will be implemented by M3-1")

    async def add(self, ticket_ref: str) -> SyncResult:
        """
        Add a new root and run whole-snapshot refresh.

        Parameters
        ----------
        ticket_ref:
            Issue key or Linear issue URL of the ticket to add as a root.

        Returns
        -------
        SyncResult
        """
        raise NotImplementedError("add will be implemented by M3-2")

    async def remove_root(self, ticket_ref: str) -> SyncResult:
        """
        Remove a root and run whole-snapshot refresh.

        Parameters
        ----------
        ticket_ref:
            Issue key or Linear issue URL of the root to remove.

        Returns
        -------
        SyncResult
        """
        raise NotImplementedError("remove_root will be implemented by M3-2")

    async def diff(self) -> DiffResult:
        """
        Compare local snapshot to live Linear state without modifying files.

        Returns
        -------
        DiffResult
        """
        raise NotImplementedError("diff will be implemented by M3-3")
