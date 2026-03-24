"""
context-sync — Deterministic Linear ticket neighborhood snapshots.

Public API
----------
The primary entry point is :class:`ContextSync`, which receives an
authenticated ``linear-client`` ``Linear`` instance and a target directory.
All mutating and read-only operations are async methods that return
:class:`SyncResult` or :class:`DiffResult`.

.. code-block:: python

    from context_sync import ContextSync

    syncer = ContextSync(
        linear=linear_client_instance,
        context_dir=Path("linear-context"),
    )
    result = await syncer.sync(root_ticket_id="ACP-123")

Configuration constants, traversal dimensions, and the testing harness are
also importable from the package root.
"""

from context_sync._config import (
    DEFAULT_CONCURRENCY_LIMIT,
    DEFAULT_DIMENSIONS,
    DEFAULT_MAX_TICKETS_PER_ROOT,
    FORMAT_VERSION,
    TIER_1_DIMENSIONS,
    TIER_2_DIMENSIONS,
    TIER_3_DIMENSIONS,
    TRAVERSAL_TIERS,
    Dimension,
    resolve_dimensions,
)
from context_sync._errors import (
    ActiveLockError,
    ContextSyncError,
    DiffLockError,
    LockError,
    ManifestError,
    RootNotFoundError,
    RootNotInManifestError,
    StaleLockError,
    SystemicRemoteError,
    WorkspaceMismatchError,
    WriteError,
)
from context_sync._gateway import (
    AttachmentData,
    CommentData,
    IssueData,
    LinearGateway,
    RefreshCommentMeta,
    RefreshIssueMeta,
    RefreshThreadMeta,
    RelationData,
    ThreadData,
    TicketBundle,
    WorkspaceIdentity,
)
from context_sync._io import atomic_write, write_and_verify_ticket
from context_sync._lock import (
    LOCK_FILENAME,
    LockRecord,
    acquire_lock,
    inspect_lock,
    is_lock_stale,
    release_lock,
)
from context_sync._manifest import (
    MANIFEST_FILENAME,
    Manifest,
    ManifestRootEntry,
    ManifestSnapshot,
    ManifestTicketEntry,
    initialize_manifest,
    load_manifest,
    save_manifest,
)
from context_sync._models import DiffEntry, DiffResult, SyncError, SyncResult
from context_sync._pipeline import (
    TicketWriteResult,
    compute_refresh_cursor,
    fetch_tickets,
    make_ticket_ref_provider,
    write_ticket,
)
from context_sync._renderer import render_ticket_file
from context_sync._signatures import compute_comments_signature, compute_relations_signature
from context_sync._sync import ContextSync
from context_sync._traversal import (
    TicketRefProvider,
    TraversalResult,
    TraversedTicket,
    build_reachable_graph,
)
from context_sync.version import __prog_name__ as __prog_name__
from context_sync.version import __version__ as __version__

# Prevent the 'version' submodule from appearing as a public attribute.
del version  # type: ignore[name-defined]  # noqa: F821

__all__ = [
    # Core
    "ContextSync",
    # Result models
    "DiffEntry",
    "DiffResult",
    "SyncError",
    "SyncResult",
    # Errors
    "ActiveLockError",
    "ContextSyncError",
    "DiffLockError",
    "LockError",
    "ManifestError",
    "RootNotFoundError",
    "RootNotInManifestError",
    "StaleLockError",
    "SystemicRemoteError",
    "WorkspaceMismatchError",
    "WriteError",
    # Gateway types
    "AttachmentData",
    "CommentData",
    "IssueData",
    "LinearGateway",
    "RefreshCommentMeta",
    "RefreshIssueMeta",
    "RefreshThreadMeta",
    "RelationData",
    "ThreadData",
    "TicketBundle",
    "WorkspaceIdentity",
    # Manifest
    "MANIFEST_FILENAME",
    "Manifest",
    "ManifestRootEntry",
    "ManifestSnapshot",
    "ManifestTicketEntry",
    "initialize_manifest",
    "load_manifest",
    "save_manifest",
    # Lock
    "LOCK_FILENAME",
    "LockRecord",
    "acquire_lock",
    "inspect_lock",
    "is_lock_stale",
    "release_lock",
    # Pipeline
    "TicketWriteResult",
    "compute_refresh_cursor",
    "fetch_tickets",
    "make_ticket_ref_provider",
    "write_ticket",
    # Renderer
    "render_ticket_file",
    # Signatures
    "compute_comments_signature",
    "compute_relations_signature",
    # I/O
    "atomic_write",
    "write_and_verify_ticket",
    # Config
    "DEFAULT_CONCURRENCY_LIMIT",
    "DEFAULT_DIMENSIONS",
    "DEFAULT_MAX_TICKETS_PER_ROOT",
    "FORMAT_VERSION",
    "TIER_1_DIMENSIONS",
    "TIER_2_DIMENSIONS",
    "TIER_3_DIMENSIONS",
    "TRAVERSAL_TIERS",
    "Dimension",
    "resolve_dimensions",
    # Traversal
    "TicketRefProvider",
    "TraversalResult",
    "TraversedTicket",
    "build_reachable_graph",
    # Version / identity
    "__prog_name__",
    "__version__",
]
