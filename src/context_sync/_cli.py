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
from dataclasses import asdict
from pathlib import Path
from typing import NoReturn

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

LOG_LEVEL_CHOICES: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "OFF")
"""Valid ``--log-level`` values."""

DEFAULT_LOG_LEVEL: str = "WARNING"
"""Log level applied when ``--log-level`` is not supplied."""

_VERSION_STRING: str = f"{__prog_name__} {__version__}"
"""Pre-formatted version string shared by ``-v``, ``-h``, and error output."""

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
            lines.append(f"Error [{err.error_type}] {err.ticket_id}: {err.message}")

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
        lines.append(f"Current ({len(current)}): {', '.join(e.ticket_id for e in current)}")
    if stale:
        for entry in stale:
            fields = ", ".join(entry.changed_fields) if entry.changed_fields else "unknown"
            lines.append(f"Stale: {entry.ticket_id} [{fields}]")
    if missing_local:
        keys = ", ".join(e.ticket_id for e in missing_local)
        lines.append(f"Missing locally ({len(missing_local)}): {keys}")
    if missing_remote:
        keys = ", ".join(e.ticket_id for e in missing_remote)
        lines.append(f"Missing remotely ({len(missing_remote)}): {keys}")
    if result.errors:
        for err in result.errors:
            lines.append(f"Error [{err.error_type}] {err.ticket_id}: {err.message}")

    if not lines:
        lines.append("No tracked tickets.")

    return "\n".join(lines)


def _emit(text_output: str, json_output: dict[str, object] | None, *, use_json: bool) -> None:
    """
    Write the formatted result to stdout.

    Parameters
    ----------
    text_output:
        Pre-formatted human-readable text.
    json_output:
        Serializable dict for ``--json`` mode.  ``None`` skips JSON emission.
    use_json:
        If ``True``, print *json_output*; otherwise print *text_output*.
    """
    if use_json and json_output is not None:
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


def _create_linear_client() -> object:
    """
    Construct an authenticated ``linear_client.Linear`` instance from the
    environment.

    Raises
    ------
    SystemExit
        If ``linear-client`` is not installed or authentication fails.
    """
    try:
        from linear_client import Linear  # type: ignore[import-untyped]
    except ImportError:
        logger.error(
            "linear-client is not installed.  Install it into the active "
            "environment before running context-sync CLI commands."
        )
        sys.exit(EXIT_ERROR)

    try:
        return Linear()
    except Exception as exc:
        logger.error("Failed to initialize Linear client: %s", exc)
        sys.exit(EXIT_ERROR)


async def _run_sync(args: argparse.Namespace) -> int:
    """Execute the ``sync`` subcommand."""
    from context_sync._sync import ContextSync

    linear = _create_linear_client()
    syncer = ContextSync(
        linear=linear,
        context_dir=Path(args.context_dir),
        dimensions=_build_dimensions(args),
        max_tickets_per_root=args.max_tickets_per_root,
    )
    result = syncer.sync(
        root_ticket_id=args.root_ticket,
        max_tickets_per_root=args.max_tickets_per_root,
        dimensions=_build_dimensions(args),
    )
    result = await result
    text = _format_sync_result_text(result)
    _emit(text, asdict(result), use_json=args.json)
    return EXIT_SUCCESS


async def _run_refresh(args: argparse.Namespace) -> int:
    """Execute the ``refresh`` subcommand."""
    from context_sync._sync import ContextSync

    linear = _create_linear_client()
    syncer = ContextSync(
        linear=linear,
        context_dir=Path(args.context_dir),
    )
    result = await syncer.refresh(missing_root_policy=args.missing_root_policy)
    text = _format_sync_result_text(result)
    _emit(text, asdict(result), use_json=args.json)
    return EXIT_SUCCESS


async def _run_add(args: argparse.Namespace) -> int:
    """Execute the ``add`` subcommand."""
    from context_sync._sync import ContextSync

    linear = _create_linear_client()
    syncer = ContextSync(
        linear=linear,
        context_dir=Path(args.context_dir),
    )
    result = await syncer.add(ticket_ref=args.ticket_ref)
    text = _format_sync_result_text(result)
    _emit(text, asdict(result), use_json=args.json)
    return EXIT_SUCCESS


async def _run_remove_root(args: argparse.Namespace) -> int:
    """Execute the ``remove-root`` subcommand."""
    from context_sync._sync import ContextSync

    linear = _create_linear_client()
    syncer = ContextSync(
        linear=linear,
        context_dir=Path(args.context_dir),
    )
    result = await syncer.remove_root(ticket_ref=args.ticket_ref)
    text = _format_sync_result_text(result)
    _emit(text, asdict(result), use_json=args.json)
    return EXIT_SUCCESS


async def _run_diff(args: argparse.Namespace) -> int:
    """Execute the ``diff`` subcommand."""
    from context_sync._sync import ContextSync

    linear = _create_linear_client()
    syncer = ContextSync(
        linear=linear,
        context_dir=Path(args.context_dir),
    )
    result = await syncer.diff()
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
        "--log-level",
        choices=LOG_LEVEL_CHOICES,
        default=DEFAULT_LOG_LEVEL,
        help=f"Diagnostic log verbosity to stderr (default: {DEFAULT_LOG_LEVEL}).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- sync ---------------------------------------------------------------
    sync_parser = subparsers.add_parser(
        "sync",
        help="Full-snapshot sync from a root ticket.",
    )
    sync_parser.add_argument(
        "root_ticket",
        help="Issue key or Linear URL of the root ticket.",
    )
    sync_parser.add_argument(
        "--max-tickets-per-root",
        type=int,
        default=DEFAULT_MAX_TICKETS_PER_ROOT,
        metavar="N",
        help=f"Per-root ticket cap (default: {DEFAULT_MAX_TICKETS_PER_ROOT}).",
    )
    _add_common_args(sync_parser)
    _add_dimension_args(sync_parser)

    # -- refresh ------------------------------------------------------------
    refresh_parser = subparsers.add_parser(
        "refresh",
        help="Incremental refresh of all tracked roots.",
    )
    refresh_parser.add_argument(
        "--missing-root-policy",
        choices=["quarantine", "remove"],
        default="quarantine",
        help="How to handle roots no longer visible (default: quarantine).",
    )
    _add_common_args(refresh_parser)

    # -- add ----------------------------------------------------------------
    add_parser = subparsers.add_parser(
        "add",
        help="Add a new root ticket and refresh the snapshot.",
    )
    add_parser.add_argument(
        "ticket_ref",
        help="Issue key or Linear URL of the ticket to add as root.",
    )
    _add_common_args(add_parser)

    # -- remove-root --------------------------------------------------------
    remove_root_parser = subparsers.add_parser(
        "remove-root",
        help="Remove a root ticket and refresh the snapshot.",
    )
    remove_root_parser.add_argument(
        "ticket_ref",
        help="Issue key or Linear URL of the root to remove.",
    )
    _add_common_args(remove_root_parser)

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
_HANDLERS: dict[str, object] = {
    "sync": _run_sync,
    "refresh": _run_refresh,
    "add": _run_add,
    "remove-root": _run_remove_root,
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

    # Configure logging before any library code runs.
    if args.log_level == "OFF":
        logging.disable(logging.CRITICAL)
    else:
        logging.basicConfig(
            level=getattr(logging, args.log_level),
            format="%(levelname)s %(name)s: %(message)s",
            stream=sys.stderr,
        )

    handler = _HANDLERS.get(args.command)
    if handler is None:
        parser.error(f"Unknown command: {args.command}")

    try:
        exit_code = asyncio.run(handler(args))  # type: ignore[operator]
    except ContextSyncError as exc:
        # Operational errors: report clearly and exit 1.
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
