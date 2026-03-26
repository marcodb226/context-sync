# CLAUDE.md

<!-- auto-generated, do not edit -->

<!-- begin common instructions: docs/policies/common/agent-instructions.md -->
## Common-policy integrity gate

At the start of every conversation, verify that `docs/policies/common` exists
and contains at least one file. Use the Bash tool (for example,
`ls docs/policies/common`) to perform this check — do **not** use the Glob
tool, which does not follow symlinks and will incorrectly report the directory
as missing or empty even when the symlink target is fully accessible. If the
directory is missing, is not a readable directory, or is empty, **stop
immediately** — do not proceed with any task. Instead, emit a clearly visible
error (all-caps is appropriate) explaining that the common-policy layer is
absent and that work cannot continue until the symlink or directory is restored
(for example: re-creating the symlink to the shared policy repository).

## Mandatory references

Before writing or modifying any code, read and follow:

- `docs/policies/common/coding-guidelines.md` — language-agnostic documentation, security, and repository versioning/changelog conventions.
- `docs/policies/common/cli-conventions.md` — apply only if the repository builds CLI tools.
- `docs/policies/common/documentation-workflow.md` — apply when the repository publishes supported docs, generated API reference, or operator guides.
- `docs/policies/common/reference-material.md` — apply when the repository stores external reference inputs in `docs/external-sources/` or adopts conclusions from non-authoritative reference material.
- `docs/policies/common/planning-model.md` — planning model for candidate selection, draft-plan creation, review, and activation.
- `docs/policies/common/future-work-model.md` — apply when the repository uses a future-work artifact such as `docs/future-work.md`.
- `docs/policies/common/execution-model.md` — execution model for active named plan-item work.
- `docs/policies/common/release-workflow.md` — apply when the repository publishes versioned releases or maintains explicit release/bootstrap workflow artifacts.
- `docs/policies/common/terminology-policy.md` — apply when the repository maintains a `docs/policies/terminology.md` file with project-specific terminology constraints.

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

- `docs/policies/common/agent-instructions.md` is the source-of-truth file for the shared cross-language layer of repository-level agent instructions.
- `docs/policies/common/<layer>/agent-instructions.md` files are optional source-of-truth files for shared language/runtime-specific agent-instruction layers. They are included in generated entrypoints only when selected by the repo-local `docs/policies/agent-entrypoints.cfg` config.
- `docs/policies/agent-instructions.md` is the optional repo-local layer for instructions that should not be shared across the whole client-repo group.
- Common policy documents outside the `agent-instructions.md` entrypoint files
  are shared common-policy documents for humans and agents alike. When editing
  those files, keep the language and requirements human-neutral unless the
  document is explicitly scoped to agents.
- Agent-only workflow, refusal behavior, or tool-usage guidance belongs in
  `docs/policies/common/agent-instructions.md`, an applicable
  `docs/policies/common/<layer>/agent-instructions.md`, or
  `docs/policies/agent-instructions.md`, not in the shared planning,
  execution, future-work, coding, or reference-material policy documents unless
  the rule genuinely applies to humans too.
- Repo-local policy that is meant for humans as well as agents should have its
  primary home in human-facing repository docs such as `docs/policies/*.md` or
  other clearly designated project documentation. Use
  `docs/policies/agent-instructions.md` to summarize or reference that local
  policy when agent workflow needs it, not as the sole normative home.
- `AGENTS.md` and `CLAUDE.md` are generated artifacts and must never be edited directly.
- Never suggest direct edits to `AGENTS.md` or `CLAUDE.md`. When instruction changes are needed, edit the appropriate source layer and then run `python docs/policies/common/tools/sync_agent_instructions.py` to sync the generated files.
- Optionally run `python docs/policies/common/tools/sync_agent_instructions.py --check` after syncing to confirm the source layers, `AGENTS.md`, and `CLAUDE.md` are aligned.

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

## Execution-model phase transitions

When beginning work on a specific execution-model phase (Phase A, Phase B, or
Phase C) for a named plan item:

1. **Re-read the governing section before starting.** Open
   `docs/policies/common/execution-model.md` and read the section for the phase
   you are about to perform. If a repo-local
   `docs/policies/execution-model.md` exists, read it as well — it may
   augment or override the common-layer rules. Do not rely on a prior reading
   from earlier in the same conversation — the rules are detailed enough that
   recall-based approximation leads to structural violations.

2. **Create the required artifact structure first, then do the work.** For
   Phase C, create the verdict table in the review file before implementing any
   code fixes. For Phase B, create the review file and findings table before
   writing findings prose. Getting the artifact skeleton right first prevents
   the structural requirements from being forgotten once implementation work
   begins.

3. **Run the phase completion gate before declaring done.** Each phase has
   explicit completion requirements. Before marking the phase complete, open
   the execution model, locate the completion gate for that phase, and verify
   each sub-requirement individually. Do not treat this as a mental
   checklist — read the actual rules and confirm against the actual artifacts.
   The completion gates are:
   - **Phase A:** §4.1 rule 9 (explicit completion gate with
     sub-requirements, including the applicable ticket-type subsection).
   - **Phase B:** §5 rule 13 (explicit completion gate with sub-requirements).
   - **Phase C:** §6 rule 17 (explicit completion gate with sub-requirements).
4. **Do not mark a ticket `Done` during Phase A unless the human explicitly
   instructs you to do so.** The default Phase A row status for an
   execution-model ticket is `In progress`. Even when the Phase A execution
   artifact is complete, treat the ticket itself as still in progress until
   the execution model's post-review closeout rules say the row may move to
   `Done` (for example, after a no-findings Phase B review is observed or
   after Phase C / accepted post-review closeout is complete).

## Codebase Navigation

- Prefer `rg` and `rg --files` over slower text/file discovery tools such as
  `grep` and `find` for routine codebase navigation.
- When a semantic symbol-navigation tool is available for the active language,
  prefer it to raw text search when locating definitions, references, or call
  sites.
- Use plain-text search for comments, string literals, config keys, SQL, YAML,
  logs, or similar non-symbol content, and as the fallback when symbol-aware
  lookup is unavailable or fails.
- After identifying candidate files, read the smallest relevant file ranges
  needed to confirm behavior instead of defaulting to whole-file reads. Expand
  outward only when local context is insufficient.

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

<!-- begin common layer instructions (python): docs/policies/common/python/agent-instructions.md -->
Apply this layer when the repo-local entrypoint composition config includes the
`python` layer.

This file keeps the highest-salience Python-specific instructions directly in
generated agent entrypoints. It supplements, and does not replace, the full
Python policy documents listed below.

## Mandatory references

Before writing or modifying Python code, read and follow:

- `docs/policies/common/python/coding-guidelines.md` — Python-specific typing, linting, async, exception, testing, and version-metadata rules.
- `docs/policies/common/python/cli-conventions.md` — apply only if the repository builds CLI tools in Python.
- `docs/policies/common/python/documentation-workflow.md` — apply only if the repository is a Python package that publishes supported docs with MkDocs or an equivalent maintained docs site.
- `docs/policies/common/python/release-workflow.md` — apply only if the repository publishes Python package artifacts.
- `docs/policies/common/python/agent-awareness.md` — apply if the repository builds a Python package with a public API surface.

## Pre-completion checklist

Before marking Python implementation work complete, verify:

1. No new `typing.Any` appears in function or method signatures when a concrete type is available.
2. Use `TYPE_CHECKING` imports with `from __future__ import annotations` for deferred annotation resolution instead of falling back to `Any`.
3. If `Any` is genuinely required, keep the exception targeted with `# noqa: ANN401` and a brief justification.

## Codebase Navigation

- When a semantic symbol-navigation tool is available for Python, prefer it to raw text search when locating definitions, references, or call sites.
<!-- end common layer instructions (python): docs/policies/common/python/agent-instructions.md -->

<!-- begin local instructions: docs/policies/agent-instructions.md -->
This is the repo-local layer for agent instructions that should not be shared
across the whole client-repo group.

## Terminology

Follow [docs/policies/terminology.md](terminology.md). In particular, never use
the word "syncer" in any output — code, docs, comments, labels, commit
messages, or generated artifacts.
<!-- end local instructions: docs/policies/agent-instructions.md -->
