# Implementation Plan - Context Sync v1.0 Delivery

> **Status**: Active
> **Governing artifacts**:
> [docs/problem-statement.md](problem-statement.md),
> [docs/adr.md](adr.md),
> [docs/design/0-top-level-design.md](design/0-top-level-design.md),
> [docs/workspace-setup.md](workspace-setup.md),
> [docs/future-work.md](future-work.md),
> [docs/policies/common/planning-model.md](policies/common/planning-model.md),
> [docs/policies/common/execution-model.md](policies/common/execution-model.md)

---

## 1. Scope and Strategy

This active plan is the repository's formal delivery plan for a shippable
`context-sync` `1.0.0`. It turns the existing problem statement, ADR, design
notes, ADR review outcomes, and later accepted planning amendments into a
sequenced path from foundation work through supported runtime wiring,
user-facing docs, and the first stable release.

**Implementation strategy - foundation first, then whole-snapshot behavior.**

The plan front-loads the release-gating refresh validation work and the shared
file-system/runtime primitives before building `sync`, then layers incremental
operations and CLI/readiness work on top of that base. This sequencing keeps
the early tickets focused on repository-shaping decisions that later milestones
should not have to rediscover.

Milestone 4 remains the existing CLI/review/readiness layer and is unchanged
by the 2026-03-23 amendment. The repository is still pre-release after
Milestone 4 because the real gateway, supported docs surface, and canonical
release workflow are still missing. This plan therefore continues through
Milestone 5 and Milestone 6 before the product can be treated as a credible
`1.0.0`.

**Guiding principles:**
- Preserve the contracts already defined in
  [docs/adr.md](adr.md) and
  [docs/design/0-top-level-design.md](design/0-top-level-design.md)
  instead of reopening settled design questions during implementation.
- Treat
  [OQ-1](adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior)
  as a release gate for `refresh`, not as a post-release TODO.
- Keep first-release scope aligned with the explicit deferrals in
  [docs/future-work.md](future-work.md).
- Build shared deterministic rendering, manifest, and lock helpers once and
  reuse them across `sync`, `refresh`, `remove`, and `diff`.

**What this plan covers:** the initial Python package and project scaffold, the
async library surface, deterministic context-directory persistence, whole-
snapshot `sync` (with optional root argument), incremental `refresh`,
`remove`, `diff`, a thin
CLI wrapper, post-implementation CLI and API review passes, the real
`linear-client`-backed gateway, supported public-runtime validation, supported
user-facing docs, the canonical release workflow, a dedicated `1.0.0`
readiness review, and the actual `1.0.0` cut plus next-cycle bootstrap.

### 1.1 Stage 1 Planning Inputs

- Bootstrap candidate sources:
  [docs/problem-statement.md](problem-statement.md),
  [docs/adr.md](adr.md),
  [docs/design/0-top-level-design.md](design/0-top-level-design.md),
  [docs/design/linear-client-v1.0.0.md](design/linear-client-v1.0.0.md),
  [docs/planning/26.03.15 - ADR review.md](planning/26.03.15%20-%20ADR%20review.md),
  and [docs/future-work.md](future-work.md).
- Direct human request: start the first formal implementation plan draft for
  the repository.
- Prior release / archival context: none. The repository is still in bootstrap
  planning state and does not yet have an active plan artifact.
- Material-amendment candidate sources applied on 2026-03-23:
  [docs/execution/M4-1-review.md](execution/M4-1-review.md),
  [docs/execution/M4-2-review.md](execution/M4-2-review.md),
  [README.md](../README.md),
  [src/context_sync/version.py](../src/context_sync/version.py),
  [docs/design/linear-domain-coverage-audit-v1.0.0.md](design/linear-domain-coverage-audit-v1.0.0.md),
  [docs/policies/common/documentation-workflow.md](policies/common/documentation-workflow.md),
  [docs/policies/common/release-workflow.md](policies/common/release-workflow.md),
  [docs/policies/common/python/release-workflow.md](policies/common/python/release-workflow.md),
  [docs/policies/common/release-checklist-template.md](policies/common/release-checklist-template.md),
  [docs/policies/common/coding-guidelines.md](policies/common/coding-guidelines.md),
  and direct human request to extend the plan from Milestone 5 onward to a
  shippable `1.0.0` without changing the remaining Milestone 4 items.
- Material-amendment candidate sources applied on 2026-03-24:
  [docs/future-work.md §FW-10](future-work.md#fw-10-cli-simplification-amendment),
  [docs/execution/M4-R1.md](execution/M4-R1.md),
  [docs/execution/M4-R2.md](execution/M4-R2.md), and
  [docs/planning/change-requests/CR-26.03.24.md](planning/change-requests/CR-26.03.24.md).
- Material-amendment candidate sources applied on 2026-03-24 (second):
  [docs/policies/common/coding-guidelines.md](policies/common/coding-guidelines.md),
  [docs/policies/common/python/coding-guidelines.md](policies/common/python/coding-guidelines.md),
  [docs/policies/common/python/agent-awareness.md](policies/common/python/agent-awareness.md),
  [docs/policies/common/README.md](policies/common/README.md), and
  [docs/planning/change-requests/CR-26.03.24-policy-compliance.md](planning/change-requests/CR-26.03.24-policy-compliance.md).
- Material-amendment candidate sources applied on 2026-04-07:
  [linear-client CHANGELOG.md](../../linear-client/CHANGELOG.md),
  [linear-client docs/pub/release-1.1.0.md](../../linear-client/docs/pub/release-1.1.0.md),
  [docs/design/linear-domain-coverage-audit-v1.0.0.md](design/linear-domain-coverage-audit-v1.0.0.md),
  [docs/design/linear-client-v1.0.0.md](design/linear-client-v1.0.0.md),
  [docs/policies/common/python/agent-awareness.md](policies/common/python/agent-awareness.md),
  and direct human request to upgrade context-sync to `linear-client` v1.1.0.

### 1.2 Candidate Decisions

Because
[docs/future-work.md](future-work.md)
has no shortlisted `Next release` items, the initial bootstrap planning pass
and later accepted material amendments selected concrete scope from the
problem statement, ADR/design artifacts, accepted review outcomes, and direct
human requests while explicitly keeping the current `FW-*` backlog deferred.

| Candidate | Decision | Plan destination | Notes |
| --- | --- | --- | --- |
| Live Linear validation environment bootstrap from [docs/design/0-top-level-design.md](design/0-top-level-design.md#11-linear-dependency-boundary), [docs/design/linear-client-v1.0.0.md](design/linear-client-v1.0.0.md#authentication), and direct human clarification during planning | Keep | [M1-O1](#m1-o1---live-linear-validation-environment-available) | Makes the human-provided runtime/bootstrap prerequisite for the release-gate spike explicit before [M1-D1](#m1-d1---refresh-freshness-validation-spike) begins. |
| Refresh correctness gate from [OQ-1](adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior) | Keep | [M1-D1](#m1-d1---refresh-freshness-validation-spike) | Must be settled before `refresh` can be considered implementation-complete. |
| Post-spike refresh-contract amendment from [docs/design/refresh-freshness-validation.md](design/refresh-freshness-validation.md) and [docs/planning/change-requests/CR-26.03.18.md](planning/change-requests/CR-26.03.18.md) | Keep | [M1-D3](#m1-d3---refresh-composite-freshness-contract-amendment) | Separates the release-gate spike from the governing design rewrite, makes relation freshness mandatory first-release scope, and narrows attachment freshness out of the v1 incremental-refresh correctness contract. |
| Linear domain-layer coverage audit and adapter-boundary definition from [docs/adr.md](adr.md#31-foundation), [docs/design/0-top-level-design.md](design/0-top-level-design.md#11-linear-dependency-boundary), and [docs/design/linear-client-v1.0.0.md](design/linear-client-v1.0.0.md) | Keep | [M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) | Makes the domain-vs-GraphQL fallback decision explicit before traversal, relation, and refresh tickets depend on it. |
| Library API, runtime configuration, and package bootstrap from [docs/adr.md](adr.md#31-foundation), [docs/design/0-top-level-design.md](design/0-top-level-design.md#1-library-api), and [docs/design/linear-client-v1.0.0.md](design/linear-client-v1.0.0.md) | Keep | [M1-1](#m1-1---project-scaffold-and-public-runtime-contracts) | Establishes the project layout, public interfaces, per-process concurrency controls, reusable test harness, and the narrow dependency boundary with `linear-client`. |
| Manifest, deterministic ticket rendering, and lock metadata from [docs/adr.md](adr.md#2-persistence-format), [docs/design/0-top-level-design.md](design/0-top-level-design.md#21-context-directory-contents), and [ADR-R2a](planning/26.03.15%20-%20ADR%20review.md#adr-r2a-done-stale-lock-recovery-and-lock-metadata) | Keep | [M1-2](#m1-2---manifest-lock-and-rendering-primitives) | Shared persistence helpers should land before the flow-specific tickets. |
| Tiered per-root traversal and bounded reachable sets from [docs/adr.md](adr.md#13-traversal-order-and-ticket-cap) and [ADR-R3](planning/26.03.15%20-%20ADR%20review.md#adr-r3-done-pure-breadth-first-traversal-cutoffs) | Keep | [M2-1](#m2-1---reachable-graph-builder-and-tiered-per-root-traversal) | Structural edges must beat informational edges near the ticket cap. |
| Full-snapshot `sync` behavior from [docs/adr.md](adr.md#51-sync-full-snapshot-rebuild) and [docs/design/0-top-level-design.md](design/0-top-level-design.md#61-sync-flow) | Keep | [M2-3](#m2-3---full-snapshot-sync-flow) | Initial materialization should exist before incremental maintenance flows. |
| Incremental `refresh` and root quarantine semantics from [docs/adr.md](adr.md#52-refresh-incremental-whole-snapshot-update), [docs/adr.md](adr.md#61-snapshot-consistency-contract), and [ADR-R4](planning/26.03.15%20-%20ADR%20review.md#adr-r4-done-terminal-root-fragility) | Keep | [M3-1](#m3-1---incremental-refresh-and-quarantined-root-recovery) | Depends on the `OQ-1` outcome and should carry the default `quarantine` policy. |
| Root-set mutation flows from [docs/design/0-top-level-design.md](design/0-top-level-design.md#63-add-flow) and [docs/design/0-top-level-design.md](design/0-top-level-design.md#65-remove-root-flow) | Keep | [M3-2](#m3-2---add-and-remove-root-whole-snapshot-flows) | `add` and `remove-root` should reuse whole-snapshot refresh semantics under one writer lock. |
| Non-mutating drift inspection from [docs/adr.md](adr.md#53-diff-non-mutating-drift-inspection) and [docs/design/0-top-level-design.md](design/0-top-level-design.md#64-diff-flow) | Keep | [M3-3](#m3-3---diff-mode-and-lock-aware-drift-reporting) | Must preserve the read-only lock behavior described in the ADR. |
| CLI packaging and operator-facing runtime docs from [docs/design/0-top-level-design.md](design/0-top-level-design.md#2-cli-interface), [README.md](../README.md), and [docs/policies/common/coding-guidelines.md](policies/common/coding-guidelines.md) | Keep | [M4-1](#m4-1---cli-surface-and-command-output-contracts), [M4-2](#m4-2---operational-logging-validation-hardening-and-user-docs) | The repo currently has no runtime scaffold, so the first implementation pass must also define how humans run and validate the tool. |
| Post-implementation CLI interface review of the command surface from direct human request, [docs/execution/M4-1-review.md](execution/M4-1-review.md), and [docs/design/0-top-level-design.md](design/0-top-level-design.md#2-cli-interface) | Keep | [M4-R1](#m4-r1---cli-interface-review) | Adds a dedicated top-level CLI review ticket that stays distinct from the Phase B review of [M4-1](#m4-1---cli-surface-and-command-output-contracts) and settles command-surface semantics before the separate API review. |
| Post-implementation public API review of the `ContextSync` library surface from direct human request, [docs/design/0-top-level-design.md](design/0-top-level-design.md#1-library-api), and the planned CLI review outcome | Keep | [M4-R2](#m4-r2---api-interface-review) | Keeps the public library API review separate from the CLI review, lets [M4-R1](#m4-r1---cli-interface-review) resolve command-surface semantics first, and preserves room for API-only follow-on work such as [M4-3](#m4-3---rename-root-ticket-id-to-key). |
| Post-M4 runtime gateway and public-entrypoint validation from [docs/execution/M4-1-review.md](execution/M4-1-review.md), [docs/execution/M4-2-review.md](execution/M4-2-review.md), [README.md](../README.md), and direct human request | Keep | [M5-1](#m5-1---real-linear-gateway-and-runtime-wiring), [M5-2](#m5-2---supported-public-runtime-validation-and-smoke-path) | Extends the plan past the fake-gateway-only dead end without rewriting the remaining Milestone 4 items. |
| Post-M4 supported docs, release workflow, and actual `1.0.0` cut from [docs/execution/M4-2-review.md](execution/M4-2-review.md), [docs/policies/common/documentation-workflow.md](policies/common/documentation-workflow.md), [docs/policies/common/release-workflow.md](policies/common/release-workflow.md), [docs/policies/common/python/release-workflow.md](policies/common/python/release-workflow.md), [docs/policies/common/release-checklist-template.md](policies/common/release-checklist-template.md), and direct human request | Keep | [M6-O1](#m6-o1---release-channel-and-install-path-chosen), [M6-O2](#m6-o2---release-publication-credentials-and-approval-window-available), [M6-R1](#m6-r1---100-release-readiness-review), [M6-1](#m6-1---supported-user-facing-docs-and-installoperator-guide), [M6-2](#m6-2---canonical-release-workflow-checklist-and-version-state-guardrails), [M6-3](#m6-3---100-release-cut-archive-and-next-cycle-bootstrap) | Makes the supported install path, release automation/checklist, version guardrails, readiness review, and first stable release part of the active plan. |
| CLI and library simplification from [FW-10](future-work.md#fw-10-cli-simplification-amendment), [M4-R1](execution/M4-R1.md), and [M4-R2](execution/M4-R2.md) | Keep | [M4.1-1](#m4.1-1---cli-and-library-simplification) | Pulls the deferred CLI simplification into the active plan immediately before M5 so the real gateway and all subsequent work uses the settled four-command surface. |
| [FW-1](future-work.md#fw-1-comment-storage-optimizations) | Defer | None in this plan | Keep the first-release full-comment-history contract. |
| [FW-2](future-work.md#fw-2-attachment-content-handling) | Defer | None in this plan | Attachment and resource handling remains metadata-only in v1, and attachment-only freshness drift is not part of the first-release incremental-refresh correctness contract. |
| [FW-3](future-work.md#fw-3-whole-snapshot-atomic-commit) | Defer | None in this plan | Preserve atomic file writes, but defer whole-directory atomic commit. |
| [FW-4](future-work.md#fw-4-historical-ticket-alias-import) | Defer | None in this plan | Offline alias resolution is limited to aliases observed after tracking begins. |
| [FW-5](future-work.md#fw-5-ticket-history-and-sectioned-ticket-artifacts) | Defer | None in this plan | The v1 base snapshot is limited to metadata, description, and comments. |
| [FW-6](future-work.md#fw-6-transient-ticket-preview-without-persistence) | Defer | None in this plan | Preview-only behavior is explicitly out of scope for the first plan. |
| Cross-process rate-limit coordination from [ADR-R5](planning/26.03.15%20-%20ADR%20review.md#adr-r5-discarded-the-thundering-herd-rate-limit-risk) | Drop | None in this plan | Keep rate-limit/backoff behavior inside `linear-client` or the embedding runtime. |
| UUID-based ticket filenames from [ADR-R6](planning/26.03.15%20-%20ADR%20review.md#adr-r6-discarded-file-renaming-breaks-strict-idempotency) | Drop | None in this plan | Keep human-readable current issue-key filenames as the persisted default. |
| Upgrade `linear-client` dependency from v1.0.0 to v1.1.0, add a new v1.1.0 domain-coverage audit, and update M5-1 to use the new audit from [CR-26.04.07](planning/change-requests/CR-26.04.07.md) | Keep | [M5-D1](#m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110) (new design ticket), [M5-D2](#m5-d2---design-artifact-refresh-for-v110-workspace-model) (new design ticket), updates to [M5-1](#m5-1---real-linear-gateway-and-runtime-wiring) dependencies and notes | v1.1.0 closes the relation-read and per-issue comment-metadata gaps. A new audit defines the authoritative boundary for M5-1 without retroactively modifying the completed M1-D2 deliverable. A separate design-artifact refresh brings the ADR, top-level design, and dependency pointers to current state. |

### 1.3 Execution Model

This active plan explicitly adopts
[docs/policies/common/execution-model.md](policies/common/execution-model.md)
for the named operational, design, review, and implementation tickets below.
Once a ticket begins, its work must follow the execution-model Phase A/B/C
artifact flow in [docs/execution/](execution/) and satisfy the validation and
review gates defined there.

Ticket identifiers in this active plan use these forms:

- Operational tickets: `Mx-Oy`
- Design tickets: `Mx-Dy`
- Review tickets: `Mx-Ry`
- Implementation tickets: `Mx-z`
- Review finding IDs after activation: `<ticket-id>-Rn`

---

## 2. Milestone Overview

| Milestone | Name | Primary deliverable |
| --- | --- | --- |
| M1 | Foundation and release-gate validation | Live validation bootstrap, project scaffold, Linear adapter-boundary audit, shared persistence primitives, and an explicit `OQ-1` outcome |
| M2 | Full snapshot materialization | Deterministic traversal, rendering, and whole-snapshot `sync` |
| M3 | Incremental maintenance and drift inspection | `refresh`, `add`, `remove-root`, and `diff` with the ADR's missing-root and lock semantics |
| M4 | CLI and release readiness | Human-facing commands, separate CLI and API reviews, operational logging, validation coverage, and onboarding docs |
| M4.1 | CLI and library simplification | Four-command public CLI (`sync [TICKET]`, `refresh`, `remove TICKET`, `diff`), matching library method boundaries, traversal-config preservation semantics, and optional-ticket `sync` covering the full-rebuild-all-roots use case without root-membership change |
| M4.2 | Common-policy compliance | `scripts/validate.sh`, Pyright integration, semantic types (`_types.py`), `py.typed` marker, `coverage.py` tooling, `examples/` directory, `docs/design/dependency-map.md`, public interface docstring completion, and README common-policy bootstrap fixes |
| M5 | Supported runtime gateway | A real `linear-client`-backed gateway, wired public CLI/library entry points, and supported validation of the shipped runtime path |
| M6 | Supported docs and `1.0.0` release workflow | Canonical user-facing docs, release automation/checklist/version guardrails, an explicit `1.0.0` readiness review, and the actual `1.0.0` cut plus next-cycle bootstrap |

The sequence intentionally moves from repository-shaping primitives to
full-snapshot behavior and only then to incremental flows. That keeps the plan
from implementing `refresh` or CLI affordances on top of unstable persistence
or traversal foundations.

---

## 3. Milestone 1 - Foundation and Release-Gate Validation

**Goal:** establish the operational bootstrap for live validation, the
package/runtime baseline, shared file-system helpers, and the
refresh-correctness decision that later milestones depend on.

### 3.1 Operational Prerequisites

| # | Status | Item | Requirement | Unblocks | Verification | Source |
| --- | --- | --- | --- | --- | --- | --- |
| <a id="m1-o1---live-linear-validation-environment-available"></a>M1-O1 | Done | Live Linear validation environment available | A human-prepared execution environment for the repository with the repo-local `.venv` available, `linear-client` installed in that environment, and the required Linear credential environment variables exposed to the same execution session that will run the release-gate spike | [M1-D1](#m1-d1---refresh-freshness-validation-spike) | Confirm the repo-local Python environment can import `linear_client` and that the same session can authenticate successfully before starting the spike | [docs/design/0-top-level-design.md](design/0-top-level-design.md#11-linear-dependency-boundary), [docs/design/linear-client-v1.0.0.md](design/linear-client-v1.0.0.md#authentication) |

### 3.2 Design Tickets

| # | Status | Ticket | Deliverable | Dependencies | Reviewers | Source |
| --- | --- | --- | --- | --- | --- | --- |
| <a id="m1-d1---refresh-freshness-validation-spike"></a>M1-D1 | Done | Refresh freshness validation spike | A short repository artifact that records whether issue-level `updated_at` is sufficient for the v1 persisted snapshot contract and, if not, the minimum amendment shape plus the need for a follow-on plan/design update before `refresh` work proceeds | [M1-O1](#m1-o1---live-linear-validation-environment-available) | Independent Stage 2 review session | [OQ-1](adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior) |
| <a id="m1-d3---refresh-composite-freshness-contract-amendment"></a>M1-D3 | Done | Refresh composite freshness contract amendment | A governing design amendment that replaces the single issue-level `updated_at` refresh assumption with the v1 per-ticket composite freshness contract required after [M1-D1](#m1-d1---refresh-freshness-validation-spike), including the exact comment-change signal to support comment creation and comment edits, the mandatory first-release relation freshness contract needed to keep graph state correct, the required local freshness metadata/comparison contract, and the explicit narrowing of attachment freshness out of the v1 incremental-refresh correctness contract into future work | [M1-D1](#m1-d1---refresh-freshness-validation-spike) | Independent Stage 2 review session | [docs/design/refresh-freshness-validation.md](design/refresh-freshness-validation.md), [docs/design/0-top-level-design.md](design/0-top-level-design.md#62-refresh-flow), [OQ-1](adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior), [FW-2](future-work.md#fw-2-attachment-content-handling) |
| <a id="m1-d2---linear-domain-coverage-audit-and-adapter-boundary"></a>M1-D2 | Done | Linear domain-coverage audit and adapter boundary | A repository artifact that enumerates the v1 Linear operations required by traversal, fetch, and the amended refresh contract, records whether the `linear-client` domain layer already covers each one, and defines any narrow `linear.gql.*` fallback boundary that implementation tickets may use | [M1-D3](#m1-d3---refresh-composite-freshness-contract-amendment) | Independent Stage 2 review session | [docs/adr.md](adr.md#31-foundation), [docs/design/0-top-level-design.md](design/0-top-level-design.md#11-linear-dependency-boundary), [docs/design/linear-client-v1.0.0.md](design/linear-client-v1.0.0.md) |

### 3.3 Implementation Tickets

| # | Status | Ticket | Description | Dependencies | Tests | Source |
| --- | --- | --- | --- | --- | --- | --- |
| <a id="m1-1---project-scaffold-and-public-runtime-contracts"></a>M1-1 | Done | Project scaffold and public runtime contracts | Create the initial Python package layout, configuration surface, public async entry points, shared result/error models, reusable fake-client test harness, and the documented developer command set the rest of the plan will rely on | [M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) | Unit tests for configuration parsing, result/error contracts, adapter/fake-client contracts, and package import boundaries | [docs/adr.md](adr.md#31-foundation), [docs/design/0-top-level-design.md](design/0-top-level-design.md#1-library-api), [docs/design/linear-client-v1.0.0.md](design/linear-client-v1.0.0.md), [README.md](../README.md) |
| <a id="m1-2---manifest-lock-and-rendering-primitives"></a>M1-2 | Done | Manifest, lock, and rendering primitives | Implement the manifest schema, deterministic YAML/Markdown rendering helpers, atomic per-file writes, lock metadata handling, and post-write verification utilities for later flows to reuse | [M1-1](#m1-1---project-scaffold-and-public-runtime-contracts) | Round-trip tests for manifest and ticket serialization, lock acquisition/preemption tests, and verification-failure tests | [docs/adr.md](adr.md#2-persistence-format), [docs/design/0-top-level-design.md](design/0-top-level-design.md#21-context-directory-contents), [docs/design/0-top-level-design.md](design/0-top-level-design.md#22-ticket-file-rendering), [ADR-R2a](planning/26.03.15%20-%20ADR%20review.md#adr-r2a-done-stale-lock-recovery-and-lock-metadata) |

### 3.4 Detailed Ticket Notes

#### M1-O1 - Live Linear validation environment available

- This prerequisite exists so the repository can perform the live
  [OQ-1](adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior)
  spike without depending on future scaffold work to invent a launcher or
  bootstrap story first.
- The human-provided prerequisite is operational, not product scope. Completing
  it makes the live spike runnable but does not itself answer
  [OQ-1](adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior).
- If the repository later standardizes a launcher or env-loading convention in
  [M1-1](#m1-1---project-scaffold-and-public-runtime-contracts), that later
  workflow should replace this ad hoc prerequisite for routine execution, but
  [M1-O1](#m1-o1---live-linear-validation-environment-available) is still the
  explicit precondition for the first live validation pass.

#### M1-D1 - Refresh freshness validation spike

- Record the outcome in a durable repository artifact rather than in chat-only
  notes so later sessions can decide whether `refresh` is still on-plan.
- Do not start the spike until
  [M1-O1](#m1-o1---live-linear-validation-environment-available) is complete in
  the same execution session, so the ticket does not rely on undocumented
  bootstrap assumptions about `linear-client` installation or credential
  exposure.
- If the issue-level `updated_at` contract fails for any v1-persisted field,
  stop, record the evidence and minimum amendment shape, and route that change
  through
  [M1-D3](#m1-d3---refresh-composite-freshness-contract-amendment) before
  [M3-1](#m3-1---incremental-refresh-and-quarantined-root-recovery) begins.

#### M1-D3 - Refresh composite freshness contract amendment

- Rewrite the governing refresh design in
  [docs/design/0-top-level-design.md](design/0-top-level-design.md#62-refresh-flow)
  so `refresh` no longer relies on issue-level `updated_at` as the sole
  freshness cursor.
- Decide and document whether
  [docs/adr.md](adr.md#52-refresh-incremental-whole-snapshot-update) section
  6.1 should also be rewritten as part of
  [M1-D3](#m1-d3---refresh-composite-freshness-contract-amendment), or whether
  the existing
  [OQ-1](adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior)
  annotation plus the top-level design rewrite is sufficient. Do not leave the
  ADR-update scope implicit.
- Define the minimum v1 composite freshness contract needed to detect comment
  creation and comment edits before a ticket is treated as fresh.
- Define the first-release relation freshness contract explicitly. Because
  relation changes affect graph construction and tracked-ticket reachability,
  the amendment must require `refresh` to detect relation changes and must not
  defer relation freshness out of v1 scope.
- Treat empirical relation probing as a recommended input to that design. If
  the amendment owner does not run additional live relation probes, the design
  should say so explicitly and still choose a conservative
  relation-freshness mechanism that keeps graph state correct.
- Narrow attachment freshness out of the first-release incremental-refresh
  correctness contract. If attachment metadata remains persisted in ticket
  files, the amendment should say explicitly that v1 selective refresh does not
  promise to detect attachment-only drift, and it should route richer
  attachment freshness handling to
  [FW-2](future-work.md#fw-2-attachment-content-handling) or a direct
  successor item.
- Record the exact remote data requirements that
  [M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) must
  audit so the adapter-boundary ticket can settle the final Linear operation
  set against the amended contract rather than the invalidated one.

#### M1-D2 - Linear domain-coverage audit and adapter boundary

- Audit the exact v1 read operations needed for traversal, relation discovery,
  ticket fetch, and the amended refresh freshness checks before implementation
  tickets widen the `linear-client` adapter by accident.
- Call out the refresh-operation path explicitly, especially the mandatory
  relation-freshness mechanism and any remaining batched issue/comment
  freshness queries. If the `linear-client` domain layer does not already
  expose one of those operations, record the expected `linear.gql.*` fallback
  shape inside the narrow adapter boundary so later tickets do not rediscover
  it ad hoc.
- Evaluate whether the accepted metadata-only comment freshness path remains
  operationally cheap enough for the default `refresh` contract. If the
  available Linear surface would make `comments_signature` materially more
  expensive than intended, record that explicitly as an adapter/design risk
  instead of silently weakening the default correctness contract. A degraded
  append-only or "new comments only" fast mode may be proposed as a follow-on
  option, but it must not replace the default first-release refresh semantics
  without an explicit accepted plan/design change.
- Confirm whether comment-level `updated_at` advances on comment edits in the
  available Linear surface. If that assumption cannot be confirmed, record the
  gap explicitly and define the fallback remote input or follow-on design work
  needed for `comments_signature` before
  [M3-1](#m3-1---incremental-refresh-and-quarantined-root-recovery) begins.
- Record any newly discovered missing domain capabilities in an authoritative
  repository artifact so maintainers have a durable upstream follow-up target.
- This dependency chain is intentional. The plan prefers one coherent audit
  artifact against the settled refresh contract over partial-completion
  semantics inside a single named ticket, and
  [M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) is
  expected to remain a short-duration design item once
  [M1-D3](#m1-d3---refresh-composite-freshness-contract-amendment) is settled.

#### M1-1 - Project scaffold and public runtime contracts

- The repository currently has design docs but no code scaffold, package
  metadata, or declared validation commands. This ticket should define that
  baseline explicitly instead of leaving later tickets to infer it.
- Keep the `linear-client` dependency behind the narrow adapter boundary
  defined by [M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary)
  so later tickets can fall back to its GraphQL layer only when that design
  artifact says the domain layer is insufficient.
- Define the per-process concurrency configuration surface described in
  [docs/adr.md](adr.md#31-foundation), including the semaphore limit that
  later fetch-heavy tickets must honor.
- Establish the reusable fake-client or fixture-builder contract that later
  integration tests extend instead of inventing one-off mocks per ticket.

#### M1-2 - Manifest, lock, and rendering primitives

- Shared persistence logic should live below the flow-specific orchestration
  layer so `sync`, `refresh`, `add`, `remove-root`, and `diff` can reuse the
  same normalization and verification rules.
- Keep the v1 deferral to
  [FW-3](future-work.md#fw-3-whole-snapshot-atomic-commit)
  intact: individual file writes should be atomic, but the milestone should not
  try to invent whole-directory staging semantics.

### 3.5 Exit Criteria

1. The repository has a runnable package scaffold and documented validation
   command set.
2. The repository has an explicit Linear adapter-boundary artifact that
   records required domain operations and any approved GraphQL fallbacks before
   traversal or refresh work begins.
3. Manifest, lock, and ticket-render helpers exist with deterministic
   round-trip coverage.
4. The `OQ-1` outcome is recorded in-repo and any blocking refresh-contract
   amendment is owned by a named design artifact before incremental refresh
   work starts.

---

## 4. Milestone 2 - Full Snapshot Materialization

**Goal:** make `sync` produce a deterministic whole-snapshot context directory
from one or more roots using the agreed v1 traversal and persistence contracts.

### 4.1 Design Tickets

No additional milestone-specific design tickets are planned once
[M1-D3](#m1-d3---refresh-composite-freshness-contract-amendment) settles the
accepted refresh contract. Milestone 2 should implement the already-adopted
ADR/design behavior rather than reopen it.

### 4.2 Implementation Tickets

| # | Status | Ticket | Description | Dependencies | Tests | Source |
| --- | --- | --- | --- | --- | --- | --- |
| <a id="m2-1---reachable-graph-builder-and-tiered-per-root-traversal"></a>M2-1 | Done | Reachable graph builder and tiered per-root traversal | Build the traversal engine that tracks one bounded reachable set per root, enforces per-root ticket caps, prioritizes structural tiers ahead of informational tiers, and unions the per-root results into one snapshot graph | [M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary), [M1-1](#m1-1---project-scaffold-and-public-runtime-contracts) | Unit tests for per-root caps, tier priority, shortest-depth resolution, cycle safety, and multi-root overlap | [docs/adr.md](adr.md#11-dimensions), [docs/adr.md](adr.md#13-traversal-order-and-ticket-cap), [docs/adr.md](adr.md#14-root-vs-derived-tickets), [ADR-R3](planning/26.03.15%20-%20ADR%20review.md#adr-r3-done-pure-breadth-first-traversal-cutoffs) |
| <a id="m2-2---ticket-fetch-normalization-and-render-pipeline"></a>M2-2 | Done | Ticket fetch normalization and render pipeline | Normalize fetched ticket data into the persisted manifest/ticket shape, execute bounded concurrent fetches through the shared adapter, preserve alias history on issue-key changes, render threaded comments deterministically, and verify generated output before it is accepted | [M1-2](#m1-2---manifest-lock-and-rendering-primitives), [M2-1](#m2-1---reachable-graph-builder-and-tiered-per-root-traversal) | Serializer and parser tests for alias retention, issue-key rename behavior, comment-thread ordering, concurrency-limit behavior, and verification mismatch handling | [docs/adr.md](adr.md#2-persistence-format), [docs/adr.md](adr.md#31-foundation), [docs/design/0-top-level-design.md](design/0-top-level-design.md#22-ticket-file-rendering), [docs/design/0-top-level-design.md](design/0-top-level-design.md#7-risks-and-mitigations-tool-specific) |
| <a id="m2-3---full-snapshot-sync-flow"></a>M2-3 | Done | Full-snapshot `sync` flow | Implement the initial/rooted whole-snapshot rebuild path, including workspace validation, manifest bootstrap, all-root traversal, reachable-ticket rewrite, and derived-ticket pruning | [M2-1](#m2-1---reachable-graph-builder-and-tiered-per-root-traversal), [M2-2](#m2-2---ticket-fetch-normalization-and-render-pipeline) | Integration tests for initial sync, repeated no-op sync, workspace mismatch rejection, and derived-ticket pruning | [docs/adr.md](adr.md#51-sync-full-snapshot-rebuild), [docs/design/0-top-level-design.md](design/0-top-level-design.md#61-sync-flow), [docs/design/0-top-level-design.md](design/0-top-level-design.md#4-error-handling) |

### 4.3 Detailed Ticket Notes

#### M2-1 - Reachable graph builder and tiered per-root traversal

- Implement the per-root cap exactly as described in
  [docs/adr.md](adr.md#13-traversal-order-and-ticket-cap); do not collapse
  back to one global ticket cap during implementation.
- The first release should keep `ticket_ref` discovery limited to URLs found in
  fetched Linear content. Repository scanning stays out of scope.

#### M2-2 - Ticket fetch normalization and render pipeline

- Preserve current human-readable issue-key filenames and manifest-based alias
  resolution as documented in
  [docs/adr.md](adr.md#2-persistence-format).
- Honor the per-process semaphore limit from
  [M1-1](#m1-1---project-scaffold-and-public-runtime-contracts) instead of
  allowing unbounded ticket-fetch fan-out inside one invocation.
- Keep attachment handling metadata-only and richer ticket-history capture
  deferred to
  [FW-2](future-work.md#fw-2-attachment-content-handling) and
  [FW-5](future-work.md#fw-5-ticket-history-and-sectioned-ticket-artifacts).

#### M2-3 - Full-snapshot `sync` flow

- `sync` should rewrite all reachable ticket files regardless of local
  freshness markers; incremental behavior belongs to
  [M3-1](#m3-1---incremental-refresh-and-quarantined-root-recovery).
- The writer lock should stay owned across manifest bootstrap, traversal,
  writes, and pruning so the context directory never has two active writers.

### 4.4 Exit Criteria

1. `sync` can materialize a deterministic context directory from a new or
   existing root set.
2. Repeated `sync` runs without upstream changes avoid semantic drift and keep
   file layout stable.
3. Alias handling, threaded comment rendering, and derived-ticket pruning are
   covered by automated tests.

---

## 5. Milestone 3 - Incremental Maintenance and Drift Inspection

**Goal:** add the maintenance flows that let callers evolve and inspect an
existing snapshot without always paying for a full rebuild.

### 5.1 Operational Prerequisites

| # | Status | Item | Requirement | Unblocks | Verification | Source |
| --- | --- | --- | --- | --- | --- | --- |
| <a id="m3-o1---comments-signature-input-settlement"></a>M3-O1 | Done | `comments_signature` input settlement | Confirm whether the Linear GraphQL API exposes comment-level `updatedAt` and whether it advances on comment edits. If confirmed, record the probe evidence as the accepted `comments_signature` input. If not, draft and accept a design amendment naming the replacement input (for example, a body-digest or `createdAt`-only fallback with documented limitations). | [M3-1](#m3-1---incremental-refresh-and-quarantined-root-recovery) | Repository artifact records either probe-backed acceptance of `comments_signature` canonical input or an accepted design amendment naming the replacement | [M1-D3](#m1-d3---refresh-composite-freshness-contract-amendment), [M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary), [M1-D2-R1](execution/M1-D2-review.md) |

### 5.2 Design Tickets

No new milestone-specific design tickets are planned here, but this milestone
remains explicitly gated on the resolved Milestone 1 refresh-design chain:
[M1-D1](#m1-d1---refresh-freshness-validation-spike) for the release-gate
evidence, [M1-D3](#m1-d3---refresh-composite-freshness-contract-amendment) for
the accepted replacement contract, and
[M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) for the
matching adapter audit. Milestone 3 should implement that adopted contract
rather than reopen the refresh design during implementation.

### 5.3 Implementation Tickets

| # | Status | Ticket | Description | Dependencies | Tests | Source |
| --- | --- | --- | --- | --- | --- | --- |
| <a id="m3-1---incremental-refresh-and-quarantined-root-recovery"></a>M3-1 | Done | Incremental `refresh` and quarantined-root recovery | Recompute reachability from active roots, batch-check freshness, re-fetch only stale or newly discovered tickets, quarantine or remove unavailable roots per policy, and recover quarantined roots when they become visible again | [M3-O1](#m3-o1---comments-signature-input-settlement), [M1-D3](#m1-d3---refresh-composite-freshness-contract-amendment), [M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary), [M2-2](#m2-2---ticket-fetch-normalization-and-render-pipeline), [M2-3](#m2-3---full-snapshot-sync-flow) | Integration tests for stale-vs-fresh refresh, unchanged-upstream no-op refresh/no rewrite, root quarantine, root reactivation, explicit remove policy, and changed-ticket selective rewrite behavior | [docs/adr.md](adr.md#52-refresh-incremental-whole-snapshot-update), [docs/adr.md](adr.md#61-snapshot-consistency-contract), [docs/design/0-top-level-design.md](design/0-top-level-design.md#62-refresh-flow), [ADR-R4](planning/26.03.15%20-%20ADR%20review.md#adr-r4-done-terminal-root-fragility) |
| <a id="m3-2---add-and-remove-root-whole-snapshot-flows"></a>M3-2 | Done | `add` and `remove-root` whole-snapshot flows | Implement root-set mutation through alias-aware ticket resolution, workspace checks, manifest updates, and reuse of the whole-snapshot refresh behavior under the same writer lock | [M3-1](#m3-1---incremental-refresh-and-quarantined-root-recovery) | Integration tests for adding by issue key and URL, overlapping-root refresh behavior, and failing `remove-root` for non-roots | [docs/design/0-top-level-design.md](design/0-top-level-design.md#63-add-flow), [docs/design/0-top-level-design.md](design/0-top-level-design.md#65-remove-root-flow), [docs/adr.md](adr.md#14-root-vs-derived-tickets) |
| <a id="m3-3---diff-mode-and-lock-aware-drift-reporting"></a>M3-3 | Done | `diff` mode and lock-aware drift reporting | Implement the non-mutating drift inspection path, including tracked-ticket comparison, `missing_remotely` classification, changed-field reporting, and refusal to run when a non-stale writer lock exists | [M2-2](#m2-2---ticket-fetch-normalization-and-render-pipeline), [M2-3](#m2-3---full-snapshot-sync-flow) | Integration tests for lock refusal, stale-lock observation without mutation, changed-field reporting, and unavailable-ticket classification | [docs/adr.md](adr.md#53-diff-non-mutating-drift-inspection), [docs/design/0-top-level-design.md](design/0-top-level-design.md#64-diff-flow), [docs/design/0-top-level-design.md](design/0-top-level-design.md#4-error-handling) |

### 5.4 Detailed Ticket Notes

#### M3-O1 - `comments_signature` input settlement

- This gate exists because
  [M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) confirmed
  that the installed `linear-client` comment surface does not expose the fields
  required by the
  [M1-D3](#m1-d3---refresh-composite-freshness-contract-amendment)
  `comments_signature` contract (comment `updatedAt`, parent/root topology,
  thread `resolved`, deletion signal), but did not settle a fallback input or
  confirm availability through the raw Linear GraphQL API.
- The two resolution paths are: (a) probe the raw Linear GraphQL `Comment` type
  for `updatedAt` and confirm it advances on comment edits — if so, record the
  probe evidence and accept the existing canonical input; or (b) if the field is
  unavailable or does not advance on edits, draft and accept a design amendment
  naming the replacement input (for example, a body-content digest,
  `createdAt`-only digest with documented staleness limitations, or another
  composite).
- The deliverable is a repository artifact recording the accepted decision, not
  implementation code. The outcome feeds directly into
  [M3-1](#m3-1---incremental-refresh-and-quarantined-root-recovery).
- Traced from review finding
  [M1-D2-R1](execution/M1-D2-review.md) (Medium, Fix now).
- Note: `linear-client` v1.1.0 now exposes per-issue comment metadata at the
  domain layer (`Comment.updated_at`, `.resolved_at`, `.parent`, `.children`);
  see [CR-26.04.07](planning/change-requests/CR-26.04.07.md). The batched
  refresh-metadata path still requires raw-GQL.

#### M3-1 - Incremental `refresh` and quarantined-root recovery

- Implement the refresh-contract defined by
  [M1-D3](#m1-d3---refresh-composite-freshness-contract-amendment) exactly. Do
  not improvise a silent workaround or quietly widen the accepted contract
  during implementation.
- Use the adapter contract from
  [M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) for the
  required composite freshness query path, especially the mandatory
  relation-freshness mechanism, rather than widening the Linear boundary during
  implementation.
- Do not begin until
  [M3-O1](#m3-o1---comments-signature-input-settlement) is complete. The
  `comments_signature` input must be settled by a repository artifact before
  implementation, not decided ad hoc during implementation.
- Keep the accepted v1 attachment-freshness narrowing intact. Attachment-only
  drift does not become first-release refresh scope unless a later accepted
  plan amendment changes that contract.
- Keep the default missing-root policy as `quarantine`; destructive removal
  remains opt-in.

#### M3-2 - `add` and `remove-root` whole-snapshot flows

- Root-set mutation should remain a whole-snapshot operation, not a root-local
  partial rebuild, so overlapping root graphs do not produce mixed-time local
  state.
- Reuse alias-based local resolution before any remote fetch when possible, but
  keep the fetched ticket UUID authoritative once resolution succeeds.

#### M3-3 - `diff` mode and lock-aware drift reporting

- `diff` must never clear, preempt, or create the writer lock record.
- User-facing output should explain why lock refusal is intentional, not merely
  report that a lock file exists.

### 5.5 Exit Criteria

1. `refresh` can update existing snapshots incrementally without weakening the
   ADR's freshness or missing-root semantics.
2. `add` and `remove-root` reuse whole-snapshot behavior correctly for
   overlapping root graphs.
3. `diff` reports drift without mutating files, manifest state, or lock state.

---

## 6. Milestone 4 - CLI and Release Readiness

**Goal:** make the tool usable by human operators and automation with clear
commands, separately reviewed CLI and library interfaces, durable docs, and
validation coverage that matches the repository's documented contracts.

### 6.1 Review Tickets

| # | Status | Ticket | Deliverable | Dependencies | Reviewers | Source |
| --- | --- | --- | --- | --- | --- | --- |
| <a id="m4-r1---cli-interface-review"></a>M4-R1 | Done | CLI interface review | A durable repository review artifact that evaluates the human-facing CLI command surface produced by this plan, including command semantics, overlap, output ergonomics, operator comprehension, and consistency between CLI behavior and user-facing docs. The deliverable must distinguish documentation-only clarifications from follow-on design/implementation work and must explicitly name any recommended new plan items or amendments. | [M4-2](#m4-2---operational-logging-validation-hardening-and-user-docs) | Independent Stage 2 review session | [docs/design/0-top-level-design.md](design/0-top-level-design.md#2-cli-interface), [README.md](../README.md), [docs/execution/M4-1-review.md](execution/M4-1-review.md) |
| <a id="m4-r2---api-interface-review"></a>M4-R2 | Done | API interface review | A durable repository review artifact that evaluates the public `ContextSync` library API after [M4-R1](#m4-r1---cli-interface-review) settles the command-surface semantics that may shape the library contract, including parameter naming, method boundaries, result/error ergonomics, exception taxonomy, docstring clarity, and terminology alignment between library, CLI, and user-facing docs. The deliverable must distinguish documentation-only clarifications from follow-on design/implementation work and must explicitly name any recommended new plan items or amendments. | [M4-R1](#m4-r1---cli-interface-review) | Independent Stage 2 review session | [docs/design/0-top-level-design.md](design/0-top-level-design.md#1-library-api), [README.md](../README.md), [docs/execution/M4-1-review.md](execution/M4-1-review.md) |

### 6.2 Implementation Tickets

| # | Status | Ticket | Description | Dependencies | Tests | Source |
| --- | --- | --- | --- | --- | --- | --- |
| <a id="m4-1---cli-surface-and-command-output-contracts"></a>M4-1 | Done | CLI surface and command output contracts | Add the thin CLI wrapper over the async library, expose the documented commands and options, and define human-readable plus machine-readable output behavior for success and failure cases | [M2-3](#m2-3---full-snapshot-sync-flow), [M3-1](#m3-1---incremental-refresh-and-quarantined-root-recovery), [M3-2](#m3-2---add-and-remove-root-whole-snapshot-flows), [M3-3](#m3-3---diff-mode-and-lock-aware-drift-reporting) | CLI tests for command parsing, JSON output, lock-error text, and missing-root-policy selection | [docs/design/0-top-level-design.md](design/0-top-level-design.md#2-cli-interface), [docs/design/0-top-level-design.md](design/0-top-level-design.md#4-error-handling) |
| <a id="m4-2---operational-logging-validation-hardening-and-user-docs"></a>M4-2 | Done | Operational logging, validation hardening, and user docs | Add the INFO/DEBUG logging contract, fixture-backed validation hardening for the shipped pre-release handler/runtime surface, onboarding and usage docs that accurately qualify current behavior, and the sample configuration artifact needed to satisfy the repository's documentation/security conventions. Supported public-entrypoint integration proof and the durable manual smoke recipe are deferred to [M5-2](#m5-2---supported-public-runtime-validation-and-smoke-path). | [M4-1](#m4-1---cli-surface-and-command-output-contracts) | Fixture-backed tests covering all major modes through the existing handler/fake path. Supported public-entrypoint integration validation and the durable manual smoke recipe are deferred to [M5-2](#m5-2---supported-public-runtime-validation-and-smoke-path). | [docs/adr.md](adr.md#61-snapshot-consistency-contract), [README.md](../README.md), [docs/policies/common/coding-guidelines.md](policies/common/coding-guidelines.md) |
| <a id="m4-3---rename-root-ticket-id-to-key"></a>M4-3 | Done | API terminology cleanup | Rename `root_ticket_id` to `key` on `ContextSync.sync()`, unify `ticket_ref` to `key` on `add()` and `remove_root()`, rename `SyncError.ticket_id` to `ticket_key`, rename `DiffEntry.ticket_id` to `ticket_key`, reword implementation-oriented docstring summary lines on `sync()` and `refresh()`, and fix banned-term usage in the `context_dir` property docstring. Update the CLI positional argument help text, tests, and user-facing documentation to match. | [M4-R2](#m4-r2---api-interface-review) | Update existing tests that reference the old parameter and field names | [README.md](../README.md), [docs/execution/M4-R2.md](execution/M4-R2.md) |

### 6.3 Detailed Ticket Notes

#### M4-1 - CLI surface and command output contracts

- Keep the CLI thin. Flow logic should remain in the async library layer so the
  repository does not fork behavior between human and programmatic entry
  points.
- Command output should make the difference between active-lock refusal,
  demonstrably stale-lock preemption, and root quarantine visible without
  requiring debug logging.

#### M4-R1 - CLI interface review

- Review the public CLI/operator surface produced by this plan, not the library
  API. This top-level review is separate from the Phase B review of
  [M4-1](#m4-1---cli-surface-and-command-output-contracts) and should focus on
  command semantics, output ergonomics, operator comprehension, and whether the
  CLI plus docs tell one coherent story to users.
- The current five-command CLI surface (`sync`, `refresh`, `add`,
  `remove-root`, `diff`) has significant semantic overlap. Specifically,
  `sync TICKET` on an existing snapshot and `add TICKET` produce the same
  observable result: both add the ticket as a root and rebuild the snapshot
  from all active roots. The differences are:
  - `sync` allows per-call `--max-tickets-per-root` and `--depth-*` overrides
    that get persisted into the manifest; `add` uses the manifest's existing
    traversal configuration.
  - `sync` fetches all reachable tickets before comparing locally (full
    rebuild); `add` delegates to the incremental refresh pipeline which
    batch-checks freshness and only re-fetches stale or newly discovered
    tickets.
  - `sync` is the only path that initializes a new context directory; `add`
    on an empty directory also initializes, but was designed as an
    "add to existing" operation.
- A human operator who wants to "start tracking a new ticket" has no obvious
  reason to prefer one command over the other. The distinction between "full
  rebuild" and "incremental add" is an implementation detail, not a meaningful
  user intent.
- Evaluate whether a unified command (for example `sync` that is always
  additive and always incremental when possible) or a different factoring
  (for example `sync --full` for explicit full rebuild, `sync` for
  incremental by default) would reduce operator confusion while preserving
  the efficiency benefits of incremental refresh.
- Also evaluate `remove-root` vs a potential `sync --remove TICKET` or
  `unsync TICKET` surface.
- If the CLI review concludes that command-surface changes would materially
  affect the public library contract, carry those implications into
  [M4-R2](#m4-r2---api-interface-review) rather than treating
  [M4-R1](#m4-r1---cli-interface-review) as the API review too.
- Regardless of whether the command surface changes, the deliverable must
  include expanded user-facing documentation (in
  [README.md](../README.md) and/or a dedicated operator guide) that explains
  when to use each command, what each interface does under the hood, and why
  the distinctions exist, or, if the surface is simplified, documents the new
  simpler model.
- If the review identifies new work not already tracked in the active plan, add
  it as one or more follow-on tickets through a plan amendment rather than
  silently widening a `Done` ticket or leaving the recommendation only in the
  review artifact.
- If the review proposes changes to the command surface, or identifies
  downstream API implications that need follow-on work, those changes must go
  through a plan amendment before implementation.

#### M4-R2 - API interface review

- Review the public `ContextSync` library API after
  [M4-R1](#m4-r1---cli-interface-review) settles any command-semantics changes
  that may need to propagate into library naming, factoring, or behavior.
- The review should evaluate parameter naming, result/error ergonomics,
  exception naming, method boundaries, docstring clarity, and library/CLI term
  alignment for whether they communicate the accepted contract clearly to
  callers.
- [M4-3](#m4-3---rename-root-ticket-id-to-key) is an already-selected
  follow-on API naming cleanup candidate. [M4-R2](#m4-r2---api-interface-review)
  should confirm whether that ticket is still the right shape or whether a
  broader or different API-only follow-on change set should replace it.
- If the review identifies new work not already tracked in the active plan, add
  it as one or more follow-on tickets through a plan amendment rather than
  silently widening a `Done` ticket or leaving the recommendation only in the
  review artifact.
- If the review proposes changes to the public library contract, those changes
  must go through a plan amendment before implementation.

#### M4-2 - Operational logging, validation hardening, and user docs

- The first implementation pass should add the sample configuration artifact
  that enumerates required environment variables without secrets, because the
  CLI path depends on credentialed `linear-client` startup.
- Keep validation focused on the declared repository command set from
  [M1-1](#m1-1---project-scaffold-and-public-runtime-contracts) so later ticket
  work has one canonical lint/format/test surface.
- This ticket closes with honest pre-release documentation plus
  fixture-backed/component validation for the existing handler/runtime surface.
  Supported public-entrypoint integration proof and the durable manual CLI
  smoke recipe are deferred to
  [M5-2](#m5-2---supported-public-runtime-validation-and-smoke-path).

#### M4-3 - API terminology cleanup

- The `sync()` method currently accepts a `root_ticket_id` parameter, but the
  value is a human-facing issue key (e.g. `TEAM-42`) or a Linear URL — not an
  internal UUID. The `_id` suffix is misleading, and `root_ticket_` is
  unnecessarily verbose given the method context already implies the root.
- Rename to `key` across the public API, CLI positional argument, docstrings,
  tests, and user-facing documentation.
- [M4-R2](execution/M4-R2.md#m4-3-assessment) concluded that this ticket
  should be broadened to cover the full `_id` naming problem:
  - `sync(root_ticket_id=...)` → `sync(key=...)`
  - `add(ticket_ref=...)` → `add(key=...)` (or internal only, per
    [FW-10](future-work.md#fw-10-cli-simplification-amendment))
  - `remove_root(ticket_ref=...)` → unified `key` parameter name
  - `SyncError.ticket_id` → `SyncError.ticket_key`
  - `DiffEntry.ticket_id` → `DiffEntry.ticket_key`
- Documentation-only improvements identified by M4-R2 (docstring summary
  rewording, banned-term removal) can land alongside the rename.
- This is a breaking change to the library API. Acceptable at the current
  `0.x` version, but should land before `1.0.0`.

### 6.4 Exit Criteria

1. Human operators can run the documented CLI commands for `sync`, `refresh`,
   `add`, `remove-root`, and `diff`.
2. The CLI surface and the public library API each have a durable
   post-implementation review path that can feed explicit follow-on tickets
   when needed.
3. Logging and result output make operational failures diagnosable without
   exposing secrets.
4. The repository includes user-facing docs and validation coverage that match
   the implemented public behavior.

---

## 7. Milestone 4.1 - CLI and Library Simplification

**Goal:** simplify the public CLI from five commands to four, make `sync`'s
TICKET argument optional so that standalone `sync` provides a
full-rebuild-all-roots path without changing root membership, and align the
library method boundaries to match, as prescribed by the accepted
[M4-R1](execution/M4-R1.md) and [M4-R2](execution/M4-R2.md) review outcomes.

### 7.1 Implementation Tickets

| # | Status | Ticket | Description | Dependencies | Tests | Source |
| --- | --- | --- | --- | --- | --- | --- |
| <a id="m4.1-1---cli-and-library-simplification"></a>M4.1-1 | Done | CLI and library simplification | Remove the public `add` CLI action and fold its user intent into `sync`; make `sync`'s TICKET argument optional (standalone `sync` = full rebuild of all tracked roots, no root-membership change); rename the public CLI token `remove-root` to `remove`; use `TICKET` as the required positional for `remove` and the optional positional for `sync`; make `ContextSync.add()` internal (rename to `_add()` and remove from `__all__`); rename `ContextSync.remove_root()` to `ContextSync.remove()`; make `sync()`'s `key` parameter optional (`key: str | None = None`) with standalone semantics matching the CLI; adopt `add()`'s traversal-config preservation as the no-override default for `sync()` at both CLI and library levels; update help text for `sync` and `refresh` to use clearly distinct intent-oriented language; update README, user-facing docs, and all tests to reflect the four-command surface | [M4-3](#m4-3---rename-root-ticket-id-to-key), [M4-R1](#m4-r1---cli-interface-review), [M4-R2](#m4-r2---api-interface-review) | Parser tests confirming `add` and `remove-root` are rejected by the standard unknown-subcommand path; `sync` tests verifying traversal-config preservation when no overrides are supplied and override persistence when overrides are explicitly given; standalone `sync` test confirming full rebuild of all tracked roots with no root-membership change; `remove` tests confirming the rename works end-to-end; `__all__` test confirming `add` is not exported and `_add` is present; updated integration tests routing through the four-command surface; README/docs consistency check | [docs/future-work.md §FW-10](future-work.md#fw-10-cli-simplification-amendment), [docs/execution/M4-R1.md](execution/M4-R1.md), [docs/execution/M4-R2.md](execution/M4-R2.md) |
| <a id="m4.1-2---sync-path-consolidation-and-full-rebuild-standalone"></a>M4.1-2 | Done | Sync path consolidation and full-rebuild standalone | Consolidate `_add_under_lock`'s alias resolution, early URL slug validation, and quarantine-recovery logging into `_sync_under_lock`; delete `_add()` and `_add_under_lock()` entirely; remove the `"add"` lock/snapshot mode; rewrite ~30 test callsites to use `sync(key=...)`; implement full-rebuild semantics for standalone `sync` (no key) so it unconditionally re-fetches and rewrites all tracked tickets rather than delegating to the incremental `_refresh_under_lock` path | [M4.1-1](#m4.1-1---cli-and-library-simplification) | Tests confirming alias-based local resolution, early URL slug validation, and quarantine-recovery logging work through `sync(key=...)`; standalone `sync` test confirming unconditional full rebuild (not incremental); `"add"` lock/snapshot mode no longer appears in any runtime code path | [docs/execution/M4.1-1-review.md](execution/M4.1-1-review.md) ([M4.1-1-R1](execution/M4.1-1-review.md), [M4.1-1-R2](execution/M4.1-1-review.md)) |

### 7.2 Detailed Ticket Notes

#### M4.1-1 - CLI and library simplification

The six-use-case mapping below is the authoritative surface reference for
this ticket:

| # | Use case | CLI command | Notes |
| --- | --- | --- | --- |
| 1 | Add the first tracked root | `sync TICKET` | Bootstraps the snapshot; TICKET becomes the initial root |
| 2 | Add a new root to an existing snapshot | `sync TICKET` | Same command; idempotent if TICKET is already tracked |
| 3 | Lightweight incremental refresh | `refresh` | Re-fetches only nodes identified as new or modified since the last run |
| 4 | Full rebuild (nuke and rebuild) | `sync` | Rebuilds all tracked roots unconditionally; no root-membership change |
| 5 | Remove a root and prune orphaned nodes | `remove TICKET` | Stops tracking TICKET and removes nodes not reachable from any remaining root |
| 6 | Diff without writing to disk | `diff` | Read-only comparison between local snapshot and Linear |

Both `sync TICKET` and standalone `sync` currently rebuild the full root set
regardless of graph connectivity. Selective partition-aware rebuilding is
deferred to [FW-11](future-work.md#fw-11-partition-aware-sync-rebuild).

**CLI changes:**

- Remove `add` from the CLI parser; the standard unknown-subcommand error
  handles any attempt to invoke it.
- Rename `remove-root` to `remove`; the old token is handled the same way.
- `sync`'s TICKET argument is optional. When supplied, adds or reaffirms the
  root then fully rebuilds all tracked roots. When omitted, performs the same
  full rebuild with no root-membership change.
- `sync` help string: "Fully rebuild the snapshot from all tracked roots.
  With TICKET, add or reaffirm that root first."
- `refresh` help string: "Re-fetch the latest data for all tracked tickets."
  The two strings must use clearly distinct language: `sync` unconditionally
  rewrites all nodes regardless of existing data or timestamps; `refresh`
  updates only nodes identified as new or modified since the last run.
- `sync` remains the only root-expanding public command. The
  full-vs-incremental execution strategy remains internal per
  [M4-R1 §3a](execution/M4-R1.md).

**Library changes:**

- Make `ContextSync.add()` internal: rename to `_add()` and remove from
  `__all__`. The implementation may be retained as an internal helper behind
  `sync()`.
- Rename `ContextSync.remove_root()` to `ContextSync.remove()`.
- Make `sync()`'s `key` parameter optional (`key: str | None = None`). When
  `None`, performs a full rebuild of all currently tracked roots with no
  root-membership change.
- When `sync()` is called without explicit `max_tickets_per_root` or
  `dimensions` overrides, preserve the manifest's existing traversal
  configuration. When overrides are supplied, persist them as before. This
  adopts `add()`'s preservation semantics as the no-override default per
  [M4-R1](execution/M4-R1.md) and [M4-R1-R4](execution/M4-R1-review.md).
- Update the `SyncResult` docstring to remove any reference to `add()`.
- Docstring improvements from [M4-R2 §5](execution/M4-R2.md) should land
  alongside the method boundary changes.

**Documentation changes:**

- Update [README.md](../README.md) to reflect the four-command surface.
  Remove the interim "When to use each command" section (added for
  [M4-R1-R1](execution/M4-R1-review.md)) and replace with documentation of
  the simplified model.
- Update all user-facing command tables, exit-code tables, and examples to
  reflect the six use cases and the four-command surface.
- Ensure the docs surface is consistent before M5-2 or M6-1 proceeds.

#### M4.1-2 - Sync path consolidation and full-rebuild standalone

This ticket addresses two review findings from
[M4.1-1-review.md](execution/M4.1-1-review.md):

- [M4.1-1-R1](execution/M4.1-1-review.md): `_add()` / `_add_under_lock()` are
  dead code — never called from any public API path. Three behaviors in
  `_add_under_lock` (alias-based local resolution, early URL slug validation,
  quarantine-recovery logging) are tested but unreachable from `sync(key=...)`.
  Consolidate those behaviors into `_sync_under_lock`, delete the dead code,
  rewrite the ~30 test callsites to use `sync(key=...)`, and remove the `"add"`
  lock/snapshot mode from `LOCK_MODES` and `ManifestSnapshot.mode`.

- [M4.1-1-R2](execution/M4.1-1-review.md): Standalone `sync` (no key)
  delegates to `_refresh_under_lock`, which is the incremental pipeline. The
  plan and README describe standalone `sync` as a full unconditional rebuild.
  Implement `_standalone_sync_under_lock` using the same full-fetch strategy as
  `_sync_under_lock` so standalone `sync` is a genuine full rebuild, not
  functionally equivalent to `refresh`.

### 7.3 Exit Criteria

1. The public CLI surface is `sync [TICKET]`, `refresh`, `remove TICKET`, and
   `diff`. The old `add` and `remove-root` tokens are rejected by the
   standard unknown-subcommand error path.
2. Standalone `sync` (no TICKET) performs a full rebuild of all currently
   tracked roots without changing root membership.
3. The public library surface exposes `ContextSync.sync()` (with optional
   `key`), `ContextSync.refresh()`, `ContextSync.remove()`, and
   `ContextSync.diff()`. `add()` is no longer in `__all__`.
4. `sync()` preserves existing manifest traversal configuration when no
   overrides are supplied. Explicit overrides are persisted as before.
5. README and user-facing docs reflect the four-command surface, document all
   six use cases, and contain no references to the old `add` or `remove-root`
   surface.

---

## 8. Milestone 4.2 - Common-Policy Compliance

**Goal:** close the immediate common-policy compliance gaps so that M5 and later
milestones build on a conforming toolchain, type-checking, coverage, and
documentation baseline. This milestone addresses nine gaps identified by
[CR-26.03.24-policy-compliance](planning/change-requests/CR-26.03.24-policy-compliance.md).

### 8.1 Implementation Tickets

| # | Status | Ticket | Description | Dependencies | Tests | Source |
| --- | --- | --- | --- | --- | --- | --- |
| <a id="m4.2-1---quality-gate-entry-point-static-analysis-baseline-and-semantic-types"></a>M4.2-1 | Done | Quality gate entry point, static analysis baseline, and semantic types | Create `scripts/validate.sh` that runs `ruff check`, `ruff format --check`, `pyright`, and `pytest` in sequence, exiting non-zero on any failure. Add `pyright` to dev deps. Add `[tool.pyright]` config to `pyproject.toml`. Create `src/context_sync/py.typed` and add `[tool.setuptools.package-data]` entry. Create `src/context_sync/_types.py` with `NewType` aliases for the identified domain concepts (`IssueId`, `IssueKey`, `WorkspaceId`, `WorkspaceSlug`, `CommentId`, `AttachmentId`, `WriterId`; constrained-string or `NewType` aliases for RFC 3339 timestamps and similar). Adopt the new types across the source tree. Resolve all Pyright errors. | [M4.1-2](#m4.1-2---sync-path-consolidation-and-full-rebuild-standalone) | `validate.sh` exits 0 on clean tree; `py.typed` is included in built wheel; Pyright reports zero errors; `_types.py` defines `NewType` aliases for all identified domain concepts; no bare `str` remains for semantically distinct domain fields at public boundaries | [docs/policies/common/coding-guidelines.md](policies/common/coding-guidelines.md), [docs/policies/common/python/coding-guidelines.md](policies/common/python/coding-guidelines.md) |
| <a id="m4.2-2---coverage-tooling-agent-awareness-artifacts-and-interface-documentation"></a>M4.2-2 | Done | Coverage tooling, agent-awareness artifacts, and interface documentation | Add `coverage[toml]>=7,<8` and `pytest-cov>=5,<6` to dev deps. Add `[tool.coverage.run]` and `[tool.coverage.report]` config. Update `scripts/validate.sh` to include `--cov --cov-report=term-missing` flags. Create `examples/` directory with at least one runnable script exercising `ContextSync` via the fake gateway. Create `docs/design/dependency-map.md` with entry points, module summaries, workflow-to-code map, anti-patterns, and async ownership. Complete the missing docstring dimensions on all four `ContextSync` public methods and `LinearGateway` protocol methods. Update README to add `ripgrep` and `cloc` to system prerequisites and add an explicit symlink verification step. | [M4.2-1](#m4.2-1---quality-gate-entry-point-static-analysis-baseline-and-semantic-types) | `pytest --cov --cov-report=term-missing` produces branch coverage report; `validate.sh` includes coverage flags; example script runs without error; dependency map covers all public entry points; all `ContextSync` public methods document all ten required dimensions; `LinearGateway` protocol methods have complete parameter, output, and `Raises` documentation; README prerequisites list `ripgrep` and `cloc`; README includes symlink verification step | [docs/policies/common/python/agent-awareness.md](policies/common/python/agent-awareness.md), [docs/policies/common/coding-guidelines.md](policies/common/coding-guidelines.md), [docs/policies/common/README.md](policies/common/README.md) |

### 8.2 Detailed Ticket Notes

#### M4.2-1 - Quality gate entry point, static analysis baseline, and semantic types

- `scripts/validate.sh` is the canonical "validate everything" command per
  [coding-guidelines.md](policies/common/coding-guidelines.md). It must
  run all declared quality gates and exit non-zero on any failure.
- Pyright config should target the same Python version as the rest of the
  toolchain (3.13). Use `pythonVersion = "3.13"` and `typeCheckingMode = "standard"`
  as the starting baseline; tighten to `strict` only if zero errors is achievable
  without excessive `type: ignore` annotations.
- Resolving Pyright errors may require adding or tightening type annotations in
  some modules. This is expected and should be treated as part of the ticket scope.
- The `py.typed` marker is a zero-byte file at `src/context_sync/py.typed`. The
  `[tool.setuptools.package-data]` entry ensures it ships in the wheel.
- Create `src/context_sync/_types.py` as the dedicated module for reusable type
  aliases per
  [python/coding-guidelines.md §Semantic Types](policies/common/python/coding-guidelines.md).
  At minimum define `NewType` aliases for: `IssueId`, `IssueKey`, `WorkspaceId`,
  `WorkspaceSlug`, `CommentId`, `AttachmentId`, `WriterId`. For RFC 3339
  timestamps and other constrained strings, `Annotated[str, StringConstraints(...)]`
  or `NewType` aliases are both acceptable.
- Adopt the new types across the source tree, replacing bare `str` at public
  boundaries. The type migration touches every module that handles issue IDs,
  issue keys, workspace IDs, and similar domain concepts. This is a wide
  mechanical change — scope the initial `NewType` set to the minimum that closes
  the policy gap rather than attempting a maximal migration. If the migration
  surfaces Pyright errors that are actually logic bugs (e.g. passing an
  `IssueKey` where an `IssueId` is expected), treat those as valuable
  discoveries and fix them as part of this ticket.
- Introducing semantic types and the type checker in the same ticket ensures
  Pyright validates the new type boundaries from the start rather than leaving
  bare `str` to pass unchecked.
- Update `scripts/validate.sh` in lockstep with any future toolchain changes so
  the script remains the single source of truth for quality gates.

#### M4.2-2 - Coverage tooling, agent-awareness artifacts, and interface documentation

- Coverage config should enable branch coverage and source from `src/`, omitting
  `version.py` per
  [python/agent-awareness.md](policies/common/python/agent-awareness.md).
- Update `scripts/validate.sh` to invoke `pytest --cov --cov-report=term-missing`
  instead of bare `pytest`. This is the lockstep obligation from M4.2-1: when
  a new quality gate tool is added, the canonical script must be updated in the
  same ticket that introduces the tool.
- The `examples/` script must be runnable against the fake gateway since the real
  gateway is not yet available. Use the `_gateway_override` testing hook with a
  brief comment explaining that the example will switch to the real constructor
  once the gateway lands in M5.
- The dependency map should follow the minimum content requirements from
  [python/agent-awareness.md](policies/common/python/agent-awareness.md):
  main entry points, key internal modules, workflow-to-code map, anti-patterns,
  and async ownership. Keep to 1-2 pages. **Scope risk:** if the dependency map
  writing blocks the other deliverables, the ticket owner should land the
  independent deliverables (coverage tooling, `examples/`, README fixes) first
  rather than holding the entire ticket.
- Complete the missing docstring dimensions on all four `ContextSync` public
  methods (`sync`, `refresh`, `remove`, `diff`): add realistic examples,
  idempotency statements, mutability statements, and thread-safety statements.
  Complete `LinearGateway` protocol method documentation: add missing parameter
  type documentation and `Raises` sections across `get_workspace_identity`,
  `get_ticket_relations`, `get_refresh_issue_metadata`,
  `get_refresh_comment_metadata`, `get_refresh_relation_metadata`. Note that the
  `LinearGateway` protocol method documentation may need updating again when
  [M5-1](#m5-1---real-linear-gateway-and-runtime-wiring) implements the real
  gateway.
- The README already covers common-policy dependency, symlink setup, recovery,
  and common-layer reference. The three targeted additions are: (1) add `ripgrep`
  to the Prerequisites section, (2) promote `cloc` from Developer commands into
  the Prerequisites section, and (3) add an explicit symlink verification step.

### 8.3 Exit Criteria

1. `scripts/validate.sh` runs all quality gates (Ruff lint, Ruff format check,
   Pyright, pytest with coverage) and exits 0 on a clean tree.
2. Pyright reports zero errors across the source tree.
3. `py.typed` is present and included in the built wheel.
4. `_types.py` exists and defines `NewType` aliases for all identified domain
   concepts; no bare `str` remains for semantically distinct domain fields at
   public boundaries; Pyright validates the `NewType` boundaries with zero
   errors.
5. `pytest --cov --cov-report=term-missing` produces a branch coverage report.
6. `examples/` contains at least one runnable script that exercises the primary
   `ContextSync` workflow.
7. `docs/design/dependency-map.md` covers all minimum-content requirements.
8. All four `ContextSync` public methods document all ten required interface
   dimensions. `LinearGateway` protocol methods have complete parameter, output,
   and `Raises` documentation.
9. README Prerequisites section lists `ripgrep` and `cloc` as system
   prerequisites. README includes an explicit symlink verification step.

---

## 9. Milestone 5 - Supported Runtime Gateway

**Goal:** replace the current fake-gateway-only public runtime with a real
`linear-client`-backed execution path, keep the adapter boundary aligned with
the existing design artifacts, and validate the actual public CLI/library
entry points rather than only private testing hooks.

### 9.1 Implementation Tickets

| # | Status | Ticket | Description | Dependencies | Tests | Source |
| --- | --- | --- | --- | --- | --- | --- |
| <a id="m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110"></a>M5-D1 | Done | Linear domain-coverage audit and adapter boundary — v1.1.0 | Inspect the installed `linear-client` v1.1.0 surface and produce a new domain-coverage audit at `docs/design/linear-domain-coverage-audit-v1.1.0.md` with an authoritative coverage matrix, adapter-boundary decision, approved raw-GQL helper set, recorded missing upstream capabilities, and a type-mapping table for the gateway boundary. This ticket supersedes the M1-D2 v1.0.0 audit (`docs/design/linear-domain-coverage-audit-v1.0.0.md`) as the governing adapter-boundary reference for M5-1. | None | N/A (design artifact) | [docs/design/linear-domain-coverage-audit-v1.0.0.md](design/linear-domain-coverage-audit-v1.0.0.md), [CR-26.04.07](planning/change-requests/CR-26.04.07.md), [linear-client docs/pub/release-1.1.0.md](../../linear-client/docs/pub/release-1.1.0.md) |
| <a id="m5-d2---design-artifact-refresh-for-v110-workspace-model"></a>M5-D2 | Done | Design-artifact refresh for v1.1.0 workspace model | Retire `docs/design/linear-client-v1.0.0.md` (the local API reference summary is redundant now that the full library source is in the multi-root workspace). Update stale workspace-access and dependency-version references in `docs/adr.md` and `docs/design/0-top-level-design.md` to reflect the current workspace model. Update `docs/design/dependency-map.md` private-dependency pointers to reference the library's own documentation paths within the workspace. The design layer should read as a seamless representation of current state, not a patchwork of v1.0.0-era and v1.1.0-era content. | [M5-D1](#m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110) | N/A (design artifact) | [docs/design/linear-client-v1.0.0.md](design/linear-client-v1.0.0.md), [docs/adr.md](adr.md), [docs/design/0-top-level-design.md](design/0-top-level-design.md), [docs/design/dependency-map.md](design/dependency-map.md), [CR-26.04.07](planning/change-requests/CR-26.04.07.md) |
| <a id="m5-1---real-linear-gateway-and-runtime-wiring"></a>M5-1 | Done | Real Linear gateway and runtime wiring | Implement the concrete `RealLinearGateway` over the [M5-D1](#m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110) boundary, map all required ticket-bundle and refresh-metadata reads, and wire `ContextSync(linear=...)` plus CLI startup to create that gateway instead of failing with "No gateway available"; this ticket is the explicit defer target for [M4-2-R1](execution/M4-2-review.md) | [M5-D1](#m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110), [M3-O1](#m3-o1---comments-signature-input-settlement), [M4-1](#m4-1---cli-surface-and-command-output-contracts), [M4.1-1](#m4.1-1---cli-and-library-simplification), [M4.2-1](#m4.2-1---quality-gate-entry-point-static-analysis-baseline-and-semantic-types) | Automated tests for the real gateway implementation using maintained fake/fixture transport inputs at the adapter boundary, integration tests that route `sync` / `refresh` / `remove` / `diff` through that real gateway implementation without a live workspace, and bootstrap error-path coverage for missing auth or unavailable upstream services | [docs/design/linear-domain-coverage-audit-v1.1.0.md](design/linear-domain-coverage-audit-v1.1.0.md), [docs/execution/M4-1-review.md](execution/M4-1-review.md), [docs/execution/M4-2-review.md](execution/M4-2-review.md), [README.md](../README.md), [CR-26.04.07](planning/change-requests/CR-26.04.07.md) |
| <a id="m5-2---supported-public-runtime-validation-and-smoke-path"></a>M5-2 | Done | Supported public runtime validation and smoke path | Exercise the supported CLI and library entry points through `main()` or the installed console script, replace private-handler-only "end-to-end" claims with real public-surface coverage, and add a maintained smoke-validation recipe for one successful run plus one representative failure path; this ticket is the explicit defer target for [M4-2-R2](execution/M4-2-review.md) and [M4-2-R3](execution/M4-2-review.md) | [M5-1](#m5-1---real-linear-gateway-and-runtime-wiring), [M4-2](#m4-2---operational-logging-validation-hardening-and-user-docs), [M4.2-2](#m4.2-2---coverage-tooling-agent-awareness-artifacts-and-interface-documentation) | CLI integration tests through the real parser/dispatch path with maintained fake/fixture-backed runtime inputs, plus real-environment smoke validation in a credentialed Linear workspace or equivalent maintained live validation environment, and JSON/text failure-contract regression tests | [docs/execution/M4-1-review.md](execution/M4-1-review.md), [docs/execution/M4-2-review.md](execution/M4-2-review.md), [README.md](../README.md) |
| <a id="m5-3---cli-auth-mode-selection"></a>M5-3 | Done | CLI auth-mode selection | Add a `--auth-mode` CLI option so operators can select among the three `linear-client` auth modes (`oauth`, `client_credentials`, `api_key`). Pass the selected mode to `Linear(auth_mode=...)` in `_create_linear_client()`. The library API already accepts a pre-formed `Linear` instance, so no library-layer change is needed. Update the README and smoke recipe to cover at least two modes. | [M5-2](#m5-2---supported-public-runtime-validation-and-smoke-path) | CLI parser tests for `--auth-mode`, handler integration tests confirming the selected mode reaches the `Linear()` constructor, smoke recipe covering `api_key` and `client_credentials` | [docs/linear-client-issues.md](linear-client-issues.md#lc-2---no-environment-variable-control-for-auth_mode), [docs/execution/M5-2.md](execution/M5-2.md), direct human request |
| <a id="m5-4---adopt-linear-client-newtypes"></a>M5-4 | Todo | Adopt `linear-client` NewTypes and eliminate duplicate aliases | Replace duplicate `IssueId`, `IssueKey`, `CommentId`, and `AttachmentId` in `context_sync._types` with re-exports from `linear_client.types`. Keep `WriterId`, `Timestamp`, `WorkspaceId`, and `WorkspaceSlug` as context-sync-only types. Add `linear-client` as a declared dependency or `TYPE_CHECKING`-only import. Remove the `UpstreamIssueId` bridge import workaround in `_real_gateway.py`. | [M5-1](#m5-1---real-linear-gateway-and-runtime-wiring) | All existing tests pass with shared type identity; Pyright reports zero errors; no bridge imports or casts at the gateway layer | [docs/linear-client-issues.md](linear-client-issues.md#lc-6---newtype-identity-mismatch-across-the-boundary), [docs/execution/M5-1.md](execution/M5-1.md), direct human request |

### 9.2 Detailed Ticket Notes

#### M5-D1 - Linear domain-coverage audit and adapter boundary — v1.1.0

- The executor must verify that `linear-client` v1.1.0 is the installed
  version before the audit begins (e.g.
  `python -c "import linear_client; print(linear_client.__version__)"`).
- The new audit inspects `linear-client` v1.1.0 as the installed package.
  It is a standalone design artifact, not a patch on the v1.0.0 audit.
- The v1.0.0 audit is preserved at
  `docs/design/linear-domain-coverage-audit-v1.0.0.md` as a historical
  reference. The new audit may reference it for continuity but does not
  depend on it.
- The output artifact lives at
  `docs/design/linear-domain-coverage-audit-v1.1.0.md` so the audited library
  version is explicit in the filename. The unversioned
  `docs/design/linear-domain-coverage-audit.md` path is reserved as a
  compatibility index that points readers to the maintained versioned audits.
- The gap-closure analysis in
  [CR-26.04.07](planning/change-requests/CR-26.04.07.md) and its
  breaking-change and capability tables provide the starting input. The
  audit ticket should verify and refine these findings against the installed
  v1.1.0 source rather than copying them verbatim.
- The audit must cover the same areas as M1-D2 (coverage matrix, boundary
  decision, approved raw-GQL helpers, missing capabilities, risks) but
  should produce a clean document that reflects v1.1.0 without carrying
  forward v1.0.0-era qualifications.
- The audit must verify whether the per-issue domain-layer comment surface in
  v1.1.0 (`Comment.updated_at`, `.resolved_at`, `.parent`, `.children`)
  changes the integration path relative to the M3-O1 raw-adapter-only
  conclusion. The M3-O1 core decision (canonical input accepted) is
  unchanged, but the per-issue vs. batched boundary must be clarified: the
  audit should state which comment-metadata reads can use the domain layer
  and which still require the raw-GQL batch path.
- The adapter-boundary definition must include a **type-mapping table**: for
  each value that crosses the gateway boundary, state whether it uses an
  upstream `linear_client.types` alias, a context-sync-only alias (with
  justification), or bare `str` (with justification). This makes the type
  surface an explicit boundary deliverable rather than an implementation-time
  afterthought.
- The audit must evaluate adopting `linear_client.types` as the authoritative
  source for the five context-sync types that are exact semantic duplicates
  of upstream aliases (`IssueId`, `IssueKey`, `CommentId`, `AttachmentId`,
  and `Timestamp`/`IsoTimestamp`) and recommend a concrete reconciliation
  strategy. The preferred approach is re-exporting from upstream (e.g.
  `from linear_client.types import IssueId as IssueId`) so that existing
  import sites continue to work while the underlying `NewType` identity is
  shared across the dependency boundary. For `Timestamp` vs. `IsoTimestamp`,
  the audit should evaluate whether to adopt the upstream name or keep an
  explicit alias. The three context-sync-only types (`WorkspaceId`,
  `WorkspaceSlug`, `WriterId`) remain local since they have no upstream
  counterpart.
- The audit must also evaluate whether context-sync should adopt additional
  upstream type aliases that are currently represented as bare `str`:
  `UserId`, `TeamId`, `TeamKey`, `StatusId`, `LabelId`, `IssueLinkId`,
  `IssueLinkType`, `StatusCategory`, and `AssetUrl`. Several of these appear
  in the gateway protocol or rendered output today as bare `str`.
- If the audit identifies required changes to existing done-ticket code, the
  `LinearGateway` protocol, or artifacts outside M5-1's scope, those must be
  represented as new follow-on tasks or scope amendments to existing Todo
  tickets rather than silently absorbed into M5-1 or left untracked.

#### M5-D2 - Design-artifact refresh for v1.1.0 workspace model

- Retire `docs/design/linear-client-v1.0.0.md`. With the full `linear-client`
  source in the multi-root workspace, the local API reference summary is
  redundant — the library's own `__init__.py` module docstring,
  `docs/design/dependency-map.md`, `docs/pub/` documentation, and `examples/`
  directory are authoritative and better-maintained. The only context-sync-
  specific content (boundary guidance) now lives in the domain-coverage audit
  produced by M5-D1.
- Update `docs/design/dependency-map.md`'s private-dependency pointers to
  reference the library's own documentation paths within the workspace
  rather than the retired local summary.
- Update `docs/adr.md` to remove or replace stale workspace-access and
  dependency references. Specifically: the passage describing `linear-client`
  as a private GitHub repository that agents must not attempt to install
  should reflect the current workspace model (sibling clone with editable
  install, three auth modes available, v1.1.0 surface).
- Update `docs/design/0-top-level-design.md` to replace the same stale
  references. The dependency-boundary section should describe the current
  workspace layout and install path rather than directing readers to a
  retired design document.
- These updates are factual corrections to bring design artifacts into
  alignment with the current workspace reality, not architectural changes.
  The core dependency-boundary decisions (domain-layer-first, narrow raw-GQL
  escape hatch, read-only gateway) are unchanged and should not be revisited
  by this ticket.
- M5-D2 depends on M5-D1 so that the design-artifact refresh can reference
  the new audit's boundary decisions and type-mapping table rather than
  paraphrasing them independently.

#### M5-1 - Real Linear gateway and runtime wiring

- Implement the real gateway strictly inside the boundary defined by
  [M5-D1](#m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110).
  Do not widen raw `linear.gql.*` usage beyond the audited helper set without
  a separate accepted amendment.
- The v1.1.0 upgrade
  ([CR-26.04.07](planning/change-requests/CR-26.04.07.md)) closed the
  single-issue relation-read and per-issue comment-metadata gaps that were
  open under v1.0.0. The authoritative adapter boundary is defined by
  [M5-D1](#m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110);
  implement against that boundary. This supersedes the
  [M3-O1](#m3-o1---comments-signature-input-settlement) raw-adapter-only
  conclusion for single-ticket comment fetches; the raw helper remains only
  for the batched refresh comment-metadata path.
- This ticket is the explicit defer destination for
  [M4-2-R1](execution/M4-2-review.md), which concluded that the current
  operator-facing CLI and library docs cannot be treated as shippable while
  the real gateway path is still missing.
- The ticket must make the currently documented public runtime path actually
  usable: the library constructor and shipped CLI should stop failing solely
  because the concrete gateway is missing.
- Treat workspace identity, traversal relations, and the composite refresh
  metadata helpers as first-class gateway responsibilities rather than
  scattering those queries across orchestration code.
- Keep the gateway read-only with respect to Linear. The local adapter may use
  raw GraphQL only for the audited read helpers, never for mutations.
- The automated tests in this ticket should exercise the real gateway
  implementation against maintained fake/fixture transport inputs at the
  adapter boundary. They are not the live-Linear proof; they exist so the real
  adapter code is under automated coverage without requiring credentials for
  routine validation.
- `Issue.get_comments()` now returns a root-thread projection; the gateway
  must traverse `Comment.children` for full reply content.
- The existing [src/context_sync/_gateway.py](../src/context_sync/_gateway.py)
  protocol docstrings still describe `get_ticket_relations(issue_ids)` as a
  raw-GraphQL path and still allow
  `get_refresh_relation_metadata(issue_ids)` to share that query. Update
  those docstrings during implementation so the code comments match the
  audited M5-D1 boundary: domain-layer fan-out for traversal/rendered
  relations, raw helper only for batched refresh relation metadata.
- Treat the packaged `Issue.get_links()` safety cap (250 forward and 250
  inverse links per issue) as the accepted v1 operational limit for the
  audited domain-layer relation path. Do not add a raw fallback just because
  of that cap without a separate accepted amendment.
- Normalize `IssueLink` values from the fetched issue's perspective before
  emitting `RelationData`: forward `"blocks"` becomes `blocks`, inverse
  `"blocks"` becomes `is_blocked_by`, and informational link types
  (`"related"`, `"duplicate"`, `"similar"`) become `relates_to` while the
  raw upstream value is preserved in `RelationData.relation_type`. Do not
  infer the `parent` / `child` hierarchy dimensions from `IssueLink`
  records.
- If `Issue.get_comments()` returns `Comment.is_placeholder()` synthetic
  parents, exclude those placeholders from persisted bundles and normalize
  each visible child of a placeholder into its own top-level thread root for
  both bundle rendering and local `comments_signature` derivation.
- `User.app` replaces the removed `User.is_app_actor()` for app-actor
  identification.
- v1.1.0 provides `LinearNotFoundError` for entity-not-found handling, and
  semantic type aliases from `linear_client.types` should be adopted at the
  gateway boundary. Catch `LinearNotFoundError` on explicit entity lookups
  and map it to `RootNotFoundError`; map upstream auth, transport, or
  GraphQL failures that make the run non-viable to `SystemicRemoteError`.
- The gateway implementation must use a single `NewType` identity per domain
  concept across the boundary — no parallel definitions and no runtime casts.
  The type-mapping table produced by M5-D1 is the authoritative reference for
  which types to use at each boundary position.

#### M5-2 - Supported public runtime validation and smoke path

- This ticket exists because [M4-2-R2](execution/M4-2-review.md) showed that
  the current "end-to-end" coverage does not exercise the real public CLI
  surface. The amended plan should not call the runtime shippable until that
  gap is closed.
- This ticket is the explicit defer destination for
  [M4-2-R2](execution/M4-2-review.md) and
  [M4-2-R3](execution/M4-2-review.md): once the real gateway exists, it owns
  both the supported public-entrypoint integration proof and the durable smoke
  procedure covering environment bootstrap, one successful command path, and
  one representative failure mode.
- The maintained smoke path should cover the supported operator workflow, not a
  testing-only hook. It should include one happy-path command and one
  representative failure mode with expected stdout/stderr behavior, and it
  should run against a real Linear workspace or equivalent maintained live
  validation environment rather than against only the fake gateway.
- If the repository keeps private-handler coverage for targeted component
  testing, retain it honestly as component coverage; do not let it stand in
  for the supported runtime proof.
- [M4.1-1](#m4.1-1---cli-and-library-simplification) captures the accepted
  follow-on public-surface changes from [M4-R1](#m4-r1---cli-interface-review)
  and [M4-R2](#m4-r2---api-interface-review). M5-2 validation artifacts and
  the smoke recipe must reflect the four-command surface delivered by M4.1-1.
- Once the public runtime genuinely works, remove or rewrite the README's
  current pre-release runtime warning so the supported docs no longer
  advertise a deliberately inert surface.
- When exercising OAuth or client-credentials auth modes, the validation
  environment must use a freshly created v1.1.0 token file. `linear-client`
  v1.1.0 enforces a new token-file schema (`version` and `mode` fields
  required); legacy cached token files from v1.0.0 will fail authentication.
  See [CR-26.04.07](planning/change-requests/CR-26.04.07.md).

#### M5-3 - CLI auth-mode selection

- The CLI currently calls `Linear()` with no arguments, defaulting to
  `oauth` mode. Operators using `api_key` or `client_credentials` cannot
  switch modes without modifying the source.
- The library API (`ContextSync(linear=...)`) already accepts a pre-formed
  `Linear` instance, so programmatic callers have full control over how
  the client is built. Only the CLI layer lacks mode selection.
- Add a `--auth-mode` global option (choices: `oauth`,
  `client_credentials`, `api_key`) and pass the selected mode to
  `Linear(auth_mode=...)` in `_create_linear_client()`.
- The context-sync CLI's no-flag default is `client_credentials`. This tool
  primarily targets app-actor workflows. `--auth-mode` exists so operators
  can opt into `oauth` or `api_key` explicitly when needed.
- Do not make context-sync responsible for mirroring `linear-client`'s
  `LINEAR_ENV_PREFIX` / `env_prefix` behavior. Prefixed library variables are
  not part of the context-sync CLI contract. See
  [LC-9](linear-client-issues.md#lc-9---environment-variable-prefixing-leaks-caller-policy-into-the-library).
- Update the README quick-start, configuration table, and smoke-validation
  recipe to document all three modes.
- This is a context-sync CLI responsibility, not a `linear-client`
  feature request. See
  [LC-2](linear-client-issues.md#lc-2---no-environment-variable-control-for-auth_mode).

#### M5-4 - Adopt `linear-client` NewTypes and eliminate duplicate aliases

- `context_sync._types` independently defines `IssueId`, `IssueKey`,
  `CommentId`, and `AttachmentId` as `NewType` aliases, duplicating the
  authoritative types in `linear_client.types`. Pyright treats these as
  distinct types, creating friction at every gateway boundary crossing.
- The fix is to replace the four overlapping aliases in `_types.py` with
  re-exports from `linear_client.types`. `WriterId`, `Timestamp`,
  `WorkspaceId`, and `WorkspaceSlug` are context-sync-only concepts and
  remain in `_types.py`.
- Add `linear-client` as a declared dependency or use a
  `TYPE_CHECKING`-only import so Pyright can resolve the shared types.
- Remove the `UpstreamIssueId` bridge import workaround in
  `_real_gateway.py` — with shared type identity it is no longer needed.
- This is a context-sync cleanup task, not a `linear-client` issue. See
  [LC-6](linear-client-issues.md#lc-6---newtype-identity-mismatch-across-the-boundary).

### 9.3 Exit Criteria

1. The public `ContextSync(linear=...)` path and shipped CLI can execute
   against a real `linear-client`-backed gateway without `_gateway_override`.
2. The repository has automated validation that exercises the real gateway
   implementation and the real public entry points with maintained
   fake/fixture-backed inputs rather than only private handler coverage.
3. The repository has a durable smoke-validation recipe that exercises the
   shipped runtime path against a real Linear workspace or equivalent
   credentialed live validation environment.
4. The repository docs no longer claim a working surface that still
   intentionally fails.

---

## 10. Milestone 6 - Supported Docs and `1.0.0` Release Workflow

**Goal:** define and exercise the repository's supported documentation and
release boundary so the real runtime from Milestone 5 can ship as `1.0.0`
under a documented, repeatable process with durable review and close-out
artifacts.

### 10.1 Operational Prerequisites

| # | Status | Item | Requirement | Unblocks | Verification | Source |
| --- | --- | --- | --- | --- | --- | --- |
| <a id="m6-o1---release-channel-and-install-path-chosen"></a>M6-O1 | Todo | Release channel and install path chosen | The supported `1.0.0` publication destination and install path are chosen and recorded before docs, release-workflow, or release-readiness work begins | [M6-1](#m6-1---supported-user-facing-docs-and-installoperator-guide), [M6-2](#m6-2---canonical-release-workflow-checklist-and-version-state-guardrails), [M6-R1](#m6-r1---100-release-readiness-review) | Record the chosen publication channel and supported install path in repository artifacts before Milestone 6 drafting proceeds | [docs/policies/common/release-workflow.md](policies/common/release-workflow.md), direct human request |
| <a id="m6-o2---release-publication-credentials-and-approval-window-available"></a>M6-O2 | Todo | Release publication credentials and approval window available | The required tag/publish credentials and any human approval window needed for the canonical release path are available before the final release cut begins | [M6-3](#m6-3---100-release-cut-archive-and-next-cycle-bootstrap) | Confirm access to the required credentials and approvals before running the final release workflow | [docs/policies/common/release-workflow.md](policies/common/release-workflow.md), direct human request |

### 10.2 Review Tickets

| # | Status | Ticket | Deliverable | Dependencies | Reviewers | Source |
| --- | --- | --- | --- | --- | --- | --- |
| <a id="m6-r1---100-release-readiness-review"></a>M6-R1 | Todo | `1.0.0` release-readiness review | A durable repository review artifact that evaluates whether the real runtime, supported docs, install path, release checklist, version-state guardrails, and known deferrals together define a credible `1.0.0` boundary. The deliverable must distinguish must-fix blockers from post-`1.0.0` backlog items. | [M6-O1](#m6-o1---release-channel-and-install-path-chosen), [M6-1](#m6-1---supported-user-facing-docs-and-installoperator-guide), [M6-2](#m6-2---canonical-release-workflow-checklist-and-version-state-guardrails) | Independent Stage 2 review session | [docs/policies/common/documentation-workflow.md](policies/common/documentation-workflow.md), [docs/policies/common/release-workflow.md](policies/common/release-workflow.md), [README.md](../README.md) |

### 10.3 Implementation Tickets

| # | Status | Ticket | Description | Dependencies | Tests | Source |
| --- | --- | --- | --- | --- | --- | --- |
| <a id="m6-1---supported-user-facing-docs-and-installoperator-guide"></a>M6-1 | Todo | Supported user-facing docs and install/operator guide | Replace the current pre-release README surface with the supported `1.0.0` documentation set: installation guidance for the chosen distribution channel, configuration/bootstrap docs, operator workflows, manual smoke steps, and library/CLI examples aligned with the real shipped behavior | [M6-O1](#m6-o1---release-channel-and-install-path-chosen), [M5-2](#m5-2---supported-public-runtime-validation-and-smoke-path), [M4-R2](#m4-r2---api-interface-review), [M4-3](#m4-3---rename-root-ticket-id-to-key) | Documentation validation command for the supported docs surface, checked examples for the published install/run path, and review of all user-facing command examples against the shipped CLI/API | [docs/policies/common/documentation-workflow.md](policies/common/documentation-workflow.md), [docs/execution/M4-2-review.md](execution/M4-2-review.md), [README.md](../README.md) |
| <a id="m6-2---canonical-release-workflow-checklist-and-version-state-guardrails"></a>M6-2 | Todo | Canonical release workflow, checklist, and version-state guardrails | Define and implement the repository's canonical `1.0.0` release process, including the release automation entrypoint, human-readable release checklist, the standard maintained Python-package release scripts unless a justified exception is documented, artifact build/install validation, top-level `CHANGELOG.md` bootstrap for the first stable release, and a machine-checkable version-state guardrail for release tags versus unreleased development state | [M6-O1](#m6-o1---release-channel-and-install-path-chosen), [M6-1](#m6-1---supported-user-facing-docs-and-installoperator-guide) | Release dry-run or equivalent local validation, artifact build/install checks, version-state tests, and docs-gate evidence for the supported docs surface | [docs/policies/common/release-workflow.md](policies/common/release-workflow.md), [docs/policies/common/python/release-workflow.md](policies/common/python/release-workflow.md), [docs/policies/common/release-checklist-template.md](policies/common/release-checklist-template.md), [docs/policies/common/coding-guidelines.md](policies/common/coding-guidelines.md) |
| <a id="m6-3---100-release-cut-archive-and-next-cycle-bootstrap"></a>M6-3 | Todo | `1.0.0` release cut, archive, and next-cycle bootstrap | Run the canonical release workflow for `1.0.0`, publish the release through the chosen channel, archive the active plan / planning / execution artifacts under the release archive layout, and bootstrap the next unreleased development version and planning state | [M6-O2](#m6-o2---release-publication-credentials-and-approval-window-available), [M6-R1](#m6-r1---100-release-readiness-review) | Tagged-release verification, archive-layout verification, and post-release version/bootstrap checks proving the repo is back in a valid unreleased state | [docs/policies/common/release-workflow.md](policies/common/release-workflow.md), [docs/policies/common/python/release-workflow.md](policies/common/python/release-workflow.md), [docs/policies/common/planning-model.md](policies/common/planning-model.md), [src/context_sync/version.py](../src/context_sync/version.py) |

### 10.4 Detailed Ticket Notes

#### M6-1 - Supported user-facing docs and install/operator guide

- This ticket should define the repository's canonical supported docs surface
  for the first stable release. That may stay in `README.md` plus selected
  `docs/` pages, but the source tree and validation command must be explicit.
- Installation guidance must describe the real supported distribution channel
  for `context-sync` and any required `linear-client` precondition. Do not
  assume a public package index if the repository's chosen channel is still a
  git tag or private artifact source.
- The docs must cover at least: installation, credential/bootstrap setup, one
  first-time `sync`, routine `refresh`, root-management workflows, `diff`,
  logging/lock behavior, common failures, and the supported smoke path.
- If [M4-R2](#m4-r2---api-interface-review) accepts follow-on public API
  changes beyond [M4-3](#m4-3---rename-root-ticket-id-to-key), land those
  blockers before freezing the `1.0.0` docs set.
- The operator guide must document that `linear-client` v1.1.0 enforces a new
  token-file schema (`version` and `mode` fields required). Operators with
  cached OAuth or client-credentials token files from v1.0.0 must delete and
  recreate them. This applies only to those two auth modes; `api_key` mode
  does not use token files. See
  [CR-26.04.07](planning/change-requests/CR-26.04.07.md).

#### M6-2 - Canonical release workflow, checklist, and version-state guardrails

- The release workflow should define one canonical release entrypoint, one
  canonical checklist artifact, and the version/bootstrap rules needed after
  publication. Do not leave release steps scattered across chat, local notes,
  or execution artifacts.
- Because this repository ships Python package artifacts, the default
  Milestone 6 expectation is the standard maintained script split from
  [docs/policies/common/python/release-workflow.md](policies/common/python/release-workflow.md):
  `scripts/build_release.sh`, `scripts/build_validate.sh`,
  `scripts/next_release.sh`, and `scripts/check_version_state.py`, plus the
  matching README and checklist exposure. If the repo intentionally chooses a
  different maintained layout, document that exception explicitly rather than
  drifting into an ad hoc release flow.
- The first stable release must add a top-level `CHANGELOG.md` per
  [docs/policies/common/coding-guidelines.md](policies/common/coding-guidelines.md).
- The release path must prove the chosen artifact/install story actually
  works. A wheel or sdist build alone is not enough if the supported install
  contract requires additional validation.
- The version-state guardrail should fail loudly when the repository version
  and tag/bootstrap state disagree.

#### M6-R1 - `1.0.0` release-readiness review

- This review is separate from the Phase B review of any one implementation
  ticket. It evaluates the total shipped boundary: runtime, docs, install
  path, release checklist, known deferrals, and the credibility of the
  `1.0.0` promise.
- If the review identifies missing must-fix work, add it as explicit follow-on
  ticket(s) or a further plan amendment rather than burying it in review
  prose.

#### M6-3 - `1.0.0` release cut, archive, and next-cycle bootstrap

- The release cut should follow the canonical release order from
  [docs/policies/common/release-workflow.md](policies/common/release-workflow.md):
  automated validation, docs validation, artifact build/validation, annotated
  tag creation, publication, and post-release verification.
- Close-out must archive the active plan, planning change requests, and
  execution artifacts together under the release archive layout.
- The next-cycle bootstrap must leave the repository in a valid unreleased
  development state rather than stranded on the release version after publish.

### 10.5 Exit Criteria

1. The repository has a supported `1.0.0` docs surface aligned with actual
   installation, configuration, CLI, and library behavior.
2. The repository has a canonical release workflow, release checklist,
   `CHANGELOG.md`, and machine-checkable version-state guardrail for stable
   releases.
3. An independent release-readiness review has concluded that the `1.0.0`
   boundary is credible, and the actual `1.0.0` cut/archive/bootstrap path has
   been executed successfully.

---

## 11. Validation Strategy

**Unit and component tests**
- [M1-1](#m1-1---project-scaffold-and-public-runtime-contracts) should define
  the repository's canonical format/lint/test commands before later
  implementation tickets depend on them.
- Cover manifest parsing, lock contention, traversal decisions, alias
  resolution, and serializer normalization with isolated tests.

**Integration tests**
- [M1-1](#m1-1---project-scaffold-and-public-runtime-contracts) should
  establish the reusable fake-client or fixture-builder pattern that later
  integration tickets extend instead of inventing per-ticket mocks.
- Use fixture-driven or fake-client-backed tests to exercise `sync`,
  `refresh`, `add`, `remove-root`, and `diff` end to end without requiring live
  network access for routine validation.
- [M5-1](#m5-1---real-linear-gateway-and-runtime-wiring) should add automated
  coverage for the real gateway implementation itself using maintained
  fake/fixture transport inputs at the audited adapter boundary.
- [M5-2](#m5-2---supported-public-runtime-validation-and-smoke-path) should
  exercise the shipped CLI through `main()` or the installed console script
  with maintained fake/fixture-backed runtime inputs, and keep the private
  handler path classified as component coverage only.
- Treat directory-level idempotency as a named cross-cutting check: run
  `sync` twice against the same fixture and verify the second pass performs no
  file rewrites, then run `refresh` against unchanged upstream fixtures and
  verify zero local churn there as well.
- Keep live Linear behavior checks narrowly scoped to
  [M1-D1](#m1-d1---refresh-freshness-validation-spike) and the explicit
  real-environment smoke path in
  [M5-2](#m5-2---supported-public-runtime-validation-and-smoke-path).

**Documentation and release gates**
- Update README and operator-facing docs in the same tickets that change public
  CLI or configuration behavior.
- Because the repository has not yet declared a runtime toolchain, the first
  implementation milestone must make the command surface explicit before later
  tickets can satisfy the validation gate consistently.
- [M6-1](#m6-1---supported-user-facing-docs-and-installoperator-guide) should
  define the supported docs surface explicitly and validate checked examples
  against the chosen install/run path.
- [M6-2](#m6-2---canonical-release-workflow-checklist-and-version-state-guardrails)
  should add the canonical release dry-run/build/install validation,
  version-state guardrail checks, and release-checklist evidence for the chosen
  publication channel.
- [M6-3](#m6-3---100-release-cut-archive-and-next-cycle-bootstrap) should
  verify tagged release publication, archive layout, and post-release
  bootstrap state.

**Manual validation**
- Smoke-test CLI commands against a temporary context directory and inspect the
  rendered manifest, lock, and ticket files for readability and determinism.
- The durable smoke path from
  [M5-2](#m5-2---supported-public-runtime-validation-and-smoke-path) should
  cover environment bootstrap, one successful command path, and one
  representative failure path against a real Linear workspace or equivalent
  maintained live validation environment.
- Manually verify root quarantine warnings, changed-field reporting, and the
  final install/run/docs story in representative scenarios.

---

## 12. Open Items to Resolve Before Execution

| Item | Blocks | Resolution path |
| --- | --- | --- |
| Availability of a live Linear workspace or fixture strategy for [M1-D1](#m1-d1---refresh-freshness-validation-spike) | [M1-D1](#m1-d1---refresh-freshness-validation-spike), [M3-1](#m3-1---incremental-refresh-and-quarantined-root-recovery) | After [M1-O1](#m1-o1---live-linear-validation-environment-available) makes the execution environment available, confirm whether the refresh validation spike can run against real workspace data or whether a narrower pre-implementation probe artifact is needed first |

---

## 13. Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| [OQ-1](adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior) invalidates issue-level `updated_at` as the refresh cursor | High | Front-load [M1-D1](#m1-d1---refresh-freshness-validation-spike), route the governing design response through [M1-D3](#m1-d3---refresh-composite-freshness-contract-amendment), and keep [M3-1](#m3-1---incremental-refresh-and-quarantined-root-recovery) blocked until [M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) audits the required refresh operations against that accepted contract |
| `linear-client` lacks one or more required domain operations for v1, or a required audited read still proves insufficient during [M5-1](#m5-1---real-linear-gateway-and-runtime-wiring) | High | Audit the required operations in [M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary), keep a narrow adapter boundary in [M1-1](#m1-1---project-scaffold-and-public-runtime-contracts), and require [M5-1](#m5-1---real-linear-gateway-and-runtime-wiring) to record any remaining upstream gap explicitly instead of hiding it in ad hoc adapter changes |
| Real gateway wiring drifts away from the audited `linear-client` boundary | Medium | Constrain [M5-1](#m5-1---real-linear-gateway-and-runtime-wiring) to the helper set already documented in [docs/design/linear-domain-coverage-audit-v1.1.0.md](design/linear-domain-coverage-audit-v1.1.0.md), and route any new raw GraphQL need through an explicit accepted amendment rather than widening the shipped boundary silently |
| Deterministic rendering or alias-renaming bugs produce misleading local context | Medium | Centralize rendering/verification in [M1-2](#m1-2---manifest-lock-and-rendering-primitives) and cover rename/threading cases in [M2-2](#m2-2---ticket-fetch-normalization-and-render-pipeline) |
| Interrupted runs still leave a partially updated directory at snapshot scope in v1 | Medium | Preserve atomic per-file writes, document the limitation clearly, and keep stronger directory-level atomicity deferred to [FW-3](future-work.md#fw-3-whole-snapshot-atomic-commit) |
| Supported docs, install guidance, or smoke steps drift away from the actual shipped runtime and publication path | Medium | Gate [M6-1](#m6-1---supported-user-facing-docs-and-installoperator-guide) on [M5-2](#m5-2---supported-public-runtime-validation-and-smoke-path) plus the chosen publication channel in [M6-O1](#m6-o1---release-channel-and-install-path-chosen), and keep [M6-R1](#m6-r1---100-release-readiness-review) responsible for checking the final docs/install story against the real boundary |
| Release tag, changelog, or bootstrap state diverges from the canonical version source | Medium | Use [M6-2](#m6-2---canonical-release-workflow-checklist-and-version-state-guardrails) to add the canonical release scripts, checklist, `CHANGELOG.md`, and version-state guardrail, then require [M6-3](#m6-3---100-release-cut-archive-and-next-cycle-bootstrap) to verify tagged release publication and valid post-release bootstrap state |

---

## 14. Notes

- This active plan was promoted from the reviewed Stage 3 draft on 2026-03-17
  under
  [docs/policies/common/planning-model.md](policies/common/planning-model.md).
  The activation review record remains in
  [docs/planning/implementation-plan-review.md](planning/implementation-plan-review.md).
- The active plan was materially amended on 2026-03-18 by accepting and
  applying
  [docs/planning/change-requests/CR-26.03.18.md](planning/change-requests/CR-26.03.18.md).
- The active plan was materially amended again on 2026-03-23 by accepting and
  applying
  [docs/planning/change-requests/CR-26.03.23.md](planning/change-requests/CR-26.03.23.md).
- The active plan was materially amended on 2026-03-24 by accepting and
  applying
  [docs/planning/change-requests/CR-26.03.24.md](planning/change-requests/CR-26.03.24.md).
- The active plan was materially amended again on 2026-03-24 by accepting and
  applying
  [docs/planning/change-requests/CR-26.03.24-policy-compliance.md](planning/change-requests/CR-26.03.24-policy-compliance.md),
  adding Milestone 4.2 (common-policy compliance) and updating M5-1/M5-2
  dependencies.
- If future work currently deferred in
  [docs/future-work.md](future-work.md)
  is pulled into this release, treat that as a material planning change rather
  than silently adding scope during implementation.
