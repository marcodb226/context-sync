# Review: [M1-D1](../implementation-plan.md#m1-d1---refresh-freshness-validation-spike)

> **Status**: Phase B complete
> **Plan ticket**:
> [M1-D1](../implementation-plan.md#m1-d1---refresh-freshness-validation-spike)
> **Execution record**:
> [docs/execution/M1-D1.md](M1-D1.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/design-review.md](../policies/common/reviews/design-review.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/adr.md](../adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#62-refresh-flow),
> [docs/design/refresh-freshness-validation.md](../design/refresh-freshness-validation.md),
> [docs/planning/change-requests/CR-26.03.18.md](../planning/change-requests/CR-26.03.18.md)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M1-D1-R1 | Medium | Deferred (Milestone 1) | Requirements Fit | The spike result proves that issue-level `updated_at` is insufficient, but the repository artifact still stops at a minimum amendment shape and leaves attachment/relation freshness as an unresolved either-or even though the active plan says [M1-D1](../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) should record the exact amendment needed before `refresh` work proceeds. | [docs/implementation-plan.md:143](../implementation-plan.md), [docs/execution/M1-D1.md:88](M1-D1.md), [docs/execution/M1-D1.md:94](M1-D1.md), [docs/design/refresh-freshness-validation.md:74](../design/refresh-freshness-validation.md) | Later readers can treat [M1-D1](../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) as having settled the full refresh-contract amendment even though two v1-persisted field groups still need either additional validation or an explicit design decision. That leaves the precondition for [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery) ambiguous until a follow-on plan/design update lands. | Either extend the repository artifact so it states the accepted v1 amendment for attachments and relations, or accept a plan amendment that explicitly re-scopes [M1-D1](../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) and assigns the remaining contract work to a follow-on ticket before treating the design gate as fully settled. |

## Reviewer Notes

- The live evidence recorded in
  [docs/design/refresh-freshness-validation.md](../design/refresh-freshness-validation.md)
  is otherwise convincing for the core release-gate question: positive-control
  issue-field edits advanced `updatedAt`, while comment creation and comment
  edit did not, including the delayed follow-up probe. Evidence:
  [docs/design/refresh-freshness-validation.md:35](../design/refresh-freshness-validation.md),
  [docs/design/refresh-freshness-validation.md:44](../design/refresh-freshness-validation.md),
  [docs/execution/M1-D1.md:45](M1-D1.md),
  [docs/execution/M1-D1.md:51](M1-D1.md).
- The execution record correctly captures the intended scope boundary and routes
  the governing design rewrite through the planning workspace rather than
  silently widening the Phase A deliverable. Supporting context:
  [docs/execution/M1-D1.md:93](M1-D1.md),
  [docs/planning/change-requests/CR-26.03.18.md](../planning/change-requests/CR-26.03.18.md).
- I did not find any evidence that secrets or credential values were written
  into the repository artifacts. The ticket records probe behavior and probe
  issue cleanup, but not sensitive runtime material. Evidence:
  [docs/execution/M1-D1.md:111](M1-D1.md),
  [docs/execution/M1-D1.md:124](M1-D1.md).

## Residual Risks and Testing Gaps

- Attachment and relation freshness still need an accepted repository-level
  contract before
  [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery)
  can implement `refresh` correctly.
- This was a docs-only design ticket, so there was no repository-wide
  lint/format/test gate to rerun during review. The review relied on
  cross-document consistency plus the recorded live-probe evidence.

---

## Second Review Pass

> **Reviewer**: Independent second-pass review session
> **Date**: 2026-03-18
> **Prior review status**: Phase B complete (first pass)

This pass was requested as an additional independent Phase B review of
[M1-D1](../implementation-plan.md#m1-d1---refresh-freshness-validation-spike).

### Additional Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M1-D1-R2 | Low | Deferred (Milestone 1) | Testing and Validation | The spike probed only 2 of the 4 v1-persisted field categories against `updatedAt`: metadata (title/description) as positive controls and comments (create/edit) as the release-gate discriminator. Attachments and relations were not probed. The design artifact's recommendation for those fields ("either validate that their changes advance the parent issue `updatedAt` or include freshness signals for them") is therefore based on structural reasoning rather than empirical evidence. | [docs/design/refresh-freshness-validation.md:19-24](../design/refresh-freshness-validation.md), [docs/design/refresh-freshness-validation.md:76-81](../design/refresh-freshness-validation.md), [docs/execution/M1-D1.md:47-49](M1-D1.md) | When [M1-D3](../planning/change-requests/CR-26.03.18.md#cr-26.03.18-proposed-m1-d3) (via [CR-26.03.18](../planning/change-requests/CR-26.03.18.md)) designs the composite freshness contract, it will need to either run additional live probes for attachments and relations or make a conservative design choice to include them in the composite signal without empirical confirmation. Neither path is blocked, but the design artifact does not flag this as an explicit input for the follow-on ticket. | If [CR-26.03.18](../planning/change-requests/CR-26.03.18.md) is accepted, consider noting in [M1-D3](../planning/change-requests/CR-26.03.18.md#cr-26.03.18-proposed-m1-d3)'s detailed ticket notes that empirical attachment/relation probing is a recommended input, not just the disposition decision. |

### Second-Pass Reviewer Notes

- The first-pass finding
  [M1-D1-R1](M1-D1-review.md)
  remains the primary concern from this ticket. The deliverable gap between the
  plan table row's "exact amendment needed" language and the actual "minimum
  amendment shape" delivered is real but is being addressed through the
  [CR-26.03.18](../planning/change-requests/CR-26.03.18.md) amendment path. This second pass
  concurs with that assessment.
- The probe methodology is sound: using disposable issues, positive controls
  first, then the release-gate discriminator, with a delayed follow-up to rule
  out stale reads. The evidence table in
  [docs/design/refresh-freshness-validation.md:42-48](../design/refresh-freshness-validation.md)
  is unambiguous.
- The scope boundary is correctly drawn. The ticket notes in
  [docs/implementation-plan.md:179-181](../implementation-plan.md) say to "stop
  and route that change through a plan amendment before
  [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery)
  begins," and the execution record does exactly that by creating
  [CR-26.03.18](../planning/change-requests/CR-26.03.18.md) rather than silently extending
  the spike into a design rewrite.
- The design artifact at
  [docs/design/refresh-freshness-validation.md](../design/refresh-freshness-validation.md)
  is well-structured: clear scope, reproducible probe method, tabular evidence,
  unambiguous outcome, and actionable amendment requirements.
- The ADR
  [OQ-1](../adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior)
  annotation correctly records the validation outcome with a forward reference
  to the design artifact. The ADR's main refresh strategy prose (section 6.1)
  already describes itself as provisional pending this validation, so the
  combination of the existing caveat and the OQ-1 annotation is sufficient for
  now. The governing design rewrite belongs to
  [M1-D3](../planning/change-requests/CR-26.03.18.md#cr-26.03.18-proposed-m1-d3).
- No secrets or credential values were found in the repository artifacts. The
  probe issues were archived after use.

### Second-Pass Residual Risks

- The first-pass residual risk (attachment/relation freshness contract needed
  before
  [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery))
  remains.
  [CR-26.03.18](../planning/change-requests/CR-26.03.18.md) acceptance and
  [M1-D3](../planning/change-requests/CR-26.03.18.md#cr-26.03.18-proposed-m1-d3) execution
  are the resolution path.
- [M1-D1-R2](#additional-findings) adds a minor gap: when
  [M1-D3](../planning/change-requests/CR-26.03.18.md#cr-26.03.18-proposed-m1-d3) designs the
  composite contract, it will need to decide whether to run live probes for
  attachments/relations or to conservatively include them without probing. That
  decision should be explicit in the
  [M1-D3](../planning/change-requests/CR-26.03.18.md#cr-26.03.18-proposed-m1-d3) execution
  record.

## Ticket Owner Response

| ID | Verdict | Rationale |
| --- | --- | --- |
| M1-D1-R1 | Defer to Milestone 1 | The scope-boundary concern is valid, but the chosen resolution path is now explicit: [docs/execution/M1-D1.md](M1-D1.md) states that [M1-D1](../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) intentionally stopped at recording the failed assumption and minimum amendment shape, and the governing refresh-contract rewrite is being handled through the Milestone 1 planning amendment draft [docs/planning/change-requests/CR-26.03.18.md](../planning/change-requests/CR-26.03.18.md). The human has accepted that route in principle, so the remaining work belongs to the Milestone 1 plan-amendment flow rather than retroactively widening the completed spike ticket. |
| M1-D1-R2 | Defer to Milestone 1 | This is a real follow-on input for the amendment work, but not a reason to reopen the spike itself. If [docs/planning/change-requests/CR-26.03.18.md](../planning/change-requests/CR-26.03.18.md) is accepted, the resulting Milestone 1 design ticket should explicitly decide whether to run attachment/relation probes or to conservatively include those field groups in the composite freshness signal without additional live validation. |
