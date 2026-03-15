#!/usr/bin/env python3
"""
Sync agent instruction markdown files.

By default, this script treats docs/policies/common/agent-instructions.md as
the source of truth and mirrors it to CLAUDE.md and AGENTS.md. It can also run
in check mode for CI/pre-commit validation.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

AUTOGEN_COMMENT = "<!-- auto-generated, do not edit -->"
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SOURCE = Path("docs/policies/common/agent-instructions.md")
DEFAULT_TARGETS = (Path("CLAUDE.md"), Path("AGENTS.md"))


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sync agent instruction files. Defaults to reading "
            "docs/policies/common/agent-instructions.md and writing CLAUDE.md + AGENTS.md."
        )
    )
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="Source markdown file path (default: docs/policies/common/agent-instructions.md).",
    )
    parser.add_argument(
        "--targets",
        nargs="+",
        default=[str(path) for path in DEFAULT_TARGETS],
        help="Target markdown files to sync (default: CLAUDE.md AGENTS.md).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check that targets already match source without writing files.",
    )
    return parser.parse_args(argv)


def _resolve_repo_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()


def _read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return path.read_text(encoding="utf-8")


def _normalize_newline(text: str) -> str:
    return text if text.endswith("\n") else f"{text}\n"


def _strip_generated_prefix(text: str) -> str:
    lines = _normalize_newline(text).splitlines()

    if lines and lines[0].startswith("# "):
        lines = lines[1:]

    while lines and not lines[0].strip():
        lines = lines[1:]

    if lines and lines[0].strip().lower() == AUTOGEN_COMMENT:
        lines = lines[1:]

    while lines and not lines[0].strip():
        lines = lines[1:]

    return "\n".join(lines).rstrip("\n")


def _render_target_text(source_text: str, target: Path) -> str:
    body = _strip_generated_prefix(source_text)
    header = f"# {target.name}\n\n{AUTOGEN_COMMENT}\n"
    if body:
        return f"{header}\n{body}\n"
    return f"{header}\n"


def _sync(source: Path, targets: Sequence[Path], check_only: bool) -> int:
    source_text = _read_text(source)
    mismatches: list[Path] = []
    updated: list[Path] = []

    for target in targets:
        expected_text = _render_target_text(source_text=source_text, target=target)
        target_text = (
            _normalize_newline(target.read_text(encoding="utf-8")) if target.exists() else ""
        )

        if target_text == expected_text:
            print(f"unchanged: {target}")
            continue

        mismatches.append(target)
        if check_only:
            print(f"out-of-sync: {target}")
            continue

        target.write_text(expected_text, encoding="utf-8")
        updated.append(target)
        print(f"updated: {target}")

    if check_only and mismatches:
        print(
            f"\n{len(mismatches)} target file(s) differ from {source}. "
            "Run without --check to sync.",
            file=sys.stderr,
        )
        return 1

    if not check_only:
        print(f"\nSync complete. {len(updated)} file(s) updated from {source}.")

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    source = _resolve_repo_path(args.source)
    targets = [_resolve_repo_path(target) for target in args.targets]

    unique_targets: list[Path] = []
    seen: set[Path] = set()
    for target in targets:
        if target == source:
            continue
        if target not in seen:
            unique_targets.append(target)
            seen.add(target)

    if not unique_targets:
        print("No target files to sync.")
        return 0

    try:
        return _sync(source=source, targets=unique_targets, check_only=args.check)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
