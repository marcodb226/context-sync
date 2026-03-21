# Implementation Plan - Context Sync v1 Bootstrap

> **Status**: Active
> **Governing artifacts**:
> [docs/problem-statement.md](problem-statement.md),
> [docs/adr.md](adr.md),
> [docs/design/0-top-level-design.md](design/0-top-level-design.md),
> [docs/design/linear-client.md](design/linear-client.md),
> [docs/future-work.md](future-work.md),
> [docs/policies/common/planning-model.md](policies/common/planning-model.md),
> [docs/policies/common/execution-model.md](policies/common/execution-model.md)

---

## 1. Scope and Strategy

This active plan is the repository's first formal implementation plan. It turns the
existing problem statement, ADR, design notes, and ADR review outcomes into a
bootstrap delivery sequence for the initial `context-sync` release.

**Implementation strategy - foundation first, then whole-snapshot behavior.**

The plan front-loads the release-gating refresh validation work and the shared
file-system/runtime primitives before building `sync`, then layers incremental
operations and CLI/readiness work on top of that base. This sequencing keeps
the early tickets focused on repository-shaping decisions that later milestones
should not have to rediscover.

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
  reuse them across `sync`, `refresh`, `add`, `remove-root`, and `diff`.

**What this plan covers:** the initial Python package and project scaffold, the
async library surface, deterministic context-directory persistence, whole-
snapshot `sync`, incremental `refresh`, `add`, `remove-root`, `diff`, a thin
CLI wrapper, and the validation/documentation work needed to ship that first
release.

### 1.1 Stage 1 Planning Inputs

- Bootstrap candidate sources:
  [docs/problem-statement.md](problem-statement.md),
  [docs/adr.md](adr.md),
  [docs/design/0-top-level-design.md](design/0-top-level-design.md),
  [docs/design/linear-client.md](design/linear-client.md),
  [docs/planning/26.03.15 - ADR review.md](planning/26.03.15%20-%20ADR%20review.md),
  and [docs/future-work.md](future-work.md).
- Direct human request: start the first formal implementation plan draft for
  the repository.
- Prior release / archival context: none. The repository is still in bootstrap
  planning state and does not yet have an active plan artifact.

### 1.2 Candidate Decisions

Because
[docs/future-work.md](future-work.md)
has no shortlisted `Next release` items, this bootstrap planning pass selected
concrete scope from the problem statement, ADR/design artifacts, and accepted
ADR review outcomes while explicitly keeping the current `FW-*` backlog
deferred.

| Candidate | Decision | Plan destination | Notes |
| --- | --- | --- | --- |
| Live Linear validation environment bootstrap from [docs/design/0-top-level-design.md](design/0-top-level-design.md#11-linear-dependency-boundary), [docs/design/linear-client.md](design/linear-client.md#authentication), and direct human clarification during planning | Keep | [M1-O1](#m1-o1---live-linear-validation-environment-available) | Makes the human-provided runtime/bootstrap prerequisite for the release-gate spike explicit before [M1-D1](#m1-d1---refresh-freshness-validation-spike) begins. |
| Refresh correctness gate from [OQ-1](adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior) | Keep | [M1-D1](#m1-d1---refresh-freshness-validation-spike) | Must be settled before `refresh` can be considered implementation-complete. |
| Post-spike refresh-contract amendment from [docs/design/refresh-freshness-validation.md](design/refresh-freshness-validation.md) and [docs/planning/change-requests/CR-26.03.18.md](planning/change-requests/CR-26.03.18.md) | Keep | [M1-D3](#m1-d3---refresh-composite-freshness-contract-amendment) | Separates the release-gate spike from the governing design rewrite, makes relation freshness mandatory first-release scope, and narrows attachment freshness out of the v1 incremental-refresh correctness contract. |
| Linear domain-layer coverage audit and adapter-boundary definition from [docs/adr.md](adr.md#31-foundation), [docs/design/0-top-level-design.md](design/0-top-level-design.md#11-linear-dependency-boundary), and [docs/design/linear-client.md](design/linear-client.md) | Keep | [M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) | Makes the domain-vs-GraphQL fallback decision explicit before traversal, relation, and refresh tickets depend on it. |
| Library API, runtime configuration, and package bootstrap from [docs/adr.md](adr.md#31-foundation), [docs/design/0-top-level-design.md](design/0-top-level-design.md#1-library-api), and [docs/design/linear-client.md](design/linear-client.md) | Keep | [M1-1](#m1-1---project-scaffold-and-public-runtime-contracts) | Establishes the project layout, public interfaces, per-process concurrency controls, reusable test harness, and the narrow dependency boundary with `linear-client`. |
| Manifest, deterministic ticket rendering, and lock metadata from [docs/adr.md](adr.md#2-persistence-format), [docs/design/0-top-level-design.md](design/0-top-level-design.md#21-context-directory-contents), and [ADR-R2a](planning/26.03.15%20-%20ADR%20review.md#adr-r2a-done-stale-lock-recovery-and-lock-metadata) | Keep | [M1-2](#m1-2---manifest-lock-and-rendering-primitives) | Shared persistence helpers should land before the flow-specific tickets. |
| Tiered per-root traversal and bounded reachable sets from [docs/adr.md](adr.md#13-traversal-order-and-ticket-cap) and [ADR-R3](planning/26.03.15%20-%20ADR%20review.md#adr-r3-done-pure-breadth-first-traversal-cutoffs) | Keep | [M2-1](#m2-1---reachable-graph-builder-and-tiered-per-root-traversal) | Structural edges must beat informational edges near the ticket cap. |
| Full-snapshot `sync` behavior from [docs/adr.md](adr.md#51-sync-full-snapshot-rebuild) and [docs/design/0-top-level-design.md](design/0-top-level-design.md#61-sync-flow) | Keep | [M2-3](#m2-3---full-snapshot-sync-flow) | Initial materialization should exist before incremental maintenance flows. |
| Incremental `refresh` and root quarantine semantics from [docs/adr.md](adr.md#52-refresh-incremental-whole-snapshot-update), [docs/adr.md](adr.md#61-snapshot-consistency-contract), and [ADR-R4](planning/26.03.15%20-%20ADR%20review.md#adr-r4-done-terminal-root-fragility) | Keep | [M3-1](#m3-1---incremental-refresh-and-quarantined-root-recovery) | Depends on the `OQ-1` outcome and should carry the default `quarantine` policy. |
| Root-set mutation flows from [docs/design/0-top-level-design.md](design/0-top-level-design.md#63-add-flow) and [docs/design/0-top-level-design.md](design/0-top-level-design.md#65-remove-root-flow) | Keep | [M3-2](#m3-2---add-and-remove-root-whole-snapshot-flows) | `add` and `remove-root` should reuse whole-snapshot refresh semantics under one writer lock. |
| Non-mutating drift inspection from [docs/adr.md](adr.md#53-diff-non-mutating-drift-inspection) and [docs/design/0-top-level-design.md](design/0-top-level-design.md#64-diff-flow) | Keep | [M3-3](#m3-3---diff-mode-and-lock-aware-drift-reporting) | Must preserve the read-only lock behavior described in the ADR. |
| CLI packaging and operator-facing runtime docs from [docs/design/0-top-level-design.md](design/0-top-level-design.md#2-cli-interface), [README.md](../README.md), and [docs/policies/common/coding-guidelines.md](policies/common/coding-guidelines.md) | Keep | [M4-1](#m4-1---cli-surface-and-command-output-contracts), [M4-2](#m4-2---operational-logging-validation-hardening-and-user-docs) | The repo currently has no runtime scaffold, so the first implementation pass must also define how humans run and validate the tool. |
| [FW-1](future-work.md#fw-1-comment-storage-optimizations) | Defer | None in this plan | Keep the first-release full-comment-history contract. |
| [FW-2](future-work.md#fw-2-attachment-content-handling) | Defer | None in this plan | Attachment and resource handling remains metadata-only in v1, and attachment-only freshness drift is not part of the first-release incremental-refresh correctness contract. |
| [FW-3](future-work.md#fw-3-whole-snapshot-atomic-commit) | Defer | None in this plan | Preserve atomic file writes, but defer whole-directory atomic commit. |
| [FW-4](future-work.md#fw-4-historical-ticket-alias-import) | Defer | None in this plan | Offline alias resolution is limited to aliases observed after tracking begins. |
| [FW-5](future-work.md#fw-5-ticket-history-and-sectioned-ticket-artifacts) | Defer | None in this plan | The v1 base snapshot is limited to metadata, description, and comments. |
| [FW-6](future-work.md#fw-6-transient-ticket-preview-without-persistence) | Defer | None in this plan | Preview-only behavior is explicitly out of scope for the first plan. |
| Cross-process rate-limit coordination from [ADR-R5](planning/26.03.15%20-%20ADR%20review.md#adr-r5-discarded-the-thundering-herd-rate-limit-risk) | Drop | None in this plan | Keep rate-limit/backoff behavior inside `linear-client` or the embedding runtime. |
| UUID-based ticket filenames from [ADR-R6](planning/26.03.15%20-%20ADR%20review.md#adr-r6-discarded-file-renaming-breaks-strict-idempotency) | Drop | None in this plan | Keep human-readable current issue-key filenames as the persisted default. |

### 1.3 Execution Model

This active plan explicitly adopts
[docs/policies/common/execution-model.md](policies/common/execution-model.md)
for the named operational, design, and implementation tickets below. Once a
ticket begins, its work must follow the execution-model Phase A/B/C artifact
flow in [docs/execution/](execution/) and satisfy the validation and review
gates defined there.

Ticket identifiers in this active plan use these forms:

- Operational tickets: `Mx-Oy`
- Design tickets: `Mx-Dy`
- Implementation tickets: `Mx-z`
- Review finding IDs after activation: `<ticket-id>-Rn`

---

## 2. Milestone Overview

| Milestone | Name | Primary deliverable |
| --- | --- | --- |
| M1 | Foundation and release-gate validation | Live validation bootstrap, project scaffold, Linear adapter-boundary audit, shared persistence primitives, and an explicit `OQ-1` outcome |
| M2 | Full snapshot materialization | Deterministic traversal, rendering, and whole-snapshot `sync` |
| M3 | Incremental maintenance and drift inspection | `refresh`, `add`, `remove-root`, and `diff` with the ADR's missing-root and lock semantics |
| M4 | CLI and release readiness | Human-facing commands, operational logging, validation coverage, and onboarding docs |

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
| <a id="m1-o1---live-linear-validation-environment-available"></a>M1-O1 | Done | Live Linear validation environment available | A human-prepared execution environment for the repository with the repo-local `.venv` available, `linear-client` installed in that environment, and the required Linear credential environment variables exposed to the same execution session that will run the release-gate spike | [M1-D1](#m1-d1---refresh-freshness-validation-spike) | Confirm the repo-local Python environment can import `linear_client` and that the same session can authenticate successfully before starting the spike | [docs/design/0-top-level-design.md](design/0-top-level-design.md#11-linear-dependency-boundary), [docs/design/linear-client.md](design/linear-client.md#authentication) |

### 3.2 Design Tickets

| # | Status | Ticket | Deliverable | Dependencies | Reviewers | Source |
| --- | --- | --- | --- | --- | --- | --- |
| <a id="m1-d1---refresh-freshness-validation-spike"></a>M1-D1 | Done | Refresh freshness validation spike | A short repository artifact that records whether issue-level `updated_at` is sufficient for the v1 persisted snapshot contract and, if not, the minimum amendment shape plus the need for a follow-on plan/design update before `refresh` work proceeds | [M1-O1](#m1-o1---live-linear-validation-environment-available) | Independent Stage 2 review session | [OQ-1](adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior) |
| <a id="m1-d3---refresh-composite-freshness-contract-amendment"></a>M1-D3 | Done | Refresh composite freshness contract amendment | A governing design amendment that replaces the single issue-level `updated_at` refresh assumption with the v1 per-ticket composite freshness contract required after [M1-D1](#m1-d1---refresh-freshness-validation-spike), including the exact comment-change signal to support comment creation and comment edits, the mandatory first-release relation freshness contract needed to keep graph state correct, the required local freshness metadata/comparison contract, and the explicit narrowing of attachment freshness out of the v1 incremental-refresh correctness contract into future work | [M1-D1](#m1-d1---refresh-freshness-validation-spike) | Independent Stage 2 review session | [docs/design/refresh-freshness-validation.md](design/refresh-freshness-validation.md), [docs/design/0-top-level-design.md](design/0-top-level-design.md#62-refresh-flow), [OQ-1](adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior), [FW-2](future-work.md#fw-2-attachment-content-handling) |
| <a id="m1-d2---linear-domain-coverage-audit-and-adapter-boundary"></a>M1-D2 | Done | Linear domain-coverage audit and adapter boundary | A repository artifact that enumerates the v1 Linear operations required by traversal, fetch, and the amended refresh contract, records whether the `linear-client` domain layer already covers each one, and defines any narrow `linear.gql.*` fallback boundary that implementation tickets may use | [M1-D3](#m1-d3---refresh-composite-freshness-contract-amendment) | Independent Stage 2 review session | [docs/adr.md](adr.md#31-foundation), [docs/design/0-top-level-design.md](design/0-top-level-design.md#11-linear-dependency-boundary), [docs/design/linear-client.md](design/linear-client.md) |

### 3.3 Implementation Tickets

| # | Status | Ticket | Description | Dependencies | Tests | Source |
| --- | --- | --- | --- | --- | --- | --- |
| <a id="m1-1---project-scaffold-and-public-runtime-contracts"></a>M1-1 | Done | Project scaffold and public runtime contracts | Create the initial Python package layout, configuration surface, public async entry points, shared result/error models, reusable fake-client test harness, and the documented developer command set the rest of the plan will rely on | [M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) | Unit tests for configuration parsing, result/error contracts, adapter/fake-client contracts, and package import boundaries | [docs/adr.md](adr.md#31-foundation), [docs/design/0-top-level-design.md](design/0-top-level-design.md#1-library-api), [docs/design/linear-client.md](design/linear-client.md), [README.md](../README.md) |
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
| <a id="m2-2---ticket-fetch-normalization-and-render-pipeline"></a>M2-2 | In progress | Ticket fetch normalization and render pipeline | Normalize fetched ticket data into the persisted manifest/ticket shape, execute bounded concurrent fetches through the shared adapter, preserve alias history on issue-key changes, render threaded comments deterministically, and verify generated output before it is accepted | [M1-2](#m1-2---manifest-lock-and-rendering-primitives), [M2-1](#m2-1---reachable-graph-builder-and-tiered-per-root-traversal) | Serializer and parser tests for alias retention, issue-key rename behavior, comment-thread ordering, concurrency-limit behavior, and verification mismatch handling | [docs/adr.md](adr.md#2-persistence-format), [docs/adr.md](adr.md#31-foundation), [docs/design/0-top-level-design.md](design/0-top-level-design.md#22-ticket-file-rendering), [docs/design/0-top-level-design.md](design/0-top-level-design.md#7-risks-and-mitigations-tool-specific) |
| <a id="m2-3---full-snapshot-sync-flow"></a>M2-3 | Todo | Full-snapshot `sync` flow | Implement the initial/rooted whole-snapshot rebuild path, including workspace validation, manifest bootstrap, all-root traversal, reachable-ticket rewrite, and derived-ticket pruning | [M2-1](#m2-1---reachable-graph-builder-and-tiered-per-root-traversal), [M2-2](#m2-2---ticket-fetch-normalization-and-render-pipeline) | Integration tests for initial sync, repeated no-op sync, workspace mismatch rejection, and derived-ticket pruning | [docs/adr.md](adr.md#51-sync-full-snapshot-rebuild), [docs/design/0-top-level-design.md](design/0-top-level-design.md#61-sync-flow), [docs/design/0-top-level-design.md](design/0-top-level-design.md#4-error-handling) |

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

### 5.1 Design Tickets

No new milestone-specific design tickets are planned here, but this milestone
remains explicitly gated on the resolved Milestone 1 refresh-design chain:
[M1-D1](#m1-d1---refresh-freshness-validation-spike) for the release-gate
evidence, [M1-D3](#m1-d3---refresh-composite-freshness-contract-amendment) for
the accepted replacement contract, and
[M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) for the
matching adapter audit. Milestone 3 should implement that adopted contract
rather than reopen the refresh design during implementation.

### 5.2 Implementation Tickets

| # | Status | Ticket | Description | Dependencies | Tests | Source |
| --- | --- | --- | --- | --- | --- | --- |
| <a id="m3-1---incremental-refresh-and-quarantined-root-recovery"></a>M3-1 | Todo | Incremental `refresh` and quarantined-root recovery | Recompute reachability from active roots, batch-check freshness, re-fetch only stale or newly discovered tickets, quarantine or remove unavailable roots per policy, and recover quarantined roots when they become visible again | [M1-D3](#m1-d3---refresh-composite-freshness-contract-amendment), [M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary), [M2-2](#m2-2---ticket-fetch-normalization-and-render-pipeline), [M2-3](#m2-3---full-snapshot-sync-flow) | Integration tests for stale-vs-fresh refresh, unchanged-upstream no-op refresh/no rewrite, root quarantine, root reactivation, explicit remove policy, and changed-ticket selective rewrite behavior | [docs/adr.md](adr.md#52-refresh-incremental-whole-snapshot-update), [docs/adr.md](adr.md#61-snapshot-consistency-contract), [docs/design/0-top-level-design.md](design/0-top-level-design.md#62-refresh-flow), [ADR-R4](planning/26.03.15%20-%20ADR%20review.md#adr-r4-done-terminal-root-fragility) |
| <a id="m3-2---add-and-remove-root-whole-snapshot-flows"></a>M3-2 | Todo | `add` and `remove-root` whole-snapshot flows | Implement root-set mutation through alias-aware ticket resolution, workspace checks, manifest updates, and reuse of the whole-snapshot refresh behavior under the same writer lock | [M3-1](#m3-1---incremental-refresh-and-quarantined-root-recovery) | Integration tests for adding by issue key and URL, overlapping-root refresh behavior, and failing `remove-root` for non-roots | [docs/design/0-top-level-design.md](design/0-top-level-design.md#63-add-flow), [docs/design/0-top-level-design.md](design/0-top-level-design.md#65-remove-root-flow), [docs/adr.md](adr.md#14-root-vs-derived-tickets) |
| <a id="m3-3---diff-mode-and-lock-aware-drift-reporting"></a>M3-3 | Todo | `diff` mode and lock-aware drift reporting | Implement the non-mutating drift inspection path, including tracked-ticket comparison, `missing_remotely` classification, changed-field reporting, and refusal to run when a non-stale writer lock exists | [M2-2](#m2-2---ticket-fetch-normalization-and-render-pipeline), [M2-3](#m2-3---full-snapshot-sync-flow) | Integration tests for lock refusal, stale-lock observation without mutation, changed-field reporting, and unavailable-ticket classification | [docs/adr.md](adr.md#53-diff-non-mutating-drift-inspection), [docs/design/0-top-level-design.md](design/0-top-level-design.md#64-diff-flow), [docs/design/0-top-level-design.md](design/0-top-level-design.md#4-error-handling) |

### 5.3 Detailed Ticket Notes

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
- Do not begin [M3-1](#m3-1---incremental-refresh-and-quarantined-root-recovery)
  until repository artifacts record the accepted `comments_signature` input:
  either probe-backed confirmation that comment-level `updated_at` advances on
  edit, or a later accepted design amendment that names the replacement input.
  This is a pre-implementation gate carried forward from
  [M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary), not an
  implementation-time choice.
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

### 5.4 Exit Criteria

1. `refresh` can update existing snapshots incrementally without weakening the
   ADR's freshness or missing-root semantics.
2. `add` and `remove-root` reuse whole-snapshot behavior correctly for
   overlapping root graphs.
3. `diff` reports drift without mutating files, manifest state, or lock state.

---

## 6. Milestone 4 - CLI and Release Readiness

**Goal:** make the tool usable by human operators and automation with clear
commands, durable docs, and validation coverage that matches the repository's
documented contracts.

### 6.1 Design Tickets

No additional design tickets are planned. This milestone should package and
validate the already-implemented behavior rather than introduce new product
scope.

### 6.2 Implementation Tickets

| # | Status | Ticket | Description | Dependencies | Tests | Source |
| --- | --- | --- | --- | --- | --- | --- |
| <a id="m4-1---cli-surface-and-command-output-contracts"></a>M4-1 | Todo | CLI surface and command output contracts | Add the thin CLI wrapper over the async library, expose the documented commands and options, and define human-readable plus machine-readable output behavior for success and failure cases | [M2-3](#m2-3---full-snapshot-sync-flow), [M3-1](#m3-1---incremental-refresh-and-quarantined-root-recovery), [M3-2](#m3-2---add-and-remove-root-whole-snapshot-flows), [M3-3](#m3-3---diff-mode-and-lock-aware-drift-reporting) | CLI tests for command parsing, JSON output, lock-error text, and missing-root-policy selection | [docs/design/0-top-level-design.md](design/0-top-level-design.md#2-cli-interface), [docs/design/0-top-level-design.md](design/0-top-level-design.md#4-error-handling) |
| <a id="m4-2---operational-logging-validation-hardening-and-user-docs"></a>M4-2 | Todo | Operational logging, validation hardening, and user docs | Add the INFO/DEBUG logging contract, end-to-end validation coverage, onboarding and usage docs, and the sample configuration artifact needed to satisfy the repository's documentation/security conventions | [M4-1](#m4-1---cli-surface-and-command-output-contracts) | End-to-end fixture tests covering all major modes plus manual CLI smoke checks documented in repo docs | [docs/adr.md](adr.md#61-snapshot-consistency-contract), [README.md](../README.md), [docs/policies/common/coding-guidelines.md](policies/common/coding-guidelines.md) |

### 6.3 Detailed Ticket Notes

#### M4-1 - CLI surface and command output contracts

- Keep the CLI thin. Flow logic should remain in the async library layer so the
  repository does not fork behavior between human and programmatic entry
  points.
- Command output should make the difference between active-lock refusal,
  demonstrably stale-lock preemption, and root quarantine visible without
  requiring debug logging.

#### M4-2 - Operational logging, validation hardening, and user docs

- The first implementation pass should add the sample configuration artifact
  that enumerates required environment variables without secrets, because the
  CLI path depends on credentialed `linear-client` startup.
- Keep validation focused on the declared repository command set from
  [M1-1](#m1-1---project-scaffold-and-public-runtime-contracts) so later ticket
  work has one canonical lint/format/test surface.

### 6.4 Exit Criteria

1. Human operators can run the documented CLI commands for `sync`, `refresh`,
   `add`, `remove-root`, and `diff`.
2. Logging and result output make operational failures diagnosable without
   exposing secrets.
3. The repository includes user-facing docs and validation coverage that match
   the implemented public behavior.

---

## 7. Validation Strategy

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
- Treat directory-level idempotency as a named cross-cutting check: run
  `sync` twice against the same fixture and verify the second pass performs no
  file rewrites, then run `refresh` against unchanged upstream fixtures and
  verify zero local churn there as well.
- Keep live Linear behavior checks narrowly scoped to
  [M1-D1](#m1-d1---refresh-freshness-validation-spike)
  and any explicit follow-up needed to confirm `linear-client` integration
  assumptions.

**Documentation and release gates**
- Update README and operator-facing docs in the same tickets that change public
  CLI or configuration behavior.
- Because the repository has not yet declared a runtime toolchain, the first
  implementation milestone must make the command surface explicit before later
  tickets can satisfy the validation gate consistently.

**Manual validation**
- Smoke-test CLI commands against a temporary context directory and inspect the
  rendered manifest, lock, and ticket files for readability and determinism.
- Manually verify root quarantine warnings, issue-key rename behavior, and
  changed-field reporting in representative scenarios.

---

## 8. Open Items to Resolve Before Execution

| Item | Blocks | Resolution path |
| --- | --- | --- |
| Availability of a live Linear workspace or fixture strategy for [M1-D1](#m1-d1---refresh-freshness-validation-spike) | [M1-D1](#m1-d1---refresh-freshness-validation-spike), [M3-1](#m3-1---incremental-refresh-and-quarantined-root-recovery) | After [M1-O1](#m1-o1---live-linear-validation-environment-available) makes the execution environment available, confirm whether the refresh validation spike can run against real workspace data or whether a narrower pre-implementation probe artifact is needed first |

---

## 9. Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| [OQ-1](adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior) invalidates issue-level `updated_at` as the refresh cursor | High | Front-load [M1-D1](#m1-d1---refresh-freshness-validation-spike), route the governing design response through [M1-D3](#m1-d3---refresh-composite-freshness-contract-amendment), and keep [M3-1](#m3-1---incremental-refresh-and-quarantined-root-recovery) blocked until [M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) audits the required refresh operations against that accepted contract |
| `linear-client` lacks one or more required domain operations for v1 | Medium | Audit the required operations in [M1-D2](#m1-d2---linear-domain-coverage-audit-and-adapter-boundary), keep a narrow adapter boundary in [M1-1](#m1-1---project-scaffold-and-public-runtime-contracts), and explicitly document any GraphQL fallbacks instead of scattering them across later tickets |
| Deterministic rendering or alias-renaming bugs produce misleading local context | Medium | Centralize rendering/verification in [M1-2](#m1-2---manifest-lock-and-rendering-primitives) and cover rename/threading cases in [M2-2](#m2-2---ticket-fetch-normalization-and-render-pipeline) |
| Interrupted runs still leave a partially updated directory at snapshot scope in v1 | Medium | Preserve atomic per-file writes, document the limitation clearly, and keep stronger directory-level atomicity deferred to [FW-3](future-work.md#fw-3-whole-snapshot-atomic-commit) |

---

## 10. Notes

- This active plan was promoted from the reviewed Stage 3 draft on 2026-03-17
  under
  [docs/policies/common/planning-model.md](policies/common/planning-model.md).
  The activation review record remains in
  [docs/planning/implementation-plan-review.md](planning/implementation-plan-review.md).
- The active plan was materially amended on 2026-03-18 by accepting and
  applying
  [docs/planning/change-requests/CR-26.03.18.md](planning/change-requests/CR-26.03.18.md).
- If future work currently deferred in
  [docs/future-work.md](future-work.md)
  is pulled into this release, treat that as a material planning change rather
  than silently adding scope during implementation.
