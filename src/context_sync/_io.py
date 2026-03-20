"""
Atomic file writes and post-write verification.

Every file that context-sync persists is written atomically: content goes to
a temporary file in the same directory, then ``os.rename()`` replaces the
target.  Ticket files additionally undergo a lightweight verification step
that re-parses the generated output and checks critical frontmatter fields
plus required ``context-sync:`` structural markers.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from context_sync._errors import ManifestError, WriteError
from context_sync._yaml import parse_frontmatter

logger = logging.getLogger(__name__)

# Frontmatter fields that must survive the write → re-parse round trip.
CRITICAL_FRONTMATTER_FIELDS: tuple[str, ...] = (
    "format_version",
    "ticket_uuid",
    "ticket_key",
    "root",
)


def atomic_write(path: Path, content: str) -> None:
    """
    Atomically write *content* to *path*.

    Creates a temporary file in the same directory as *path*, writes the
    content, flushes to disk, and renames over the target.  If any step
    fails, the temporary file is removed and a :class:`WriteError` is
    raised.

    Parameters
    ----------
    path:
        Destination file path.
    content:
        Text content to write.

    Raises
    ------
    WriteError
        If the write or rename fails.
    """
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)

    fd: int | None = None
    tmp_path: str | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=parent, prefix=".ctx-sync-", suffix=".tmp")
        os.write(fd, content.encode("utf-8"))
        os.fsync(fd)
        os.close(fd)
        fd = None
        os.rename(tmp_path, path)
        tmp_path = None
    except OSError as exc:
        raise WriteError(f"Atomic write failed for {path}: {exc}") from exc
    finally:
        if fd is not None:
            os.close(fd)
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def write_and_verify_ticket(
    path: Path,
    content: str,
    expected_frontmatter: dict[str, Any],
    expected_markers: list[str],
) -> None:
    """
    Atomically write a ticket file and verify the result.

    After writing, re-reads the file, parses frontmatter, and checks:

    1. Critical frontmatter fields match *expected_frontmatter*.
    2. All *expected_markers* (``context-sync:`` HTML comments) are present
       in the body.

    This is the lightweight verification contract from the top-level design
    §7 (R1 mitigation).

    Parameters
    ----------
    path:
        Destination file path.
    content:
        Full Markdown file content (frontmatter + body).
    expected_frontmatter:
        Mapping of critical field names to expected values.
    expected_markers:
        HTML comment marker strings that must appear in the body.

    Raises
    ------
    WriteError
        If the write fails or verification detects a mismatch.
    """
    atomic_write(path, content)

    try:
        written = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WriteError(f"Cannot re-read {path} for verification: {exc}") from exc

    try:
        parsed_fm = parse_frontmatter(written)
    except ManifestError as exc:
        raise WriteError(f"Post-write frontmatter parse failed for {path}: {exc}") from exc
    fm_mismatches = _verify_frontmatter(parsed_fm, expected_frontmatter)
    marker_mismatches = _verify_markers(written, expected_markers)

    errors = fm_mismatches + marker_mismatches
    if errors:
        detail = "; ".join(errors)
        raise WriteError(f"Post-write verification failed for {path}: {detail}")


def _verify_frontmatter(
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> list[str]:
    """
    Compare critical frontmatter fields.

    Returns a list of mismatch descriptions (empty if all match).
    """
    mismatches: list[str] = []
    for field in CRITICAL_FRONTMATTER_FIELDS:
        if field not in expected:
            continue
        actual_val = actual.get(field)
        expected_val = expected[field]
        if actual_val != expected_val:
            mismatches.append(
                f"frontmatter field '{field}': expected {expected_val!r}, got {actual_val!r}"
            )
    return mismatches


def _verify_markers(content: str, expected_markers: list[str]) -> list[str]:
    """
    Check that all expected HTML comment markers are present.

    Returns a list of missing marker descriptions (empty if all present).
    """
    return [f"missing marker: {marker}" for marker in expected_markers if marker not in content]
