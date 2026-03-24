"""
Manifest schema and I/O for ``.context-sync.yml``.

The manifest is the authoritative directory-level metadata file.  It stores
workspace identity, the root-ticket set, ticket lookup mappings, key aliases,
traversal configuration, and snapshot-pass metadata.  Pydantic models are
used because the manifest crosses the serialization boundary (written to
disk, read back and validated).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from context_sync._config import FORMAT_VERSION
from context_sync._errors import ManifestError
from context_sync._gateway import WorkspaceIdentity
from context_sync._io import atomic_write
from context_sync._yaml import dump_yaml

MANIFEST_FILENAME: str = ".context-sync.yml"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ManifestRootEntry(BaseModel):
    """
    Per-root metadata in the manifest.

    Attributes
    ----------
    state:
        ``"active"`` or ``"quarantined"``.
    quarantined_reason:
        Machine-readable reason when ``state == "quarantined"``
        (e.g. ``"not_available_in_visible_view"``).
    """

    model_config = ConfigDict(extra="forbid")

    state: Literal["active", "quarantined"]
    quarantined_reason: str | None = None


class ManifestTicketEntry(BaseModel):
    """
    Per-ticket lookup metadata in the manifest.

    Attributes
    ----------
    current_key:
        Current human-facing issue key (e.g. ``"ACP-123"``).
    current_path:
        Relative path to the ticket file within the context directory.
    """

    model_config = ConfigDict(extra="forbid")

    current_key: str
    current_path: str


class ManifestSnapshot(BaseModel):
    """
    Snapshot-pass metadata.

    Attributes
    ----------
    mode:
        The operation that produced this snapshot
        (``"sync"``, ``"refresh"``, ``"remove"``, or ``"add"`` for the
        internal ``_add`` path).
    started_at:
        UTC RFC 3339 timestamp when the pass began.
    completed_at:
        UTC RFC 3339 timestamp when the pass finished, or ``None`` if
        the pass did not complete.
    completed_successfully:
        Whether the pass completed without aborting.
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["sync", "refresh", "add", "remove"]
    started_at: str
    completed_at: str | None = None
    completed_successfully: bool | None = None


class Manifest(BaseModel):
    """
    The ``.context-sync.yml`` schema.

    This is the authoritative source for workspace binding, root-set
    membership, ticket identity lookups, key aliases, traversal
    configuration, and snapshot-pass metadata.
    """

    model_config = ConfigDict(extra="forbid")

    format_version: int
    workspace_id: str
    workspace_slug: str
    dimensions: dict[str, int]
    max_tickets_per_root: int
    roots: dict[str, ManifestRootEntry] = {}
    tickets: dict[str, ManifestTicketEntry] = {}
    aliases: dict[str, str] = {}
    snapshot: ManifestSnapshot | None = None


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def initialize_manifest(
    workspace: WorkspaceIdentity,
    dimensions: dict[str, int],
    max_tickets_per_root: int,
) -> Manifest:
    """
    Create a new manifest for an empty context directory.

    Parameters
    ----------
    workspace:
        Workspace identity to bind the directory to.
    dimensions:
        Active traversal-depth configuration.
    max_tickets_per_root:
        Per-root ticket cap.

    Returns
    -------
    Manifest
    """
    return Manifest(
        format_version=FORMAT_VERSION,
        workspace_id=workspace.workspace_id,
        workspace_slug=workspace.workspace_slug,
        dimensions=dimensions,
        max_tickets_per_root=max_tickets_per_root,
    )


def load_manifest(context_dir: Path) -> Manifest:
    """
    Load and validate the manifest from *context_dir*.

    Raises
    ------
    ManifestError
        If the file is missing, corrupt, has an unrecognized
        ``format_version``, or fails Pydantic validation.
    """
    path = context_dir / MANIFEST_FILENAME
    if not path.is_file():
        raise ManifestError(f"Manifest not found: {path}")

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"Cannot read manifest: {exc}") from exc

    try:
        raw: Any = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ManifestError(f"Malformed manifest YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ManifestError(f"Manifest must be a YAML mapping, got {type(raw).__name__}")

    fv = raw.get("format_version")
    if fv != FORMAT_VERSION:
        raise ManifestError(
            f"Unsupported manifest format_version: {fv!r} (expected {FORMAT_VERSION})"
        )

    try:
        return Manifest.model_validate(raw)
    except ValidationError as exc:
        raise ManifestError(f"Invalid manifest: {exc}") from exc


def save_manifest(manifest: Manifest, context_dir: Path) -> None:
    """
    Atomically write the manifest to *context_dir*.

    YAML keys are lexicographically ordered and empty collections are
    omitted, matching the project's normalization contract.
    """
    path = context_dir / MANIFEST_FILENAME
    data = manifest.model_dump(mode="json")
    content = dump_yaml(data)
    atomic_write(path, content)
