# Execution Model

> **Status**: Active

This document defines the ticket execution model used by repository implementation plans.

## 1. Scope

This execution model applies only to named tickets created by an implementation plan that explicitly adopts it, such as [`docs/implementation-plan.md`](<../../implementation-plan.md>).

It does not apply to ad hoc repository work, repository-maintenance tasks, or direct edits to planning, design, or instruction documents unless a named implementation-plan ticket explicitly requires that work.

Each covered ticket runs through three explicit phases.

## 2. Ticket Artifacts

Ticket artifacts live under `docs/execution/`.

- Each ticket has an execution file at `docs/execution/<ticket-id>.md`.
- Each ticket has a review file at `docs/execution/<ticket-id>-review.md`.
- The `*-review.md` artifact is shared by Phase B and Phase C. Phase B owns the findings table and reviewer notes; Phase C appends a ticket-owner-response section below the reviewer-authored content.

Examples (the references might not exist, and are exemplary only):
- Design tickets: `M1-D3` -> `docs/execution/M1-D3.md`, `docs/execution/M1-D3-review.md`
- Implementation tickets: `M1-2` -> `docs/execution/M1-2.md`, `docs/execution/M1-2-review.md`

## 3. Cross-Phase Rules

**Mandatory session-separation rule:**

- Phase A and Phase B must be executed in different agent sessions.
- The session that performs design/implementation work for a ticket must not also perform that ticket's review.
- Phase C must be performed by the same role as Phase A, but not by the Phase B reviewer session for that ticket.
- Phase B must rely only on repository artifacts (diffs, execution log, tests, docs/code) and not on conversational memory from Phase A.
- Phase C must respond from the repository state and the Phase B review artifact, and must not rewrite reviewer-authored content.

**Mandatory Markdown link rule (applies to all phases):**

- In all Markdown artifacts touched by the ticket (`docs/`, `docs/execution/`, and `*-review.md`), every reference to a repository file or to a cross-document identifier (ticket ID, finding ID, FW-ID, or any identifier whose definition lives in another document) must be a clickable Markdown link. For file references, link text must be repo-root path text; for cross-document identifiers, link text must be the identifier itself. In both cases, link targets must be reachable relative paths from the current file.

## 4. Phase A - Design/Implement

Phase A produces the ticket deliverable and the execution record needed for independent review. The requirements below are split into a shared core plus ticket-type-specific gates. If a ticket contains both design and implementation deliverables, satisfy both applicable subsections.

### 4.1 Common Requirements

1. **Initialize execution file:** Create (or open) the ticket execution file in `docs/execution/`.
2. **Clarification check:** Add an `## Initial Questions` section and evaluate whether any blocking questions exist.
3. **Question gate behavior:** If blocking questions exist, list them in `## Initial Questions` and stop work. Resume only after all listed questions are answered through interactive follow-up. If no blocking questions exist, record `None` in `## Initial Questions` and proceed.
4. **Work log:** Document progress, decisions, and issues in a `## Work Log` section. If new blocking questions emerge, add them to `## Initial Questions` and stop again until they are answered.
5. **Temporary scaffolding tracking:** When a ticket introduces throw-away or interim behavior, mark it explicitly as temporary in the relevant artifacts for that ticket type (for example design/spec text, document notes, and code comments as applicable), and record the planned replacement/removal milestone or ticket in the execution file. Temporary scaffolding must never be left unlabeled.
6. **Completion notes:** Capture what was produced, validations performed, and follow-up items in a `## Completion Summary` section.
7. **Reviewer handoff:** End Phase A by recording enough detail in the execution file for an independent reviewer session to evaluate the work without additional context.

### 4.2 Design Ticket Requirements

1. **Design alignment check:** Before marking design work complete, verify the deliverable against the governing artifacts for the ticket (for example the ADR, problem statement, prerequisite design docs, framework policies, and role documents as applicable). Record the documents checked in the execution file.
2. **Decision and scope capture:** Record the chosen design, material assumptions, unresolved questions, explicit deferrals, and downstream follow-up dependencies in the execution file so later implementation tickets can rely on repository artifacts alone.
3. **Design validation expectation:** For docs-only design tickets, the execution model does not impose a mandatory automated lint/test gate; instead, record the manual validation or cross-document consistency checks that were performed. If a design ticket also modifies executable code or otherwise falls outside docs-only scope, satisfy the implementation-ticket requirements in Section 4.3 for those changes.

### 4.3 Implementation Ticket Requirements

1. **Coding guidelines compliance:** Before marking implementation complete, verify every change against [`docs/policies/common/coding-guidelines.md`](<coding-guidelines.md>). Check: docstring format, type annotations, exception specificity, async patterns, Pydantic for cross-boundary models, logging, and security rules. Record the compliance check in the execution file.
2. **Non-waivable validation gate:** Before completion, run required validation commands (`ruff check`, `ruff format --check`, and ticket-appropriate test commands). If any command fails, stop and treat it as blocking. Do not mark the ticket complete while failures remain.
3. **No baseline-failure waiver:** "Pre-existing" or "out-of-scope" validation failures do not permit completion. The session must either (a) fix the failing baseline in the same ticket, or (b) explicitly log a blocking prerequisite and stop without marking the ticket complete.

## 5. Phase B - Review

1. **Reviewer session gate:** Start Phase B in a different agent session than Phase A for the same ticket.
2. **Create review file:** Create (or open) the matching `*-review.md` file in `docs/execution/`.
3. **Review focus:** Review for bugs, regressions, design-contract mismatches, operational risks, and missing tests. Use the applicable reference checklist as a lightweight prompt set: [`docs/policies/common/reviews/code-review.md`](<reviews/code-review.md>) for implementation-heavy review, [`docs/policies/common/reviews/design-review.md`](<reviews/design-review.md>) for design-heavy review, and both when a ticket spans both concerns. These references guide reviewer attention but are not a mandatory rubric: the reviewer does not need to answer every prompt, force coverage of irrelevant headings, or restate checklist items that appear satisfactory. Record material findings, notable residual risks, and meaningful testing or validation gaps.
4. **Linear-specific domain layer boundary check:** Verify changes that interact with Linear stayed within the `linear-client` domain layer, except for explicit exceptions documented in the design artifacts for the ticket.
5. **Findings table format:** Record findings in a table with this exact header order:
   `| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |`
6. **Finding ID contract:** Use progressive IDs per ticket in the form `<ticket-id>-Rn` (for example: `M1-1-R1`, `M1-1-R2`, ...). When referencing a finding ID in prose, table cells, or any text outside the `ID` column, always use the fully qualified form (e.g., `M1-3-R5`, never bare `R5`). Bare short-form IDs like `R5` are ambiguous across tickets and must not appear anywhere in the review file.
7. **Initial status contract:** Set `Status` to `Todo` for all newly recorded findings.
8. **Evidence link contract:** In `Evidence`, keep the rendered evidence text as repo-style file paths (optionally with `:line`), and ensure the underlying Markdown link target is reachable from the review file location (use relative links).
9. **Markdown link contract enforcement:** Ensure any repository file references added during review (findings, notes, residual-risk sections) follow the mandatory Markdown link rule.
10. **No-findings case:** If no findings are discovered, state that explicitly in the review file and include any residual risks/testing gaps.

## 6. Phase C - Ticket Owner Response

Phase C is written by the ticket owner: the designer for design tickets, or the implementor for implementation tickets.

1. **Ticket-owner gate:** Start Phase C using the same role that performed Phase A for the ticket. The Phase B reviewer session must not author the response.
2. **Append-only location rule:** Add the response at the bottom of the existing `*-review.md` file in a new `## Ticket Owner Response` section. Do not edit the Phase B findings table, reviewer notes, or reviewer prose.
3. **Response table format:** Record the response in a separate table with this exact header order:
   `| ID | Verdict | Rationale |`
4. **Finding coverage contract:** Add one response row for every Phase B finding ID. The `ID` values must match the reviewer finding IDs exactly.
5. **Verdict contract:** `Verdict` must propose one of these actions:
   - `Fix now`
   - `Defer to <ticket>`
   - `Defer to <milestone>`
   - `Future work`
   - `Discard`
6. **Deferral specificity rule:** Any `Defer ...` verdict must name the exact destination ticket or milestone. Bare `Defer` is not allowed. `Future work` is the only deferred-disposition verdict that intentionally omits an active-ticket or active-milestone destination.
7. **Future-work proposal rule:** `Future work` means the ticket owner proposes moving the item to post-release backlog instead of scheduling it in the active implementation plan. The proposal must not cite a future milestone or placeholder ticket.
8. **Accepted future-work export rule:** If the human accepts a `Future work` disposition, create a new `FW-n` entry in [`docs/future-work.md`](<../../future-work.md>) and then update the same Phase C response row to include a clickable reference to that exported future-work item in the `Rationale` cell.
9. **Reviewer-table content immutability:** Phase C must not rewrite reviewer-authored content in the findings table (`Severity`, `Area`, `Finding`, `Evidence`, `Impact`, `Recommendation` columns) or reviewer prose outside the table. The `Status` column is a lifecycle field owned jointly — see rule 11.
10. **Human adjudication rule:** The Phase C table is a proposal, not a final disposition. The human later reviews the response and decides which findings must be fixed now, which are deferred and to where, which are exported as future work, and which are discarded.
11. **Post-adjudication status tracking:** After the human accepts a Phase C disposition, the ticket owner updates the reviewer findings table `Status` column to reflect implementation progress. Permitted status transitions: `Todo` → `Done` when the fix lands, `Todo` → `Done (<destination>)` when an accepted deferral is recorded (e.g., `Done (M1-3)`, `Done (FW-18)`), `Todo` → `Deferred (<destination>)` when the finding is deferred without an immediate fix, `Todo` → `Future work (<FW-id>)` when exported to the backlog (e.g., `Future work (FW-22)`), or `Todo` → `Discarded` when the human accepts a `Discard` verdict. Structural changes to the findings table (e.g., splitting a row to match an accepted split disposition) are also permitted after human adjudication. Findings that remain `Todo` pending implementation (including accepted `Fix now` verdicts) keep their `Status` as `Todo` until the fix lands. No other findings-table content may be changed.
12. **No-findings case:** If Phase B records no findings, Phase C may be omitted. If a Phase C entry is still desired, record `No findings to respond to.` under the `## Ticket Owner Response` heading instead of creating an empty table.

## 7. Source of Truth

The execution file and review file together are the source of truth for ticket-level work and quality outcomes. Within the review file, Phase B captures reviewer findings and Phase C captures the ticket owner's proposed disposition pending human adjudication.
