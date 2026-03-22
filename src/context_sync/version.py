"""
Canonical package identity for context-sync.

All identity-reporting surfaces (pyproject.toml, CLI, docs) derive from this
single source so that name and version literals are never duplicated.
"""

__prog_name__ = "context-sync"
"""Canonical tool / distribution name used in CLI output, help text, and errors."""

__version__ = "0.1.0.dev0"
