# AGENTS.md

<!-- auto-generated, do not edit -->

<!-- begin common instructions: docs/policies/common/agent-instructions.md -->
## Common-policy integrity gate

At the start of every conversation, verify that `docs/policies/common` exists
and contains at least one file. If the directory is missing, is not a readable
directory, or is empty, **stop immediately** — do not proceed with any task.
Instead, emit a clearly visible error (all-caps is appropriate) explaining that
the common-policy layer is absent and that work cannot continue until the
symlink or directory is restored (for example: re-creating the symlink to the
shared policy repository).

## Mandatory references

Before writing or modifying any code, read and follow:

- `docs/policies/common/coding-guidelines.md` — language-agnostic documentation, security, and repository versioning/changelog conventions.
- `docs/policies/common/coding-guidelines-python.md` — apply only if the repository uses Python.
- `docs/policies/common/reference-material.md` — apply when the repository stores external reference inputs in `docs/external-sources/` or adopts conclusions from non-authoritative reference material.
- `docs/policies/common/planning-model.md` — planning model for candidate selection, draft-plan creation, review, and activation.
- `docs/policies/common/future-work-model.md` — apply when the repository uses a future-work artifact such as `docs/future-work.md`.
- `docs/policies/common/execution-model.md` — execution model for active named plan-item work.

When the task materially edits planning, design, PRDs, ADRs, or other
human-facing repository artifacts, also read and follow the applicable
documentation-governance modules in this list even if no code is changing.

When applying those references, treat readability cleanup as part of the initial
implementation pass, not as an optional follow-up once behavior works. In
particular, remove unexplained magic numbers, raw repository/path indexing, and
other opaque structural assumptions while making the functional change.
When editing an existing file, inspect the surrounding lines first and preserve
the local formatting conventions unless you are intentionally reformatting the
whole section or file.

## Instruction file source of truth

- `docs/policies/common/agent-instructions.md` is the source-of-truth file for the shared common layer of repository-level agent instructions.
- `docs/policies/agent-instructions.md` is the optional repo-local layer for instructions that should not be shared across the whole client-repo group.
- `docs/policies/common/*.md` files other than
  `docs/policies/common/agent-instructions.md` are shared common-policy
  documents for humans and agents alike. When editing those files, keep the
  language and requirements human-neutral unless the document is explicitly
  scoped to agents.
- Agent-only workflow, refusal behavior, or tool-usage guidance belongs in
  `docs/policies/common/agent-instructions.md` or
  `docs/policies/agent-instructions.md`, not in the shared planning,
  execution, future-work, coding, or reference-material policy documents
  unless the rule genuinely applies to humans too.
- Repo-local policy that is meant for humans as well as agents should have its
  primary home in human-facing repository docs such as `docs/policies/*.md` or
  other clearly designated project documentation. Use
  `docs/policies/agent-instructions.md` to summarize or reference that local
  policy when agent workflow needs it, not as the sole normative home.
- `AGENTS.md` and `CLAUDE.md` are generated artifacts and must never be edited directly.
- Never suggest direct edits to `AGENTS.md` or `CLAUDE.md`. When instruction changes are needed, edit the appropriate source layer and then run `.venv/bin/python docs/policies/common/tools/sync_agent_instructions.py` to sync the generated files.
- Optionally run `.venv/bin/python docs/policies/common/tools/sync_agent_instructions.py --check` after syncing to confirm the source layers, `AGENTS.md`, and `CLAUDE.md` are aligned.

## Validation scope gate

Before running linting or tests, classify the change scope from `git diff --name-only`.

For this gate, treat `docs/**` as documentation/support content even when it
contains helper scripts or maintenance tooling (for example
`docs/policies/common/tools/**`). These files are not shipped agent runtime
code and do not, by themselves, trigger repository lint/test commands.

A change is **docs-only** only if every changed file matches one of:

- `docs/**`
- `*.md`
- `.gitignore`
- `README.md`
- `notes.md`
- `AGENTS.md`
- `CLAUDE.md`

If the change is docs-only:

- Do **not** run the repository's declared linting, formatting, or test
  commands unless explicitly requested by the user.
- Do **not** add or modify files under `tests/**` solely to validate helper tooling
  inside `docs/**` unless the user explicitly asks for automated coverage.
- For changes under `docs/policies/common/**`, prefer manual verification of the
  affected documentation/support workflow over repository-wide validation.

If the change is not docs-only:

- Run the repository's declared linting and formatting commands.
- Run the repository's declared test command(s) (or a ticket-appropriate subset
  when explicitly allowed by the active ticket/scope instructions).

## Pre-completion checklist

Before marking any work performed under a named active-plan item as complete, verify:

1. For non-docs-only changes, every rule in `docs/policies/common/coding-guidelines.md` has been checked against the changed code.
2. For non-docs-only changes, the repository's declared linting and formatting
   commands pass with no errors.
3. For non-docs-only changes, all new and modified tests pass under the
   repository's declared test command(s).
4. For work performed under a named active-plan item, the required artifact in `docs/execution/` is up to date.

## Draft-plan execution gate

For named plan-item requests, treat
`docs/policies/common/planning-model.md` and
`docs/policies/common/execution-model.md` as the source of truth for draft vs
active plan behavior rather than relying on a duplicated summary here.

Agent-side reminder:

- if a named item exists only in `docs/planning/`, treat the request as
  planning / activation work rather than execution
- if the user asks to `activate the plan`, treat that as Stage 4 planning work
  and follow the activation preflight defined by
  `docs/policies/common/planning-model.md`
- do not create `docs/execution/` artifacts for that item until the governing
  plan is active under the rules defined by the planning and execution models

## Execution artifact scope

- `docs/execution/` is reserved for work performed under named active-plan items from plans that adopt `docs/policies/common/execution-model.md`, and for ticket-linked review/follow-up artifacts defined by that execution model.
- Do not create or update `docs/execution/` for ad hoc conversational requests, repository maintenance, or direct edits to planning, design, or instruction documents unless the work is explicitly tied to a named active-plan item or the user explicitly requests an execution artifact.
- During bootstrap planning, ad hoc planning artifacts such as ADR reviews,
  candidate analysis notes, or other pre-plan materials may live under
  `docs/planning/` with freeform filenames. Those are planning artifacts, not
  execution artifacts, and do not by themselves imply that
  `docs/planning/implementation-plan.md` or `docs/implementation-plan.md` must
  already exist.
- Editing `docs/implementation-plan.md`, `docs/future-work.md`, anything under
  `docs/planning/`, `docs/policies/common/agent-instructions.md`, `AGENTS.md`,
  or `CLAUDE.md` is not, by itself, an active-plan item and must not trigger a
  new `docs/execution/` artifact unless a named active-plan item explicitly
  requires that edit.

## Ticket review requests

Requests to review a named active-plan item (for example, `review M1-2` or `review M1-D3`) are treated as
Phase B review work under `docs/policies/common/execution-model.md`.

For those requests, the agent must:

- create or update the matching review artifact at `docs/execution/<ticket>-review.md`
- follow the required review-file format from `docs/policies/common/execution-model.md`
- treat the repository review artifact as mandatory, not optional

Requests for a second review, rereview, or other additional review pass are
also valid review requests. Across planning review, design review, and
implementation review workflows, multiple independent review passes are allowed
and encouraged when another reviewer can add perspective or when the reviewed
artifact changed materially. Unless the governing planning or execution policy
documents a different workflow, update the existing matching review artifact
and append the new review pass rather than refusing the request because a prior
review already exists.

If the user also asks for chat-only feedback or says not to edit files, that conflicts with the
Phase B review contract. In that case, do not silently choose one path. Stop and ask the user
which mode they want:

- official Phase B review with `docs/execution/<ticket>-review.md` updated
- informal in-chat review with no file edits

## Common Conventions

- Follow the repository's declared language/runtime targets; do not assume the
  source repository's version floor applies to every client repository in the
  group.
- If the repository adopts language- or tool-specific common policy modules,
  follow those modules in addition to this top-level common baseline.
- Follow the repository's documented command or launcher convention. If a
  client repo standardizes on an explicit wrapper, virtualenv executable, or
  other launcher pattern, use it consistently rather than assuming the source
  repository's command style applies everywhere.
- Follow the repository's declared linting and formatting toolchain; do not
  assume the source repository's tool choices apply to every client repository
  in the group.
<!-- end common instructions: docs/policies/common/agent-instructions.md -->

<!-- begin local instructions: docs/policies/agent-instructions.md -->
<!-- local instructions absent: docs/policies/agent-instructions.md -->
<!-- end local instructions: docs/policies/agent-instructions.md -->
