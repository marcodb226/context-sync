"""Tests for atomic file writes and post-write verification."""

from __future__ import annotations

from pathlib import Path

import pytest

from context_sync._errors import WriteError
from context_sync._io import (
    CRITICAL_FRONTMATTER_FIELDS,
    atomic_write,
    write_and_verify_ticket,
)

VALID_CONTENT = """\
---
format_version: 1
root: true
ticket_key: TEST-1
ticket_uuid: uuid-1
title: Test
---
<!-- context-sync:section id=description-uuid-1 start -->
## Description
test
<!-- context-sync:section id=description-uuid-1 end -->
<!-- context-sync:section id=comments-uuid-1 start -->
## Comments
<!-- context-sync:section id=comments-uuid-1 end -->
"""

VALID_FRONTMATTER: dict[str, object] = {
    "format_version": 1,
    "root": True,
    "ticket_key": "TEST-1",
    "ticket_uuid": "uuid-1",
}

VALID_MARKERS: list[str] = [
    "<!-- context-sync:section id=description-uuid-1 start -->",
    "<!-- context-sync:section id=description-uuid-1 end -->",
    "<!-- context-sync:section id=comments-uuid-1 start -->",
    "<!-- context-sync:section id=comments-uuid-1 end -->",
]


class TestAtomicWrite:
    """atomic_write persists content atomically via temp-file rename."""

    def test_writes_content_to_new_file(self, tmp_path: Path) -> None:
        target = tmp_path / "out.md"
        atomic_write(target, VALID_CONTENT)
        assert target.read_text(encoding="utf-8") == VALID_CONTENT

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "c" / "out.md"
        atomic_write(target, "hello")
        assert target.read_text(encoding="utf-8") == "hello"

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "out.md"
        target.write_text("old content", encoding="utf-8")
        atomic_write(target, "new content")
        assert target.read_text(encoding="utf-8") == "new content"

    def test_content_is_readable_after_write(self, tmp_path: Path) -> None:
        target = tmp_path / "roundtrip.md"
        atomic_write(target, VALID_CONTENT)
        result = target.read_text(encoding="utf-8")
        assert "ticket_key: TEST-1" in result
        assert "## Description" in result


class TestWriteAndVerifyTicket:
    """write_and_verify_ticket combines atomic write with post-write checks."""

    def test_passes_when_frontmatter_and_markers_match(self, tmp_path: Path) -> None:
        target = tmp_path / "ticket.md"
        write_and_verify_ticket(target, VALID_CONTENT, VALID_FRONTMATTER, VALID_MARKERS)
        assert target.read_text(encoding="utf-8") == VALID_CONTENT

    def test_raises_on_frontmatter_field_mismatch(self, tmp_path: Path) -> None:
        target = tmp_path / "ticket.md"
        bad_fm = {**VALID_FRONTMATTER, "ticket_key": "WRONG-99"}
        with pytest.raises(WriteError, match="ticket_key"):
            write_and_verify_ticket(target, VALID_CONTENT, bad_fm, VALID_MARKERS)

    def test_raises_on_missing_marker(self, tmp_path: Path) -> None:
        target = tmp_path / "ticket.md"
        extra_marker = "<!-- context-sync:section id=nonexistent start -->"
        with pytest.raises(WriteError, match="missing marker"):
            write_and_verify_ticket(
                target,
                VALID_CONTENT,
                VALID_FRONTMATTER,
                [*VALID_MARKERS, extra_marker],
            )

    def test_multiple_missing_markers_reported_together(self, tmp_path: Path) -> None:
        target = tmp_path / "ticket.md"
        missing_a = "<!-- context-sync:section id=absent-a start -->"
        missing_b = "<!-- context-sync:section id=absent-b start -->"
        with pytest.raises(WriteError, match="absent-a") as exc_info:
            write_and_verify_ticket(
                target,
                VALID_CONTENT,
                VALID_FRONTMATTER,
                [*VALID_MARKERS, missing_a, missing_b],
            )
        # Both missing markers appear in the single error message.
        message = str(exc_info.value)
        assert "absent-a" in message
        assert "absent-b" in message


class TestCriticalFrontmatterFields:
    """CRITICAL_FRONTMATTER_FIELDS contains the expected field names."""

    def test_contains_expected_fields(self) -> None:
        expected = {"format_version", "ticket_uuid", "ticket_key", "root"}
        assert set(CRITICAL_FRONTMATTER_FIELDS) == expected

    def test_is_tuple(self) -> None:
        assert isinstance(CRITICAL_FRONTMATTER_FIELDS, tuple)
