"""
Package import boundary tests.

These tests verify that the public API surface documented in ``__init__.py``
is importable from the package root and that internal modules stay behind
their underscore-prefixed boundaries.
"""

from __future__ import annotations


class TestPublicImports:
    """All advertised public names are importable from ``context_sync``."""

    def test_syncer(self) -> None:
        from context_sync import ContextSync

        assert ContextSync is not None

    def test_result_models(self) -> None:
        from context_sync import DiffEntry, DiffResult, SyncError, SyncResult

        for cls in (SyncResult, SyncError, DiffResult, DiffEntry):
            assert cls is not None

    def test_error_hierarchy(self) -> None:
        from context_sync import (
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

        # All errors derive from the base.
        for exc_cls in (
            ActiveLockError,
            DiffLockError,
            LockError,
            ManifestError,
            RootNotFoundError,
            RootNotInManifestError,
            StaleLockError,
            SystemicRemoteError,
            WorkspaceMismatchError,
            WriteError,
        ):
            assert issubclass(exc_cls, ContextSyncError)

    def test_lock_error_subtree(self) -> None:
        from context_sync import (
            ActiveLockError,
            DiffLockError,
            LockError,
            StaleLockError,
        )

        for exc_cls in (ActiveLockError, StaleLockError, DiffLockError):
            assert issubclass(exc_cls, LockError)

    def test_gateway_types(self) -> None:
        from context_sync import (
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

        for cls in (
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
        ):
            assert cls is not None

    def test_config_constants(self) -> None:
        from context_sync import (
            DEFAULT_CONCURRENCY_LIMIT,
            DEFAULT_DIMENSIONS,
            DEFAULT_MAX_TICKETS_PER_ROOT,
            FORMAT_VERSION,
            TRAVERSAL_TIERS,
            Dimension,
            resolve_dimensions,
        )

        assert isinstance(DEFAULT_DIMENSIONS, dict)
        assert isinstance(DEFAULT_MAX_TICKETS_PER_ROOT, int)
        assert isinstance(DEFAULT_CONCURRENCY_LIMIT, int)
        assert isinstance(FORMAT_VERSION, int)
        assert isinstance(TRAVERSAL_TIERS, tuple)
        assert Dimension is not None
        assert callable(resolve_dimensions)

    def test_manifest_types(self) -> None:
        from context_sync import (
            MANIFEST_FILENAME,
            Manifest,
            ManifestRootEntry,
            ManifestSnapshot,
            ManifestTicketEntry,
            initialize_manifest,
            load_manifest,
            save_manifest,
        )

        for name in (
            MANIFEST_FILENAME,
            Manifest,
            ManifestRootEntry,
            ManifestSnapshot,
            ManifestTicketEntry,
        ):
            assert name is not None
        for fn in (initialize_manifest, load_manifest, save_manifest):
            assert callable(fn)

    def test_lock_types(self) -> None:
        from context_sync import (
            LOCK_FILENAME,
            LockRecord,
            acquire_lock,
            inspect_lock,
            is_lock_stale,
            release_lock,
        )

        assert LOCK_FILENAME is not None
        assert LockRecord is not None
        for fn in (acquire_lock, inspect_lock, is_lock_stale, release_lock):
            assert callable(fn)

    def test_renderer_and_signatures(self) -> None:
        from context_sync import (
            compute_comments_signature,
            compute_relations_signature,
            render_ticket_file,
        )

        for fn in (render_ticket_file, compute_comments_signature, compute_relations_signature):
            assert callable(fn)

    def test_io_utilities(self) -> None:
        from context_sync import atomic_write, write_and_verify_ticket

        for fn in (atomic_write, write_and_verify_ticket):
            assert callable(fn)

    def test_pipeline_functions(self) -> None:
        from context_sync import (
            TicketWriteResult,
            compute_refresh_cursor,
            fetch_tickets,
            make_ticket_ref_provider,
            write_ticket,
        )

        assert TicketWriteResult is not None
        for fn in (compute_refresh_cursor, fetch_tickets, make_ticket_ref_provider, write_ticket):
            assert callable(fn)

    def test_traversal_types(self) -> None:
        from context_sync import (
            TicketRefProvider,
            TraversalResult,
            TraversedTicket,
            build_reachable_graph,
        )

        assert TicketRefProvider is not None
        assert TraversedTicket is not None
        assert TraversalResult is not None
        assert callable(build_reachable_graph)

    def test_version(self) -> None:
        from context_sync import __version__

        assert isinstance(__version__, str)
        assert "dev" in __version__  # pre-release marker


class TestAllExports:
    """``__all__`` is consistent with the actual module namespace."""

    def test_all_names_importable(self) -> None:
        import context_sync

        for name in context_sync.__all__:
            assert hasattr(context_sync, name), f"{name} listed in __all__ but missing"

    def test_no_extra_public_names(self) -> None:
        """Public names not in __all__ should be underscore-prefixed."""
        import context_sync

        exported = set(context_sync.__all__)
        for name in dir(context_sync):
            if name.startswith("_"):
                continue
            assert name in exported, f"{name} is a public name not listed in __all__"
