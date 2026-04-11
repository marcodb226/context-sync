"""
Public-surface integration tests for CLI and library entry points (M5-2).

These tests exercise the **supported public runtime** — ``main()`` for CLI and
``ContextSync(linear=...)`` for the library — through the real
``RealLinearGateway`` wiring path.  They do *not* use ``_gateway_override``.
The upstream ``linear-client`` dependency is replaced by a maintained mock
``Linear`` transport double so no live workspace is required.

Coverage categories:
- CLI dispatch through ``main()`` and ``build_parser()`` with all four
  subcommands.
- Library construction via ``ContextSync(linear=mock_linear, ...)`` routed
  through ``RealLinearGateway`` for ``sync``, ``refresh``, ``remove``, ``diff``.
- JSON and text failure-contract regression for every ``ContextSyncError``
  subtype surfaced through ``main()``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from context_sync._cli import EXIT_ERROR, EXIT_SUCCESS, main
from context_sync._errors import (
    ActiveLockError,
    ContextSyncError,
    DiffLockError,
    ManifestError,
    RootNotFoundError,
    RootNotInManifestError,
    StaleLockError,
    SystemicRemoteError,
    WorkspaceMismatchError,
    WriteError,
)
from context_sync._types import IssueKey

# ---------------------------------------------------------------------------
# Mock linear-client transport double
# ---------------------------------------------------------------------------

_WS_ID = "ws-00000000-0000-0000-0000-000000000001"
_WS_SLUG = "test-workspace"
_ISSUE_ID = "00000000-0000-0000-0000-000000000001"
_ISSUE_KEY = "TEST-1"
_ISSUE_UPDATED = "2026-01-01T00:00:00Z"

_ISSUE_ID_2 = "00000000-0000-0000-0000-000000000002"
_ISSUE_KEY_2 = "TEST-2"


def _supplementary_response(
    *,
    ws_id: str = _WS_ID,
    ws_slug: str = _WS_SLUG,
    priority: int | None = 2,
    parent_id: str | None = None,
    parent_key: str | None = None,
    labels: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Raw GQL response for the supplementary issue query."""
    parent = None
    if parent_id:
        parent = {"id": parent_id, "identifier": parent_key}
    return {
        "data": {
            "issue": {
                "priority": priority,
                "parent": parent,
                "team": {
                    "organization": {
                        "id": ws_id,
                        "urlKey": ws_slug,
                    }
                },
                "labels": {
                    "nodes": labels or [],
                },
            }
        }
    }


def _workspace_identity_response(
    *,
    ws_id: str = _WS_ID,
    ws_slug: str = _WS_SLUG,
) -> dict[str, Any]:
    """Raw GQL response for the workspace identity query."""
    return {
        "data": {
            "issue": {
                "team": {
                    "organization": {
                        "id": ws_id,
                        "urlKey": ws_slug,
                    }
                }
            }
        }
    }


def _mock_issue(
    *,
    issue_id: str = _ISSUE_ID,
    issue_key: str = _ISSUE_KEY,
    title: str = "Test issue",
    updated_at: str = _ISSUE_UPDATED,
) -> MagicMock:
    """Build a mock ``linear_client`` Issue domain object."""
    issue = MagicMock()
    issue.peek_id.return_value = issue_id
    issue.peek_key.return_value = issue_key
    issue.peek_title.return_value = title
    issue.peek_description.return_value = "Test description."
    issue.peek_created_at.return_value = "2026-01-01T00:00:00Z"
    issue.peek_updated_at.return_value = updated_at

    status = MagicMock()
    status.peek_name.return_value = "Todo"
    issue.peek_status.return_value = status

    assignee = MagicMock()
    assignee.peek_name.return_value = "Alice"
    issue.peek_assignee.return_value = assignee

    creator = MagicMock()
    creator.peek_name.return_value = "Bob"
    issue.peek_creator.return_value = creator

    issue.fetch = AsyncMock(return_value=issue)
    issue.get_comments = AsyncMock(return_value=[])
    issue.get_attachments = AsyncMock(return_value=[])
    issue.get_links = AsyncMock(return_value=[])

    return issue


def _make_mock_linear(
    *,
    issues: dict[str, MagicMock] | None = None,
    gql_query_side_effect: Any = None,
    gql_paginate_side_effect: Any = None,
) -> MagicMock:
    """
    Build a mock ``Linear`` instance that ``RealLinearGateway`` can wrap.

    Supports multiple issues keyed by ID or key.  The ``issue()`` factory
    returns the correct mock based on the ``id=`` or ``key=`` kwarg.
    """
    linear = MagicMock()
    issue_map = issues or {_ISSUE_ID: _mock_issue(), _ISSUE_KEY: _mock_issue()}

    def _issue_factory(*, id: str | None = None, key: str | None = None) -> MagicMock:  # noqa: A002
        lookup = str(id) if id is not None else str(key)
        if lookup in issue_map:
            return issue_map[lookup]
        # Return a mock whose fetch() raises not-found.
        miss = MagicMock()
        miss.fetch = AsyncMock(side_effect=Exception(f"Not found: {lookup}"))
        return miss

    linear.issue = MagicMock(side_effect=_issue_factory)

    linear.gql = MagicMock()
    if gql_query_side_effect is not None:
        linear.gql.query = AsyncMock(side_effect=gql_query_side_effect)
    else:
        linear.gql.query = AsyncMock(side_effect=_default_gql_query_router)
    if gql_paginate_side_effect is not None:
        linear.gql.paginate_connection = AsyncMock(side_effect=gql_paginate_side_effect)
    else:
        linear.gql.paginate_connection = AsyncMock(side_effect=_default_gql_paginate_router)

    return linear


def _default_gql_query_router(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Route GQL query calls based on the operation name."""
    op = kwargs.get("operation_name", "")
    if op == "WorkspaceIdentity":
        return _workspace_identity_response()
    # Default: supplementary issue query.
    return _supplementary_response()


def _default_gql_paginate_router(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
    """Route GQL paginate calls based on the connection_path."""
    conn_path = kwargs.get("connection_path", [])
    if conn_path == ["issues"]:
        # Refresh issue metadata: return one visible issue.
        return [
            {
                "id": _ISSUE_ID,
                "identifier": _ISSUE_KEY,
                "updatedAt": _ISSUE_UPDATED,
            }
        ]
    if conn_path == ["comments"]:
        return []
    if conn_path in (["issue", "relations"], ["issue", "inverseRelations"]):
        return []
    return []


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context_dir(tmp_path: Path) -> Path:
    """Provide a clean context directory."""
    d = tmp_path / "context"
    d.mkdir()
    return d


@pytest.fixture()
def mock_linear() -> MagicMock:
    """Provide a mock Linear instance with one pre-loaded issue."""
    issue = _mock_issue()
    return _make_mock_linear(issues={_ISSUE_ID: issue, _ISSUE_KEY: issue})


# ---------------------------------------------------------------------------
# CLI integration through main()
# ---------------------------------------------------------------------------


class TestCliMainSync:
    """Exercise ``main()`` dispatch for the ``sync`` subcommand."""

    def test_sync_creates_ticket_file(
        self, context_dir: Path, mock_linear: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``context-sync sync TEST-1`` creates a ticket file via main()."""
        with (
            patch("context_sync._cli._create_linear_client", return_value=mock_linear),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["sync", _ISSUE_KEY, "--context-dir", str(context_dir)])

        assert exc_info.value.code == EXIT_SUCCESS
        assert (context_dir / f"{_ISSUE_KEY}.md").is_file()
        captured = capsys.readouterr()
        assert _ISSUE_KEY in captured.out

    def test_sync_json_output(
        self, context_dir: Path, mock_linear: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``context-sync sync --json TEST-1`` emits valid JSON to stdout."""
        with (
            patch("context_sync._cli._create_linear_client", return_value=mock_linear),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["sync", _ISSUE_KEY, "--context-dir", str(context_dir), "--json"])

        assert exc_info.value.code == EXIT_SUCCESS
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert "created" in payload

    def test_sync_standalone_rebuild(self, context_dir: Path, mock_linear: MagicMock) -> None:
        """``context-sync sync`` without a ticket performs a standalone rebuild."""
        # Bootstrap a snapshot first.
        with (
            patch("context_sync._cli._create_linear_client", return_value=mock_linear),
            pytest.raises(SystemExit),
        ):
            main(["sync", _ISSUE_KEY, "--context-dir", str(context_dir)])

        # Standalone rebuild.
        with (
            patch("context_sync._cli._create_linear_client", return_value=mock_linear),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["sync", "--context-dir", str(context_dir)])

        assert exc_info.value.code == EXIT_SUCCESS


class TestCliMainRefresh:
    """Exercise ``main()`` dispatch for the ``refresh`` subcommand."""

    def test_refresh_after_sync(self, context_dir: Path, mock_linear: MagicMock) -> None:
        """``context-sync refresh`` succeeds after a sync."""
        with (
            patch("context_sync._cli._create_linear_client", return_value=mock_linear),
            pytest.raises(SystemExit),
        ):
            main(["sync", _ISSUE_KEY, "--context-dir", str(context_dir)])

        with (
            patch("context_sync._cli._create_linear_client", return_value=mock_linear),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["refresh", "--context-dir", str(context_dir)])

        assert exc_info.value.code == EXIT_SUCCESS

    def test_refresh_json_output(
        self,
        context_dir: Path,
        mock_linear: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``context-sync refresh --json`` emits valid JSON."""
        with (
            patch("context_sync._cli._create_linear_client", return_value=mock_linear),
            pytest.raises(SystemExit),
        ):
            main(["sync", _ISSUE_KEY, "--context-dir", str(context_dir)])

        # Discard bootstrap output before capturing the target command.
        capsys.readouterr()

        with (
            patch("context_sync._cli._create_linear_client", return_value=mock_linear),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["refresh", "--context-dir", str(context_dir), "--json"])

        assert exc_info.value.code == EXIT_SUCCESS
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert "created" in payload or "unchanged" in payload


class TestCliMainRemove:
    """Exercise ``main()`` dispatch for the ``remove`` subcommand."""

    def test_remove_after_sync(self, context_dir: Path, mock_linear: MagicMock) -> None:
        """``context-sync remove TEST-1`` succeeds after syncing that root."""
        with (
            patch("context_sync._cli._create_linear_client", return_value=mock_linear),
            pytest.raises(SystemExit),
        ):
            main(["sync", _ISSUE_KEY, "--context-dir", str(context_dir)])

        with (
            patch("context_sync._cli._create_linear_client", return_value=mock_linear),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["remove", _ISSUE_KEY, "--context-dir", str(context_dir)])

        assert exc_info.value.code == EXIT_SUCCESS

    def test_remove_json_output(
        self,
        context_dir: Path,
        mock_linear: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``context-sync remove --json TEST-1`` emits valid JSON."""
        with (
            patch("context_sync._cli._create_linear_client", return_value=mock_linear),
            pytest.raises(SystemExit),
        ):
            main(["sync", _ISSUE_KEY, "--context-dir", str(context_dir)])

        capsys.readouterr()

        with (
            patch("context_sync._cli._create_linear_client", return_value=mock_linear),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["remove", _ISSUE_KEY, "--context-dir", str(context_dir), "--json"])

        assert exc_info.value.code == EXIT_SUCCESS
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert "removed" in payload


class TestCliMainDiff:
    """Exercise ``main()`` dispatch for the ``diff`` subcommand."""

    def test_diff_after_sync(self, context_dir: Path, mock_linear: MagicMock) -> None:
        """``context-sync diff`` succeeds after a sync."""
        with (
            patch("context_sync._cli._create_linear_client", return_value=mock_linear),
            pytest.raises(SystemExit),
        ):
            main(["sync", _ISSUE_KEY, "--context-dir", str(context_dir)])

        with (
            patch("context_sync._cli._create_linear_client", return_value=mock_linear),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["diff", "--context-dir", str(context_dir)])

        assert exc_info.value.code == EXIT_SUCCESS

    def test_diff_json_output(
        self,
        context_dir: Path,
        mock_linear: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``context-sync diff --json`` emits valid JSON."""
        with (
            patch("context_sync._cli._create_linear_client", return_value=mock_linear),
            pytest.raises(SystemExit),
        ):
            main(["sync", _ISSUE_KEY, "--context-dir", str(context_dir)])

        capsys.readouterr()

        with (
            patch("context_sync._cli._create_linear_client", return_value=mock_linear),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["diff", "--context-dir", str(context_dir), "--json"])

        assert exc_info.value.code == EXIT_SUCCESS
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert "entries" in payload


class TestCliMainLogLevel:
    """Verify that ``--log-level`` is wired through main()."""

    def test_log_level_debug(self, context_dir: Path, mock_linear: MagicMock) -> None:
        """``--log-level DEBUG`` does not crash during dispatch."""
        with (
            patch("context_sync._cli._create_linear_client", return_value=mock_linear),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(
                [
                    "--log-level",
                    "DEBUG",
                    "sync",
                    _ISSUE_KEY,
                    "--context-dir",
                    str(context_dir),
                ]
            )

        assert exc_info.value.code == EXIT_SUCCESS

    def test_log_level_off(self, context_dir: Path, mock_linear: MagicMock) -> None:
        """``--log-level OFF`` suppresses all diagnostic output."""
        with (
            patch("context_sync._cli._create_linear_client", return_value=mock_linear),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(
                [
                    "--log-level",
                    "OFF",
                    "sync",
                    _ISSUE_KEY,
                    "--context-dir",
                    str(context_dir),
                ]
            )

        assert exc_info.value.code == EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Library entry point: ContextSync(linear=...) through RealLinearGateway
# ---------------------------------------------------------------------------


class TestLibraryPublicEntryPoint:
    """Exercise ``ContextSync(linear=mock_linear)`` without ``_gateway_override``."""

    async def test_sync_through_real_gateway(
        self, context_dir: Path, mock_linear: MagicMock
    ) -> None:
        """``ContextSync(linear=...)`` sync produces ticket files."""
        from context_sync._sync import ContextSync

        ctx = ContextSync(linear=mock_linear, context_dir=context_dir)
        result = await ctx.sync(key=_ISSUE_KEY)

        assert IssueKey(_ISSUE_KEY) in result.created
        assert (context_dir / f"{_ISSUE_KEY}.md").is_file()

    async def test_refresh_through_real_gateway(
        self, context_dir: Path, mock_linear: MagicMock
    ) -> None:
        """``refresh()`` succeeds after ``sync()`` through the real gateway."""
        from context_sync._sync import ContextSync

        ctx = ContextSync(linear=mock_linear, context_dir=context_dir)
        await ctx.sync(key=_ISSUE_KEY)
        result = await ctx.refresh()

        # Refresh should complete without error.
        assert result is not None

    async def test_remove_through_real_gateway(
        self, context_dir: Path, mock_linear: MagicMock
    ) -> None:
        """``remove()`` succeeds after ``sync()`` through the real gateway."""
        from context_sync._sync import ContextSync

        ctx = ContextSync(linear=mock_linear, context_dir=context_dir)
        await ctx.sync(key=_ISSUE_KEY)
        result = await ctx.remove(key=_ISSUE_KEY)

        assert IssueKey(_ISSUE_KEY) in result.removed

    async def test_diff_through_real_gateway(
        self, context_dir: Path, mock_linear: MagicMock
    ) -> None:
        """``diff()`` succeeds after ``sync()`` through the real gateway."""
        from context_sync._sync import ContextSync

        ctx = ContextSync(linear=mock_linear, context_dir=context_dir)
        await ctx.sync(key=_ISSUE_KEY)
        result = await ctx.diff()

        assert result is not None
        assert hasattr(result, "entries")

    async def test_sync_by_uuid(self, context_dir: Path, mock_linear: MagicMock) -> None:
        """Sync with a UUID routes through the ``id=`` constructor path."""
        from context_sync._sync import ContextSync

        ctx = ContextSync(linear=mock_linear, context_dir=context_dir)
        result = await ctx.sync(key=_ISSUE_ID)

        assert IssueKey(_ISSUE_KEY) in result.created
        # Verify the mock was called with id= (UUID pattern).
        mock_linear.issue.assert_called()
        call_kwargs = mock_linear.issue.call_args
        assert call_kwargs.kwargs.get("id") is not None

    async def test_sync_by_key(self, context_dir: Path, mock_linear: MagicMock) -> None:
        """Sync with an issue key routes through the ``key=`` constructor path."""
        from context_sync._sync import ContextSync

        ctx = ContextSync(linear=mock_linear, context_dir=context_dir)
        result = await ctx.sync(key=_ISSUE_KEY)

        assert IssueKey(_ISSUE_KEY) in result.created
        # The first issue() call should use key= (non-UUID input).
        # Later calls from traversal may use id= for resolved UUIDs.
        first_call = mock_linear.issue.call_args_list[0]
        assert first_call.kwargs.get("key") is not None

    async def test_constructor_without_linear_raises(self) -> None:
        """``ContextSync()`` without ``linear`` or ``_gateway_override`` raises."""
        from context_sync._sync import ContextSync

        with pytest.raises(ContextSyncError, match="Either 'linear' or '_gateway_override'"):
            ContextSync(context_dir=".")


# ---------------------------------------------------------------------------
# Failure-contract regression tests: text and JSON error output via main()
# ---------------------------------------------------------------------------


class TestFailureContractText:
    """Verify text-mode error output for all ``ContextSyncError`` subtypes."""

    @pytest.mark.parametrize(
        ("error_cls", "message"),
        [
            (ContextSyncError, "generic context-sync error"),
            (ActiveLockError, "lock held by another process"),
            (StaleLockError, "stale lock detected"),
            (DiffLockError, "mutating run in progress"),
            (WorkspaceMismatchError, "workspace mismatch"),
            (RootNotFoundError, "root not found upstream"),
            (RootNotInManifestError, "root not in manifest"),
            (ManifestError, "corrupt manifest"),
            (SystemicRemoteError, "upstream service unavailable"),
            (WriteError, "failed to write ticket file"),
        ],
    )
    def test_error_exits_1_with_message_on_stderr(
        self,
        error_cls: type[ContextSyncError],
        message: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Each error type produces exit code 1 and the message on stderr."""

        async def _raise(_args: object) -> int:
            raise error_cls(message)

        with (
            patch("context_sync._cli._HANDLERS", {"refresh": _raise}),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["refresh"])

        assert exc_info.value.code == EXIT_ERROR
        captured = capsys.readouterr()
        assert message in captured.err

    def test_value_error_exits_1(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``ValueError`` from the handler produces exit code 1."""

        async def _raise(_args: object) -> int:
            raise ValueError("invalid dimension depth")

        with (
            patch("context_sync._cli._HANDLERS", {"sync": _raise}),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["sync", "TEST-1"])

        assert exc_info.value.code == EXIT_ERROR
        captured = capsys.readouterr()
        assert "invalid dimension depth" in captured.err


class TestFailureContractJson:
    """Verify JSON-mode error output for all ``ContextSyncError`` subtypes."""

    @pytest.mark.parametrize(
        ("error_cls", "expected_type", "message"),
        [
            (ContextSyncError, "ContextSyncError", "generic error"),
            (ActiveLockError, "ActiveLockError", "lock held"),
            (StaleLockError, "StaleLockError", "stale lock"),
            (DiffLockError, "DiffLockError", "diff blocked"),
            (WorkspaceMismatchError, "WorkspaceMismatchError", "wrong workspace"),
            (RootNotFoundError, "RootNotFoundError", "not found"),
            (RootNotInManifestError, "RootNotInManifestError", "not a root"),
            (ManifestError, "ManifestError", "corrupt"),
            (SystemicRemoteError, "SystemicRemoteError", "upstream failure"),
            (WriteError, "WriteError", "write failed"),
        ],
    )
    def test_error_exits_1_with_json_on_stdout(
        self,
        error_cls: type[ContextSyncError],
        expected_type: str,
        message: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Each error type produces exit code 1 and a JSON error payload on stdout."""

        async def _raise(_args: object) -> int:
            raise error_cls(message)

        with (
            patch("context_sync._cli._HANDLERS", {"diff": _raise}),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["diff", "--json"])

        assert exc_info.value.code == EXIT_ERROR
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["error"] == expected_type
        assert message in payload["message"]

    def test_value_error_json_output(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``ValueError`` in JSON mode emits a structured error payload."""

        async def _raise(_args: object) -> int:
            raise ValueError("bad depth value")

        with (
            patch("context_sync._cli._HANDLERS", {"sync": _raise}),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["sync", "TEST-1", "--json"])

        assert exc_info.value.code == EXIT_ERROR
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["error"] == "ValueError"
        assert "bad depth value" in payload["message"]


# ---------------------------------------------------------------------------
# Bootstrap failure paths through main()
# ---------------------------------------------------------------------------


class TestBootstrapFailuresThroughMain:
    """Verify bootstrap failures route through the public error surface."""

    def test_missing_linear_client_text(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Missing linear-client exits 1 with a message on stderr."""
        with (
            patch(
                "context_sync._cli._create_linear_client",
                side_effect=ContextSyncError("linear-client is not installed"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["sync", "TEST-1"])

        assert exc_info.value.code == EXIT_ERROR
        captured = capsys.readouterr()
        assert "linear-client is not installed" in captured.err

    def test_missing_linear_client_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Missing linear-client in JSON mode emits a structured payload."""
        with (
            patch(
                "context_sync._cli._create_linear_client",
                side_effect=ContextSyncError("linear-client is not installed"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["sync", "TEST-1", "--json"])

        assert exc_info.value.code == EXIT_ERROR
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["error"] == "ContextSyncError"
        assert "linear-client" in payload["message"]

    def test_auth_failure_text(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Auth failure exits 1 with a message on stderr."""
        with (
            patch(
                "context_sync._cli._create_linear_client",
                side_effect=ContextSyncError("Failed to initialize Linear client: auth failed"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["sync", "TEST-1"])

        assert exc_info.value.code == EXIT_ERROR
        captured = capsys.readouterr()
        assert "auth failed" in captured.err

    def test_auth_failure_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Auth failure in JSON mode emits a structured payload."""
        with (
            patch(
                "context_sync._cli._create_linear_client",
                side_effect=ContextSyncError("Failed to initialize Linear client: auth failed"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["sync", "TEST-1", "--json"])

        assert exc_info.value.code == EXIT_ERROR
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert "auth failed" in payload["message"]
