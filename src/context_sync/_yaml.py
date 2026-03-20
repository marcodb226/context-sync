"""
Deterministic YAML serialization and frontmatter parsing.

This module provides the normalization primitives that both the manifest
(``.context-sync.yml``) and ticket-file frontmatter share:

* Lexicographically ordered mapping keys at every nesting level.
* Empty collections and ``None`` values omitted from output.
* UTC RFC 3339 timestamps passed through as opaque strings.
* Frontmatter delimited by ``---`` lines for Markdown files.
"""

from __future__ import annotations

from typing import Any

import yaml

from context_sync._errors import ManifestError

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def strip_empty(data: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively remove keys whose values are ``None``, empty list, or empty dict.

    Nested dicts are stripped recursively before the emptiness check, so a dict
    that becomes empty after stripping is itself removed.
    """
    result: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            cleaned = strip_empty(value)
            if cleaned:
                result[key] = cleaned
        elif isinstance(value, list):
            cleaned_list = _strip_empty_list(value)
            if cleaned_list:
                result[key] = cleaned_list
        elif value is not None:
            result[key] = value
    return result


def _strip_empty_list(items: list[Any]) -> list[Any]:
    """
    Recursively clean list elements.

    Dict elements are stripped; ``None`` elements are kept (lists preserve
    element identity).  Empty dicts produced by stripping are removed.
    """
    result: list[Any] = []
    for item in items:
        if isinstance(item, dict):
            cleaned = strip_empty(item)
            if cleaned:
                result.append(cleaned)
        else:
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# YAML serialization
# ---------------------------------------------------------------------------


def dump_yaml(data: dict[str, Any]) -> str:
    """
    Serialize a mapping to a YAML string with deterministic formatting.

    Keys are lexicographically sorted at every nesting level.  The output
    uses block style (no flow mappings or sequences).  Empty collections
    and ``None`` values are stripped before serialization.

    Returns
    -------
    str
        YAML text without document markers (no leading ``---``).
    """
    cleaned = strip_empty(data)
    if not cleaned:
        return ""
    return yaml.safe_dump(
        cleaned,
        sort_keys=True,
        default_flow_style=False,
        allow_unicode=True,
    )


# ---------------------------------------------------------------------------
# Frontmatter serialization / parsing
# ---------------------------------------------------------------------------


def serialize_frontmatter(data: dict[str, Any]) -> str:
    """
    Serialize a mapping to a YAML frontmatter block.

    Returns a string starting with ``---`` followed by the YAML body and
    ending with ``---``.  Keys are lexicographically sorted, empty
    collections and ``None`` values are omitted.
    """
    body = dump_yaml(data)
    return f"---\n{body}---\n"


def parse_frontmatter(text: str) -> dict[str, Any]:
    """
    Extract and parse YAML frontmatter from a Markdown file's text.

    The frontmatter must be delimited by ``---`` on the first line and a
    subsequent ``---`` line.

    Parameters
    ----------
    text:
        Full file content.

    Returns
    -------
    dict[str, Any]
        Parsed frontmatter mapping.

    Raises
    ------
    ManifestError
        If frontmatter delimiters are missing or the YAML is malformed.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ManifestError("Missing opening frontmatter delimiter '---'")

    end_index: int | None = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = i
            break

    if end_index is None:
        raise ManifestError("Missing closing frontmatter delimiter '---'")

    yaml_text = "\n".join(lines[1:end_index])
    try:
        parsed = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise ManifestError(f"Malformed frontmatter YAML: {exc}") from exc

    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ManifestError(f"Frontmatter must be a YAML mapping, got {type(parsed).__name__}")
    return parsed


def extract_body(text: str) -> str:
    """
    Extract the Markdown body after the frontmatter block.

    Returns
    -------
    str
        Everything after the closing ``---`` delimiter, with leading
        blank lines preserved.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return text

    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[i + 1 :])
    return text
