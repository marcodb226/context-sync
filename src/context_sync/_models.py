"""
Public result and error models returned by ContextSync operations.

These types are the caller-facing return contracts defined in the top-level
design (§3).  They are frozen dataclasses constructed from trusted internal
data, not parsed from external input, so Pydantic validation is unnecessary
here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SyncError:
    """A single ticket-scoped error encountered during a mutating operation.

    Attributes
    ----------
    ticket_id:
        Current issue key for human-readable reporting.
    error_type:
        Machine-readable category, e.g. ``"not_found"``,
        ``"permission_denied"``, ``"api_error"``, ``"root_quarantined"``.
    message:
        Human-readable description of the failure.
    retriable:
        Whether the caller should consider retrying this ticket.
    """

    ticket_id: str
    error_type: str
    message: str
    retriable: bool


@dataclass(frozen=True)
class SyncResult:
    """Outcome of a ``sync``, ``refresh``, ``add``, or ``remove_root`` call.

    Each list contains current issue keys.  The sets are disjoint: a ticket
    appears in exactly one of *created*, *updated*, *unchanged*, or *removed*.
    Tickets that could not be fetched appear in *errors* instead.

    Attributes
    ----------
    created:
        Issue keys of newly created local files.
    updated:
        Issue keys of files that were refreshed (re-fetched and rewritten).
    unchanged:
        Issue keys of files that were already fresh and skipped.
    removed:
        Issue keys of files removed from the snapshot (pruned derived tickets,
        roots removed by policy, etc.).
    errors:
        Ticket-scoped errors that did not abort the overall run.
    """

    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    errors: list[SyncError] = field(default_factory=list)


@dataclass(frozen=True)
class DiffEntry:
    """Drift status for one tracked ticket in ``diff`` mode.

    Attributes
    ----------
    ticket_id:
        Current issue key for reporting.
    status:
        One of ``"current"``, ``"stale"``, ``"missing_locally"``, or
        ``"missing_remotely"``.
    changed_fields:
        Field names that differ between local and remote state.  Empty when
        *status* is ``"current"``.
    """

    ticket_id: str
    status: str
    changed_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DiffResult:
    """Outcome of a ``diff`` call.

    Attributes
    ----------
    entries:
        Per-ticket drift classifications.
    errors:
        Ticket-scoped errors encountered during the comparison.
    """

    entries: list[DiffEntry] = field(default_factory=list)
    errors: list[SyncError] = field(default_factory=list)
