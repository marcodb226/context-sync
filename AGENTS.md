# AGENTS.md

<!-- auto-generated, do not edit -->

## Mandatory references

Before writing or modifying any code, read and follow:

- `docs/coding-guidelines.md` — formatting, type annotations, async patterns, exception handling, docstring format, testing, security rules.
- `docs/execution-model.md` — execution model for implementation-plan ticket work.

## Instruction file source of truth

- `agent-instructions.md` is the only source-of-truth file for repository-level agent instructions.
- `AGENTS.md` and `CLAUDE.md` are generated artifacts and must never be edited directly.
- Never suggest direct edits to `AGENTS.md` or `CLAUDE.md`. When instruction changes are needed, edit `agent-instructions.md` and then run `.venv/bin/python tools/sync_agent_instructions.py` to sync the generated files.
- Optionally run `.venv/bin/python tools/sync_agent_instructions.py --check` after syncing to confirm `agent-instructions.md`, `AGENTS.md`, and `CLAUDE.md` are aligned.

## Validation scope gate

Before running linting or tests, classify the change scope from `git diff --name-only`.

A change is **docs-only** only if every changed file matches one of:

- `docs/**`
- `*.md`
- `README.md`
- `notes.md`
- `agent-instructions.md`
- `AGENTS.md`
- `CLAUDE.md`

If the change is docs-only:

- Do **not** run `.venv/bin/ruff check`, `.venv/bin/ruff format --check`, or `.venv/bin/python -m pytest tests/` unless explicitly requested by the user.

If the change is not docs-only:

- Run `.venv/bin/ruff check`.
- Run `.venv/bin/ruff format --check`.
- Run `.venv/bin/python -m pytest tests/` (or ticket-appropriate subset when explicitly allowed by the active ticket/scope instructions).

## Pre-completion checklist

Before marking any work performed under a named implementation-plan ticket as complete, verify:

1. For non-docs-only changes, every rule in `docs/coding-guidelines.md` has been checked against the changed code.
2. For non-docs-only changes, `.venv/bin/ruff check` and `.venv/bin/ruff format --check` pass with no errors.
3. For non-docs-only changes, all new and modified tests pass (`.venv/bin/python -m pytest tests/`).
4. For work performed under a named implementation-plan ticket, the required artifact in `docs/execution/` is up to date.

## Execution artifact scope

- `docs/execution/` is reserved for work performed under named tickets from repository implementation plans that adopt `docs/execution-model.md`, and for ticket-linked review/follow-up artifacts defined by that execution model.
- Do not create or update `docs/execution/` for ad hoc conversational requests, repository maintenance, or direct edits to planning, design, or instruction documents unless the work is explicitly tied to a named ticket or the user explicitly requests an execution artifact.
- Editing `docs/implementation-plan.md`, `agent-instructions.md`, `AGENTS.md`, or `CLAUDE.md` is not, by itself, an implementation-plan ticket and must not trigger a new `docs/execution/` artifact unless a named ticket explicitly requires that edit.

## Ticket review requests

Requests to review a named implementation-plan ticket (for example, `review M1-2` or `review M1-D3`) are treated as
Phase B review work under `docs/execution-model.md`.

For those requests, the agent must:

- create or update the matching review artifact at `docs/execution/<ticket>-review.md`
- follow the required review-file format from `docs/execution-model.md`
- treat the repository review artifact as mandatory, not optional

If the user also asks for chat-only feedback or says not to edit files, that conflicts with the
Phase B review contract. In that case, do not silently choose one path. Stop and ask the user
which mode they want:

- official Phase B review with `docs/execution/<ticket>-review.md` updated
- informal in-chat review with no file edits

## Project layout

- `shared/` — framework code shared by all agent roles (installed as a package).
- `agents/<role>/` — role-specific agent code.
- `tests/` — mirrors `shared/` and `agents/` source tree.
- `docs/design/` — design documents (gate implementation tickets).
- `docs/execution/` — per-ticket execution logs.
- `deps/` — vendored private wheels (gitignored).
- `tools/` — standalone bootstrap/setup scripts (not part of agent runtime).

## Key conventions

- Python 3.13+. Async-first. Pydantic for all cross-boundary data models.
- For all Python-related commands in this repository, use the project virtualenv executables explicitly: `.venv/bin/python`, `.venv/bin/pytest`, `.venv/bin/ruff`, `.venv/bin/pip`, etc. Do not rely on bare `python`/`pytest`/`ruff`/`pip` or shell activation state.
- `linear-client` is a private dependency — see `docs/design/linear-client.md` Installation section.
- Ruff is the sole linter/formatter. Config is in `pyproject.toml`.
- Tests use `conftest.py` sys.modules mocking for `linear_client` — test passage does not verify the real library works.
