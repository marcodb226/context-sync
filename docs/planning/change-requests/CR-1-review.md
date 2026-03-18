# Review: [CR-1](CR-1.md)

> **Status**: Stage 2 review complete
> **Reviewed change request**:
> [docs/planning/change-requests/CR-1.md](CR-1.md)
> **Target active plan**:
> [docs/implementation-plan.md](../../implementation-plan.md)
> **Governing process**:
> [docs/policies/common/planning-model.md](../../policies/common/planning-model.md)
> **Reviewer references**:
> [docs/policies/common/planning-model.md](../../policies/common/planning-model.md),
> [docs/policies/common/reviews/design-review.md](../../policies/common/reviews/design-review.md),
> [docs/implementation-plan.md](../../implementation-plan.md),
> [docs/execution/M1-D1.md](../../execution/M1-D1.md),
> [docs/design/refresh-freshness-validation.md](../../design/refresh-freshness-validation.md),
> [docs/adr.md](../../adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior)

This review was performed as the independent Stage 2 review pass for the draft
change request.

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CR-1-R1 | Medium | Todo | Plan Consistency | The amendment re-scopes [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) to stop at the spike result and leave the replacement refresh contract to a new [M1-D3](CR-1.md#cr-1-proposed-m1-d3), but it only proposes changing the detailed notes. It does not also rewrite the main Milestone 1 design-ticket table row that currently says [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) records the exact amendment needed. | [docs/implementation-plan.md:143](../../implementation-plan.md), [docs/planning/change-requests/CR-1.md:33](CR-1.md), [docs/planning/change-requests/CR-1.md:74](CR-1.md) | If promoted as written, the active plan will still describe [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) as owning the exact refresh amendment while [M1-D3](CR-1.md#cr-1-proposed-m1-d3) is introduced to own that same work. That leaves ticket ownership internally contradictory at the main planning table where later sessions are most likely to look first. | Add an explicit active-plan edit that rewrites the Milestone 1 design-ticket table row for [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike), and update any matching summary wording, so the table and detailed notes agree that [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) is the validation spike while [M1-D3](CR-1.md#cr-1-proposed-m1-d3) owns the replacement refresh contract. |

## Reviewer Notes

- The core amendment direction is sound. The negative
  [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike)
  result means the active plan needs a named follow-on design artifact before
  [M3-1](../../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery)
  can proceed, and [CR-1](CR-1.md) makes that dependency explicit instead of
  leaving it in chat or reviewer notes.
- Re-sequencing
  [M1-D2](../../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary)
  behind the new amendment ticket is reasonable because the adapter audit is
  supposed to reflect the settled refresh contract, not the invalidated
  single-cursor design. Evidence:
  [docs/implementation-plan.md:183](../../implementation-plan.md),
  [docs/planning/change-requests/CR-1.md:85](CR-1.md).
- The proposed [M1-D3](CR-1.md#cr-1-proposed-m1-d3) scope is appropriately
  concrete: it assigns ownership for the comment freshness signal, the local
  comparison contract, and the explicit attachment/relation disposition that
  the spike ticket left unresolved. Evidence:
  [docs/planning/change-requests/CR-1.md:52](CR-1.md),
  [docs/planning/change-requests/CR-1.md:60](CR-1.md).

## Residual Risks and Testing Gaps

- If the owner accepts this change request, the promoted active-plan edit
  should also be checked for any stale blocker text that still treats
  [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike)
  as the sole refresh gate.
- This was planning-only review work, so no repository lint, format, or test
  commands were run.

---

## Second Review Pass

> **Reviewer**: Independent second-pass review session
> **Date**: 2026-03-18
> **Prior review status**: Stage 2 review complete (first pass)

This pass was requested as an additional independent review of
[CR-1](CR-1.md).

### Additional Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CR-1-R2 | Low | Todo | Sequencing | [CR-1](CR-1.md) proposes making [M1-D2](../../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) depend on [M1-D3](CR-1.md#cr-1-proposed-m1-d3), which in turn depends on [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike). This creates a strictly serial design chain: [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) (finish Phase C) then [M1-D3](CR-1.md#cr-1-proposed-m1-d3) (full Phase A/B/C) then [M1-D2](../../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) then [M1-1](../../implementation-plan.md#m1-1---project-scaffold-and-public-runtime-contracts) then [M1-2](../../implementation-plan.md#m1-2---manifest-lock-and-rendering-primitives). The non-refresh portions of [M1-D2](../../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) (traversal operations, fetch operations, relation discovery) do not inherently need the amended freshness contract. | [docs/planning/change-requests/CR-1.md:85-93](CR-1.md), [docs/implementation-plan.md:144](../../implementation-plan.md) | The Milestone 1 design phase becomes fully serial, potentially delaying [M1-1](../../implementation-plan.md#m1-1---project-scaffold-and-public-runtime-contracts) and all downstream implementation work. | Consider whether [M1-D2](../../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) could begin concurrently with [M1-D3](CR-1.md#cr-1-proposed-m1-d3) for its non-refresh scope, with a clearly scoped "pending [M1-D3](CR-1.md#cr-1-proposed-m1-d3)" annotation for the refresh-operation portion. Alternatively, accept the serialization as a reasonable tradeoff for audit coherence and note that [M1-D2](../../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) is expected to be a short-duration design ticket once its input is settled. |
| CR-1-R3 | Low | Todo | Requirements Fit | [CR-1](CR-1.md) proposes that [M1-D3](CR-1.md#cr-1-proposed-m1-d3) should "Rewrite the governing refresh design in [docs/design/0-top-level-design.md](../../design/0-top-level-design.md)" but does not specify whether the ADR's section 6.1 refresh strategy prose ([docs/adr.md](../../adr.md), lines 361-379) also needs amendment under [M1-D3](CR-1.md#cr-1-proposed-m1-d3), or whether the existing [OQ-1](../../adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior) annotation is sufficient for the ADR. | [docs/planning/change-requests/CR-1.md:60-62](CR-1.md), [docs/adr.md:361-379](../../adr.md), [docs/adr.md:457-465](../../adr.md) | The ADR's section 6.1 will continue to describe the single-cursor batched `updated_at` design as the refresh strategy while the top-level design describes the composite-freshness replacement. The ADR already marks the design as provisional and the [OQ-1](../../adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior) annotation records the failure, but a reader consulting only section 6.1 without reaching the OQ-1 annotation may misread the strategy text as still active. | Clarify in [M1-D3](CR-1.md#cr-1-proposed-m1-d3)'s detailed notes whether the ticket should also amend the ADR's section 6.1 refresh strategy text, or whether the [OQ-1](../../adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior) annotation plus the top-level design rewrite is sufficient. |

### Second-Pass Reviewer Notes

- The first-pass finding
  [CR-1-R1](CR-1-review.md)
  remains valid and important. The
  [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike)
  design-ticket table row must be updated alongside the detailed notes to avoid
  internal contradiction in the active plan. This second pass concurs with that
  assessment.
- The core amendment direction is sound and well-motivated. Creating
  [M1-D3](CR-1.md#cr-1-proposed-m1-d3) as a separate design ticket rather than
  expanding
  [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike)
  respects the spike ticket's intended scope and makes the design work
  independently reviewable.
- The candidate decisions table in [CR-1](CR-1.md) is thorough: each
  alternative was considered and the rationale for keep/drop is clear and
  traceable.
- Re-gating
  [M3-1](../../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery)
  on [M1-D3](CR-1.md#cr-1-proposed-m1-d3) rather than on
  [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike)
  alone is the right call. The spike proves the old design is broken;
  [M3-1](../../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery)
  needs the replacement contract, not just the proof that one is needed.
- The proposed cross-plan wording updates (Section 6 of [CR-1](CR-1.md)) are
  appropriate and cover the key locations: M1 exit criteria, M2 preface, and
  risk register mitigation.
- The [M1-D3](CR-1.md#cr-1-proposed-m1-d3) deliverable scope is appropriately
  concrete: comment freshness signal, local comparison contract, and explicit
  attachment/relation disposition.

### Second-Pass Residual Risks

- If [CR-1-R2](#additional-findings-1) serialization is accepted as-is, the M1
  design phase becomes a four-ticket serial chain
  ([M1-O1](../../implementation-plan.md#m1-o1---live-linear-validation-environment-available)
  then
  [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike)
  then [M1-D3](CR-1.md#cr-1-proposed-m1-d3) then
  [M1-D2](../../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary))
  before any implementation work can begin. This is a timeline concern, not a
  correctness concern.
- This was planning-only review work, so no repository lint, format, or test
  commands were run.
