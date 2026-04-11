"""
Thin CLI wrapper over the async ``ContextSync`` library API.

The CLI is the human-facing and shell-invocation entry point documented in the
top-level design (§2).  All flow logic remains in the library layer so behavior
is never forked between human and programmatic callers.

Entry point
-----------
``main()`` is the console-script entry point registered by ``pyproject.toml``.
It uses ``asyncio.run()`` as the sole async bridge.

Output modes
------------
- **Human-readable** (default): concise text to stdout.
- **Machine-readable** (``--json``): JSON to stdout, one top-level object per
  invocation.

Exit codes
----------
- ``0`` — success
- ``1`` — operational error (lock contention, workspace mismatch, manifest
  error, root-not-found, remote failure, etc.)
- ``2`` — usage / argument error (argparse default)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections.abc import Callable, Coroutine
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal, NoReturn

from context_sync._config import DEFAULT_DIMENSIONS, DEFAULT_MAX_TICKETS_PER_ROOT, Dimension
from context_sync._errors import ContextSyncError
from context_sync._models import DiffResult, SyncResult
from context_sync.version import __prog_name__, __version__

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXIT_SUCCESS: int = 0
EXIT_ERROR: int = 1

AUTH_MODE_CHOICES: tuple[str, ...] = ("oauth", "client_credentials", "api_key")
"""Valid ``--auth-mode`` values matching the ``linear-client`` auth modes."""

LOG_LEVEL_CHOICES: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "OFF")
"""Valid ``--log-level`` values."""

DEFAULT_LOG_LEVEL: str = "WARNING"
"""Log level applied when ``--log-level`` is not supplied."""

_VERSION_STRING: str = f"{__prog_name__} {__version__}"
"""Pre-formatted version string shared by ``-v``, ``-h``, and error output."""

_AuthMode = Literal["oauth", "client_credentials", "api_key"]
"""Auth modes accepted by ``linear-client``'s ``Linear()`` constructor."""

_Handler = Callable[..., Coroutine[Any, Any, int]]
"""Type alias for async subcommand handlers (R7)."""

# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _format_sync_result_text(result: SyncResult) -> str:
    """
    Format a ``SyncResult`` as concise human-readable text.

    Each non-empty category is listed on its own line with a count and the
    affected issue keys.  The output distinguishes active-lock refusal,
    stale-lock preemption, and root quarantine without requiring debug logging.
    """
    lines: list[str] = []

    if result.created:
        lines.append(f"Created ({len(result.created)}): {', '.join(sorted(result.created))}")
    if result.updated:
        lines.append(f"Updated ({len(result.updated)}): {', '.join(sorted(result.updated))}")
    if result.unchanged:
        lines.append(f"Unchanged ({len(result.unchanged)}): {', '.join(sorted(result.unchanged))}")
    if result.removed:
        lines.append(f"Removed ({len(result.removed)}): {', '.join(sorted(result.removed))}")
    if result.errors:
        for err in result.errors:
            lines.append(f"Error [{err.error_type}] {err.ticket_key}: {err.message}")

    if not lines:
        lines.append("No changes.")

    return "\n".join(lines)


def _format_diff_result_text(result: DiffResult) -> str:
    """
    Format a ``DiffResult`` as concise human-readable text.

    Entries are grouped by drift status.  Stale entries include the list of
    changed cursor fields.
    """
    lines: list[str] = []

    current = [e for e in result.entries if e.status == "current"]
    stale = [e for e in result.entries if e.status == "stale"]
    missing_local = [e for e in result.entries if e.status == "missing_locally"]
    missing_remote = [e for e in result.entries if e.status == "missing_remotely"]

    if current:
        lines.append(f"Current ({len(current)}): {', '.join(e.ticket_key for e in current)}")
    if stale:
        for entry in stale:
            fields = ", ".join(entry.changed_fields) if entry.changed_fields else "unknown"
            lines.append(f"Stale: {entry.ticket_key} [{fields}]")
    if missing_local:
        keys = ", ".join(e.ticket_key for e in missing_local)
        lines.append(f"Missing locally ({len(missing_local)}): {keys}")
    if missing_remote:
        keys = ", ".join(e.ticket_key for e in missing_remote)
        lines.append(f"Missing remotely ({len(missing_remote)}): {keys}")
    if result.errors:
        for err in result.errors:
            lines.append(f"Error [{err.error_type}] {err.ticket_key}: {err.message}")

    if not lines:
        lines.append("No tracked tickets.")

    return "\n".join(lines)


def _emit(text_output: str, json_output: dict[str, object], *, use_json: bool) -> None:
    """
    Write the formatted result to stdout.

    Parameters
    ----------
    text_output:
        Pre-formatted human-readable text.
    json_output:
        Serializable dict for ``--json`` mode.
    use_json:
        If ``True``, print *json_output*; otherwise print *text_output*.
    """
    if use_json:
        print(json.dumps(json_output, indent=2, sort_keys=True))
    else:
        print(text_output)


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _build_dimensions(args: argparse.Namespace) -> dict[str, int] | None:
    """
    Collect ``--depth-*`` overrides from parsed args into a dimensions dict.

    Returns ``None`` when no overrides were supplied so the library uses its
    built-in defaults.
    """
    overrides: dict[str, int] = {}
    for dim in Dimension:
        attr = f"depth_{dim.value.replace('-', '_')}"
        value = getattr(args, attr, None)
        if value is not None:
            overrides[dim.value] = value
    return overrides if overrides else None


_DEFAULT_AUTH_MODE: _AuthMode = "client_credentials"
"""No-flag auth mode.  ``context-sync`` primarily targets app-actor workflows."""


def _create_linear_client(auth_mode: _AuthMode | None = None) -> object:
    """
    Construct an authenticated ``linear_client.Linear`` instance.

    Parameters
    ----------
    auth_mode:
        Authentication mode (``oauth``, ``client_credentials``, or
        ``api_key``).  When ``None``, defaults to ``client_credentials``
        because ``context-sync`` primarily targets app-actor workflows.
        Pass an explicit value to override the default.

    Returns
    -------
    object
        An initialized ``Linear`` client instance.

    Raises
    ------
    ContextSyncError
        If ``linear-client`` is not installed or client initialization fails.
    """
    try:
        from linear_client import Linear
    except ImportError as exc:
        raise ContextSyncError(
            "linear-client is not installed.  Install it into the active "
            "environment before running context-sync CLI commands."
        ) from exc

    resolved_mode: _AuthMode = auth_mode if auth_mode is not None else _DEFAULT_AUTH_MODE

    try:
        return Linear(auth_mode=resolved_mode)
    except Exception as exc:
        raise ContextSyncError(f"Failed to initialize Linear client: {exc}") from exc


async def _run_sync(
    args: argparse.Namespace,
    *,
    _gateway_override: Any = None,
) -> int:
    """Execute the ``sync`` subcommand."""
    from context_sync._sync import ContextSync

    if _gateway_override is not None:
        ctx = ContextSync(
            context_dir=Path(args.context_dir),
            _gateway_override=_gateway_override,
        )
    else:
        linear = _create_linear_client(auth_mode=args.auth_mode)
        ctx = ContextSync(
            linear=linear,
            context_dir=Path(args.context_dir),
        )

    # ticket is optional: None means standalone full rebuild.
    ticket: str | None = getattr(args, "ticket", None)

    # Traversal overrides are only meaningful when explicitly supplied.
    # Pass None when args hold only defaults so sync() preserves the
    # manifest's existing configuration.
    cap: int | None = getattr(args, "max_tickets_per_root", None)
    dims = _build_dimensions(args)

    result = await ctx.sync(
        key=ticket,
        max_tickets_per_root=cap,
        dimensions=dims,
    )
    text = _format_sync_result_text(result)
    _emit(text, asdict(result), use_json=args.json)
    return EXIT_SUCCESS


async def _run_refresh(
    args: argparse.Namespace,
    *,
    _gateway_override: Any = None,
) -> int:
    """Execute the ``refresh`` subcommand."""
    from context_sync._sync import ContextSync

    if _gateway_override is not None:
        ctx = ContextSync(
            context_dir=Path(args.context_dir),
            _gateway_override=_gateway_override,
        )
    else:
        linear = _create_linear_client(auth_mode=args.auth_mode)
        ctx = ContextSync(
            linear=linear,
            context_dir=Path(args.context_dir),
        )
    result = await ctx.refresh(missing_root_policy=args.missing_root_policy)
    text = _format_sync_result_text(result)
    _emit(text, asdict(result), use_json=args.json)
    return EXIT_SUCCESS


async def _run_remove(
    args: argparse.Namespace,
    *,
    _gateway_override: Any = None,
) -> int:
    """Execute the ``remove`` subcommand."""
    from context_sync._sync import ContextSync

    if _gateway_override is not None:
        ctx = ContextSync(
            context_dir=Path(args.context_dir),
            _gateway_override=_gateway_override,
        )
    else:
        linear = _create_linear_client(auth_mode=args.auth_mode)
        ctx = ContextSync(
            linear=linear,
            context_dir=Path(args.context_dir),
        )
    result = await ctx.remove(key=args.ticket)
    text = _format_sync_result_text(result)
    _emit(text, asdict(result), use_json=args.json)
    return EXIT_SUCCESS


async def _run_diff(
    args: argparse.Namespace,
    *,
    _gateway_override: Any = None,
) -> int:
    """Execute the ``diff`` subcommand."""
    from context_sync._sync import ContextSync

    if _gateway_override is not None:
        ctx = ContextSync(
            context_dir=Path(args.context_dir),
            _gateway_override=_gateway_override,
        )
    else:
        linear = _create_linear_client(auth_mode=args.auth_mode)
        ctx = ContextSync(
            linear=linear,
            context_dir=Path(args.context_dir),
        )
    result = await ctx.diff()
    text = _format_diff_result_text(result)
    _emit(text, asdict(result), use_json=args.json)
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Argument parser construction
# ---------------------------------------------------------------------------


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add arguments shared by all subcommands."""
    parser.add_argument(
        "--context-dir",
        default=".",
        help="Path to the context directory (default: current directory).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit machine-readable JSON output instead of human-readable text.",
    )


def _add_dimension_args(parser: argparse.ArgumentParser) -> None:
    """Add ``--depth-<dim>`` arguments for traversal depth overrides."""
    for dim in Dimension:
        flag = f"--depth-{dim.value.replace('_', '-')}"
        default = DEFAULT_DIMENSIONS[dim.value]
        parser.add_argument(
            flag,
            type=int,
            default=None,
            metavar="N",
            help=f"Traversal depth for {dim.value} (default: {default}).",
        )


class _VersionedParser(argparse.ArgumentParser):
    """
    ``ArgumentParser`` subclass that includes tool name and version in help and
    error output, per ``docs/policies/common/cli-conventions.md``.
    """

    def format_help(self) -> str:
        """Prepend the version string to the standard help output."""
        return f"{_VERSION_STRING}\n\n{super().format_help()}"

    def error(self, message: str) -> NoReturn:
        """
        Print a short diagnostic with the tool name, version, and a pointer to
        ``--help``, then exit with code 2.
        """
        self.exit(2, f"{_VERSION_STRING}: error: {message}\nSee '{self.prog} --help'.\n")


def build_parser() -> argparse.ArgumentParser:
    """
    Construct the top-level argument parser with all subcommands.

    Returns
    -------
    argparse.ArgumentParser
        Fully configured parser ready for ``parse_args()``.
    """
    parser = _VersionedParser(
        prog=__prog_name__,
        description="Deterministic Linear ticket neighborhood snapshots.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=_VERSION_STRING,
    )
    parser.add_argument(
        "--auth-mode",
        choices=AUTH_MODE_CHOICES,
        default=_DEFAULT_AUTH_MODE,
        help=(f"Linear authentication mode (default: {_DEFAULT_AUTH_MODE})."),
    )
    parser.add_argument(
        "--log-level",
        choices=LOG_LEVEL_CHOICES,
        default=DEFAULT_LOG_LEVEL,
        help=f"Diagnostic log verbosity to stderr (default: {DEFAULT_LOG_LEVEL}).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- sync ---------------------------------------------------------------
    sync_parser = subparsers.add_parser(
        "sync",
        help=(
            "Fully rebuild the snapshot from all tracked roots. "
            "With TICKET, add or reaffirm that root first."
        ),
    )
    sync_parser.add_argument(
        "ticket",
        nargs="?",
        default=None,
        help="Issue key or Linear URL of the root ticket to track (optional).",
    )
    sync_parser.add_argument(
        "--max-tickets-per-root",
        type=int,
        default=None,
        metavar="N",
        help=f"Per-root ticket cap (default: {DEFAULT_MAX_TICKETS_PER_ROOT}).",
    )
    _add_common_args(sync_parser)
    _add_dimension_args(sync_parser)

    # -- refresh ------------------------------------------------------------
    refresh_parser = subparsers.add_parser(
        "refresh",
        help="Re-fetch the latest data for all tracked tickets.",
    )
    refresh_parser.add_argument(
        "--missing-root-policy",
        choices=["quarantine", "remove"],
        default="quarantine",
        help="How to handle roots no longer visible (default: quarantine).",
    )
    _add_common_args(refresh_parser)

    # -- remove -------------------------------------------------------------
    remove_parser = subparsers.add_parser(
        "remove",
        help="Remove a root ticket and refresh the snapshot.",
    )
    remove_parser.add_argument(
        "ticket",
        help="Issue key or Linear URL of the root to remove.",
    )
    _add_common_args(remove_parser)

    # -- diff ---------------------------------------------------------------
    diff_parser = subparsers.add_parser(
        "diff",
        help="Compare local snapshot to live Linear state (read-only).",
    )
    _add_common_args(diff_parser)

    return parser


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

# Handler dispatch table mapping subcommand names to their async handlers.
_HANDLERS: dict[str, _Handler] = {
    "sync": _run_sync,
    "refresh": _run_refresh,
    "remove": _run_remove,
    "diff": _run_diff,
}


def main(argv: list[str] | None = None) -> NoReturn:
    """
    CLI entry point for ``context-sync``.

    Parses arguments, configures logging, dispatches to the appropriate async
    handler, and exits with the correct code.  Operational errors from the
    library layer are caught and reported; unexpected exceptions propagate.

    Parameters
    ----------
    argv:
        Argument list to parse.  ``None`` uses ``sys.argv[1:]``.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    # Configure logging before any library code runs (R8).
    # All levels — including OFF — apply to the root logger so that
    # context-sync and linear-client are controlled uniformly.
    if args.log_level == "OFF":
        # Python logging has no built-in "silence everything" constant.
        # CRITICAL is 50; setting 51 rejects all messages including CRITICAL.
        effective_level = logging.CRITICAL + 1
    else:
        effective_level = getattr(logging, args.log_level)
    logging.basicConfig(
        level=effective_level,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )

    handler = _HANDLERS.get(args.command)
    if handler is None:
        parser.error(f"Unknown command: {args.command}")

    try:
        exit_code = asyncio.run(handler(args))
    except (ContextSyncError, ValueError) as exc:
        # Operational errors and input validation errors: report clearly.
        if getattr(args, "json", False):
            error_payload = {"error": type(exc).__name__, "message": str(exc)}
            print(json.dumps(error_payload, indent=2, sort_keys=True))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        sys.exit(EXIT_ERROR)
    except KeyboardInterrupt:
        # Clean exit on Ctrl+C.
        sys.exit(130)

    sys.exit(exit_code)
