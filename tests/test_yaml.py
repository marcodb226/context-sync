"""Tests for context_sync._yaml deterministic YAML serialization and frontmatter parsing."""

from __future__ import annotations

from typing import Any

import pytest

from context_sync._errors import ManifestError
from context_sync._yaml import (
    dump_yaml,
    extract_body,
    parse_frontmatter,
    serialize_frontmatter,
    strip_empty,
)


class TestStripEmpty:
    def test_removes_none_values(self) -> None:
        data: dict[str, Any] = {"a": 1, "b": None, "c": "hello"}
        assert strip_empty(data) == {"a": 1, "c": "hello"}

    def test_removes_empty_list(self) -> None:
        data: dict[str, Any] = {"a": 1, "b": []}
        assert strip_empty(data) == {"a": 1}

    def test_removes_empty_dict(self) -> None:
        data: dict[str, Any] = {"a": 1, "b": {}}
        assert strip_empty(data) == {"a": 1}

    def test_nested_dict_stripped_then_removed_if_empty(self) -> None:
        data: dict[str, Any] = {"a": {"b": None, "c": None}}
        assert strip_empty(data) == {}

    def test_nested_dict_partially_stripped(self) -> None:
        data: dict[str, Any] = {"outer": {"keep": 42, "drop": None}}
        assert strip_empty(data) == {"outer": {"keep": 42}}

    def test_list_with_dict_elements_stripped(self) -> None:
        data: dict[str, Any] = {
            "items": [
                {"a": 1, "b": None},
                {"x": None},
                {"y": 2},
            ]
        }
        result = strip_empty(data)
        assert result == {"items": [{"a": 1}, {"y": 2}]}

    def test_list_preserves_none_elements(self) -> None:
        data: dict[str, Any] = {"items": [None, 1, "two"]}
        result = strip_empty(data)
        assert result == {"items": [None, 1, "two"]}

    def test_list_with_all_empty_dicts_removed(self) -> None:
        data: dict[str, Any] = {"items": [{"a": None}, {"b": None}]}
        assert strip_empty(data) == {}

    def test_deeply_nested(self) -> None:
        data: dict[str, Any] = {"l1": {"l2": {"l3": {"keep": "yes", "drop": None}}}}
        assert strip_empty(data) == {"l1": {"l2": {"l3": {"keep": "yes"}}}}

    def test_empty_input(self) -> None:
        assert strip_empty({}) == {}

    def test_preserves_false_and_zero(self) -> None:
        data: dict[str, Any] = {"flag": False, "count": 0, "empty_str": ""}
        result = strip_empty(data)
        assert result == {"flag": False, "count": 0, "empty_str": ""}


class TestDumpYaml:
    def test_keys_are_lexicographically_sorted(self) -> None:
        data: dict[str, Any] = {"zebra": 1, "apple": 2, "mango": 3}
        output = dump_yaml(data)
        lines = output.strip().splitlines()
        keys = [line.split(":")[0] for line in lines]
        assert keys == ["apple", "mango", "zebra"]

    def test_empty_data_returns_empty_string(self) -> None:
        assert dump_yaml({}) == ""

    def test_all_none_values_returns_empty_string(self) -> None:
        data: dict[str, Any] = {"a": None, "b": None}
        assert dump_yaml(data) == ""

    def test_nested_dicts_use_block_style(self) -> None:
        data: dict[str, Any] = {"outer": {"inner": "value"}}
        output = dump_yaml(data)
        assert "{" not in output
        assert "}" not in output

    def test_nested_lists_use_block_style(self) -> None:
        data: dict[str, Any] = {"items": [1, 2, 3]}
        output = dump_yaml(data)
        assert "[" not in output
        assert "]" not in output

    def test_nested_dict_keys_sorted(self) -> None:
        data: dict[str, Any] = {"outer": {"z_key": 1, "a_key": 2}}
        output = dump_yaml(data)
        assert output.index("a_key") < output.index("z_key")

    def test_output_is_valid_yaml(self) -> None:
        import yaml

        data: dict[str, Any] = {"title": "Hello", "count": 5, "tags": ["a", "b"]}
        output = dump_yaml(data)
        parsed = yaml.safe_load(output)
        assert parsed == data

    def test_empty_values_stripped_before_serialization(self) -> None:
        data: dict[str, Any] = {"keep": "yes", "drop_none": None, "drop_list": []}
        output = dump_yaml(data)
        assert "drop_none" not in output
        assert "drop_list" not in output
        assert "keep" in output


class TestSerializeFrontmatter:
    def test_wraps_with_delimiters(self) -> None:
        data: dict[str, Any] = {"title": "Test"}
        result = serialize_frontmatter(data)
        assert result.startswith("---\n")
        assert result.endswith("---\n")

    def test_empty_data_still_has_delimiters(self) -> None:
        result = serialize_frontmatter({})
        assert result == "---\n---\n"

    def test_round_trips_with_parse(self) -> None:
        data: dict[str, Any] = {"alpha": 1, "beta": "two", "gamma": [3, 4]}
        serialized = serialize_frontmatter(data)
        parsed = parse_frontmatter(serialized)
        assert parsed == data

    def test_round_trip_preserves_nested_structure(self) -> None:
        data: dict[str, Any] = {
            "metadata": {"author": "test", "version": 1},
            "tags": ["a", "b"],
        }
        serialized = serialize_frontmatter(data)
        parsed = parse_frontmatter(serialized)
        assert parsed == data


class TestParseFrontmatter:
    def test_valid_parse(self) -> None:
        text = "---\ntitle: Hello\ncount: 5\n---\nBody here.\n"
        result = parse_frontmatter(text)
        assert result == {"title": "Hello", "count": 5}

    def test_missing_opening_delimiter(self) -> None:
        text = "title: Hello\n---\nBody here.\n"
        with pytest.raises(ManifestError, match="Missing opening frontmatter"):
            parse_frontmatter(text)

    def test_missing_closing_delimiter(self) -> None:
        text = "---\ntitle: Hello\nBody here.\n"
        with pytest.raises(ManifestError, match="Missing closing frontmatter"):
            parse_frontmatter(text)

    def test_malformed_yaml(self) -> None:
        text = "---\n: :\n  bad: [unclosed\n---\n"
        with pytest.raises(ManifestError, match="Malformed frontmatter YAML"):
            parse_frontmatter(text)

    def test_non_dict_yaml_raises(self) -> None:
        text = "---\n- item1\n- item2\n---\n"
        with pytest.raises(ManifestError, match="must be a YAML mapping"):
            parse_frontmatter(text)

    def test_empty_frontmatter_returns_empty_dict(self) -> None:
        text = "---\n---\nBody.\n"
        result = parse_frontmatter(text)
        assert result == {}

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ManifestError, match="Missing opening frontmatter"):
            parse_frontmatter("")

    def test_whitespace_around_delimiters(self) -> None:
        text = "---  \ntitle: Hello\n  ---  \nBody.\n"
        result = parse_frontmatter(text)
        assert result == {"title": "Hello"}


class TestExtractBody:
    def test_body_after_frontmatter(self) -> None:
        text = "---\ntitle: Hello\n---\nBody content here.\n"
        assert extract_body(text) == "Body content here.\n"

    def test_body_preserves_leading_blank_lines(self) -> None:
        text = "---\ntitle: Hello\n---\n\n\nBody after blanks.\n"
        assert extract_body(text) == "\n\nBody after blanks.\n"

    def test_no_frontmatter_returns_full_text(self) -> None:
        text = "Just plain text.\nNo frontmatter here.\n"
        assert extract_body(text) == text

    def test_empty_string_returns_empty(self) -> None:
        assert extract_body("") == ""

    def test_missing_closing_delimiter_returns_full_text(self) -> None:
        text = "---\ntitle: Hello\nNo closing.\n"
        assert extract_body(text) == text

    def test_empty_body_after_frontmatter(self) -> None:
        text = "---\ntitle: Hello\n---\n"
        assert extract_body(text) == ""


class TestDeterminism:
    def test_same_data_produces_identical_output(self) -> None:
        data: dict[str, Any] = {
            "z_last": [3, 2, 1],
            "a_first": "hello",
            "m_middle": {"nested_z": True, "nested_a": False},
        }
        first = dump_yaml(data)
        second = dump_yaml(data)
        assert first == second

    def test_insertion_order_does_not_affect_output(self) -> None:
        data_a: dict[str, Any] = {"x": 1, "a": 2, "m": 3}
        data_b: dict[str, Any] = {"a": 2, "m": 3, "x": 1}
        assert dump_yaml(data_a) == dump_yaml(data_b)

    def test_frontmatter_determinism(self) -> None:
        data: dict[str, Any] = {"beta": "b", "alpha": "a"}
        first = serialize_frontmatter(data)
        second = serialize_frontmatter(data)
        assert first == second
