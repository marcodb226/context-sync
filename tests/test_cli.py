"""
Tests for the CLI surface (M4-1).

Exercises command parsing, human-readable output, JSON output, error-code
behavior, lock-error text, and missing-root-policy selection.  All tests use
the :class:`FakeLinearGateway` so no real Linear calls are made.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import patch

import pytest

from context_sync._cli import (
    DEFAULT_LOG_LEVEL,
    EXIT_ERROR,
    EXIT_SUCCESS,
    PROG_NAME,
    _format_diff_result_text,
    _format_sync_result_text,
    build_parser,
    main,
)
from context_sync._errors import (
    ActiveLockError,
    ContextSyncError,
    DiffLockError,
    ManifestError,
    RootNotFoundError,
    RootNotInManifestError,
    StaleLockError,
    WorkspaceMismatchError,
)
from context_sync._models import DiffEntry, DiffResult, SyncError, SyncResult
from context_sync.version import __version__

# ---------------------------------------------------------------------------
# Parser construction and argument validation
# ---------------------------------------------------------------------------


class TestParserConstruction:
    """Verify that ``build_parser`` produces a correctly shaped parser."""

    def test_version_flag_long(self, capsys: pytest.CaptureFixture[str]) -> None:
        """``--version`` prints tool name and version and exits."""
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert PROG_NAME in captured.out
        assert __version__ in captured.out

    def test_version_flag_short(self, capsys: pytest.CaptureFixture[str]) -> None:
        """``-v`` is the short form for ``--version``, not verbose."""
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["-v"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert PROG_NAME in captured.out
        assert __version__ in captured.out

    def test_no_command_exits_with_error(self) -> None:
        """Calling with no subcommand should fail."""
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args([])
        assert exc_info.value.code == 2

    def test_sync_requires_root_ticket(self) -> None:
        """``sync`` without a root ticket should fail."""
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["sync"])
        assert exc_info.value.code == 2

    def test_sync_parses_all_options(self) -> None:
        """``sync`` accepts root ticket plus all optional flags."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "sync",
                "ACP-123",
                "--context-dir",
                "/tmp/ctx",
                "--max-tickets-per-root",
                "50",
                "--depth-blocks",
                "5",
                "--depth-relates-to",
                "2",
                "--json",
            ]
        )
        assert args.command == "sync"
        assert args.root_ticket == "ACP-123"
        assert args.context_dir == "/tmp/ctx"
        assert args.max_tickets_per_root == 50
        assert args.depth_blocks == 5
        assert args.depth_relates_to == 2
        assert args.json is True

    def test_refresh_defaults(self) -> None:
        """``refresh`` uses default missing-root-policy."""
        parser = build_parser()
        args = parser.parse_args(["refresh"])
        assert args.command == "refresh"
        assert args.missing_root_policy == "quarantine"
        assert args.json is False

    def test_refresh_with_remove_policy(self) -> None:
        """``refresh --missing-root-policy remove`` is accepted."""
        parser = build_parser()
        args = parser.parse_args(["refresh", "--missing-root-policy", "remove"])
        assert args.missing_root_policy == "remove"

    def test_add_requires_ticket_ref(self) -> None:
        """``add`` without a ticket ref should fail."""
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["add"])
        assert exc_info.value.code == 2

    def test_add_parses_correctly(self) -> None:
        """``add`` accepts a ticket ref."""
        parser = build_parser()
        args = parser.parse_args(["add", "ACP-999", "--context-dir", "my-ctx"])
        assert args.command == "add"
        assert args.ticket_ref == "ACP-999"
        assert args.context_dir == "my-ctx"

    def test_remove_root_requires_ticket_ref(self) -> None:
        """``remove-root`` without a ticket ref should fail."""
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["remove-root"])
        assert exc_info.value.code == 2

    def test_remove_root_parses_correctly(self) -> None:
        """``remove-root`` accepts a ticket ref."""
        parser = build_parser()
        args = parser.parse_args(["remove-root", "ACP-100"])
        assert args.command == "remove-root"
        assert args.ticket_ref == "ACP-100"

    def test_diff_defaults(self) -> None:
        """``diff`` with no extra flags uses defaults."""
        parser = build_parser()
        args = parser.parse_args(["diff"])
        assert args.command == "diff"
        assert args.json is False

    def test_diff_with_json(self) -> None:
        """``diff --json`` sets the json flag."""
        parser = build_parser()
        args = parser.parse_args(["diff", "--json"])
        assert args.json is True

    def test_log_level_defaults_to_warning(self) -> None:
        """``--log-level`` defaults to WARNING."""
        parser = build_parser()
        args = parser.parse_args(["refresh"])
        assert args.log_level == DEFAULT_LOG_LEVEL

    def test_log_level_debug(self) -> None:
        """``--log-level DEBUG`` is accepted."""
        parser = build_parser()
        args = parser.parse_args(["--log-level", "DEBUG", "refresh"])
        assert args.log_level == "DEBUG"

    def test_log_level_off(self) -> None:
        """``--log-level OFF`` is accepted."""
        parser = build_parser()
        args = parser.parse_args(["--log-level", "OFF", "diff"])
        assert args.log_level == "OFF"

    def test_log_level_invalid_rejected(self) -> None:
        """An invalid log level is rejected."""
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--log-level", "TRACE", "diff"])
        assert exc_info.value.code == 2

    def test_context_dir_defaults_to_cwd(self) -> None:
        """``--context-dir`` defaults to ``.``."""
        parser = build_parser()
        args = parser.parse_args(["refresh"])
        assert args.context_dir == "."


# ---------------------------------------------------------------------------
# Output formatting — SyncResult
# ---------------------------------------------------------------------------


class TestSyncResultFormatting:
    """Verify human-readable text formatting for ``SyncResult``."""

    def test_empty_result(self) -> None:
        """An empty result prints a no-changes message."""
        result = SyncResult()
        assert _format_sync_result_text(result) == "No changes."

    def test_created_only(self) -> None:
        """Only created tickets are listed."""
        result = SyncResult(created=["ACP-1", "ACP-2"])
        text = _format_sync_result_text(result)
        assert "Created (2):" in text
        assert "ACP-1" in text
        assert "ACP-2" in text

    def test_all_categories(self) -> None:
        """All categories appear when populated."""
        result = SyncResult(
            created=["ACP-1"],
            updated=["ACP-2"],
            unchanged=["ACP-3"],
            removed=["ACP-4"],
            errors=[SyncError("ACP-5", "api_error", "Timeout", retriable=True)],
        )
        text = _format_sync_result_text(result)
        assert "Created (1):" in text
        assert "Updated (1):" in text
        assert "Unchanged (1):" in text
        assert "Removed (1):" in text
        assert "Error [api_error] ACP-5: Timeout" in text

    def test_quarantined_root_visible_in_errors(self) -> None:
        """Root quarantine errors show the error type clearly."""
        result = SyncResult(
            errors=[
                SyncError(
                    "ACP-10",
                    "root_quarantined",
                    "Root not visible in current view",
                    retriable=False,
                ),
            ],
        )
        text = _format_sync_result_text(result)
        assert "root_quarantined" in text
        assert "ACP-10" in text


# ---------------------------------------------------------------------------
# Output formatting — DiffResult
# ---------------------------------------------------------------------------


class TestDiffResultFormatting:
    """Verify human-readable text formatting for ``DiffResult``."""

    def test_empty_diff(self) -> None:
        """An empty diff prints a no-tickets message."""
        result = DiffResult()
        assert _format_diff_result_text(result) == "No tracked tickets."

    def test_stale_with_changed_fields(self) -> None:
        """Stale entries show the changed cursor fields."""
        result = DiffResult(
            entries=[
                DiffEntry("ACP-1", "stale", ["comments_signature", "issue_updated_at"]),
            ],
        )
        text = _format_diff_result_text(result)
        assert "Stale: ACP-1" in text
        assert "comments_signature" in text
        assert "issue_updated_at" in text

    def test_all_statuses(self) -> None:
        """All diff statuses appear when populated."""
        result = DiffResult(
            entries=[
                DiffEntry("ACP-1", "current", []),
                DiffEntry("ACP-2", "stale", ["relations_signature"]),
                DiffEntry("ACP-3", "missing_locally", []),
                DiffEntry("ACP-4", "missing_remotely", []),
            ],
        )
        text = _format_diff_result_text(result)
        assert "Current (1):" in text
        assert "Missing locally (1):" in text
        assert "Missing remotely (1):" in text
        assert "Stale: ACP-2" in text


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


class TestJsonOutput:
    """Verify that ``--json`` mode emits well-formed JSON."""

    def test_sync_result_json_is_valid(self) -> None:
        """``asdict(SyncResult)`` produces JSON-serializable output."""
        result = SyncResult(created=["ACP-1"], updated=["ACP-2"])
        payload = asdict(result)
        dumped = json.dumps(payload, indent=2, sort_keys=True)
        loaded = json.loads(dumped)
        assert loaded["created"] == ["ACP-1"]
        assert loaded["updated"] == ["ACP-2"]

    def test_diff_result_json_is_valid(self) -> None:
        """``asdict(DiffResult)`` produces JSON-serializable output."""
        result = DiffResult(
            entries=[DiffEntry("ACP-1", "stale", ["comments_signature"])],
        )
        payload = asdict(result)
        dumped = json.dumps(payload, indent=2, sort_keys=True)
        loaded = json.loads(dumped)
        assert loaded["entries"][0]["ticket_id"] == "ACP-1"
        assert loaded["entries"][0]["status"] == "stale"


# ---------------------------------------------------------------------------
# main() exit codes and error handling
# ---------------------------------------------------------------------------


class TestMainExitCodes:
    """Verify that ``main()`` translates errors into the correct exit codes."""

    def test_context_sync_error_exits_1_text(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A ``ContextSyncError`` from the handler produces exit code 1 and text."""

        async def _raise_error(_args: object) -> int:
            raise ActiveLockError("Lock held by another process")

        with (
            patch("context_sync._cli._HANDLERS", {"refresh": _raise_error}),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["refresh"])

        assert exc_info.value.code == EXIT_ERROR
        captured = capsys.readouterr()
        assert "Lock held by another process" in captured.err

    def test_context_sync_error_exits_1_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A ``ContextSyncError`` in JSON mode emits a JSON error object to stdout."""

        async def _raise_error(_args: object) -> int:
            raise DiffLockError("Mutating run in progress")

        with (
            patch("context_sync._cli._HANDLERS", {"diff": _raise_error}),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["diff", "--json"])

        assert exc_info.value.code == EXIT_ERROR
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["error"] == "DiffLockError"
        assert "Mutating run in progress" in payload["message"]

    def test_successful_handler_exits_0(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A successful handler returns exit code 0."""

        async def _succeed(_args: object) -> int:
            print("OK")
            return EXIT_SUCCESS

        with (
            patch("context_sync._cli._HANDLERS", {"diff": _succeed}),
            pytest.raises(SystemExit) as exc_info,
        ):
            main(["diff"])

        assert exc_info.value.code == EXIT_SUCCESS

    def test_various_error_types_exit_1(self) -> None:
        """All ContextSyncError subtypes produce exit code 1."""
        error_types = [
            ActiveLockError("lock active"),
            StaleLockError("lock stale"),
            DiffLockError("diff blocked"),
            WorkspaceMismatchError("wrong workspace"),
            RootNotFoundError("root missing"),
            RootNotInManifestError("not a root"),
            ManifestError("corrupt manifest"),
            ContextSyncError("generic error"),
        ]
        for error in error_types:

            async def _raise(_args: object, exc: Exception = error) -> int:
                raise exc

            with (
                patch("context_sync._cli._HANDLERS", {"refresh": _raise}),
                pytest.raises(SystemExit) as exc_info,
            ):
                main(["refresh"])

            assert exc_info.value.code == EXIT_ERROR, f"{type(error).__name__} should exit 1"


# ---------------------------------------------------------------------------
# Lock-error text visibility
# ---------------------------------------------------------------------------


class TestLockErrorText:
    """Verify that lock contention messages are visible without debug logging."""

    def test_active_lock_message_in_text(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Active-lock refusal shows a clear message on stderr."""

        async def _raise(_args: object) -> int:
            raise ActiveLockError(
                "Context directory is locked by PID 12345 on host dev-01. "
                "Retry after the lock clears."
            )

        with (
            patch("context_sync._cli._HANDLERS", {"sync": _raise}),
            pytest.raises(SystemExit),
        ):
            main(["sync", "ACP-1"])

        captured = capsys.readouterr()
        assert "PID 12345" in captured.err
        assert "Retry after the lock clears" in captured.err

    def test_stale_lock_message_in_text(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Stale-lock error shows a clear message on stderr."""

        async def _raise(_args: object) -> int:
            raise StaleLockError(
                "Lock staleness cannot be determined safely. "
                "Inspect or remove .context-sync.lock manually."
            )

        with (
            patch("context_sync._cli._HANDLERS", {"refresh": _raise}),
            pytest.raises(SystemExit),
        ):
            main(["refresh"])

        captured = capsys.readouterr()
        assert "staleness cannot be determined" in captured.err

    def test_diff_lock_message_in_text(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Diff-lock error explains why diff refuses to run."""

        async def _raise(_args: object) -> int:
            raise DiffLockError(
                "A mutating operation owns the context directory. "
                "Running diff now would compete for rate-limited Linear API calls. "
                "Retry after the lock clears."
            )

        with (
            patch("context_sync._cli._HANDLERS", {"diff": _raise}),
            pytest.raises(SystemExit),
        ):
            main(["diff"])

        captured = capsys.readouterr()
        assert "compete for rate-limited" in captured.err
        assert "Retry after the lock clears" in captured.err

    def test_diff_lock_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Diff-lock error in JSON mode includes the error type."""

        async def _raise(_args: object) -> int:
            raise DiffLockError("Locked")

        with (
            patch("context_sync._cli._HANDLERS", {"diff": _raise}),
            pytest.raises(SystemExit),
        ):
            main(["diff", "--json"])

        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["error"] == "DiffLockError"


# ---------------------------------------------------------------------------
# Missing-root-policy selection
# ---------------------------------------------------------------------------


class TestMissingRootPolicySelection:
    """Verify the ``--missing-root-policy`` flag reaches the handler."""

    def test_quarantine_is_default(self) -> None:
        """The default missing-root-policy is quarantine."""
        parser = build_parser()
        args = parser.parse_args(["refresh"])
        assert args.missing_root_policy == "quarantine"

    def test_remove_is_accepted(self) -> None:
        """``--missing-root-policy remove`` is parsed correctly."""
        parser = build_parser()
        args = parser.parse_args(["refresh", "--missing-root-policy", "remove"])
        assert args.missing_root_policy == "remove"

    def test_invalid_policy_rejected(self) -> None:
        """An invalid policy value is rejected by argparse."""
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["refresh", "--missing-root-policy", "ignore"])
        assert exc_info.value.code == 2
