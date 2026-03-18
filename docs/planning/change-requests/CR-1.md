# CR-1 - Split the Refresh-Contract Amendment out of M1-D1

> **Status**: Stage 1 draft
> **Target active plan**:
> [docs/implementation-plan.md](../../implementation-plan.md)
> **Governing process**:
> [docs/policies/common/planning-model.md](../../policies/common/planning-model.md)

## Candidate Sources Consulted

- [docs/implementation-plan.md](../../implementation-plan.md)
- [docs/execution/M1-D1.md](../../execution/M1-D1.md)
- [docs/design/refresh-freshness-validation.md](../../design/refresh-freshness-validation.md)
- [docs/design/0-top-level-design.md](../../design/0-top-level-design.md#62-refresh-flow)
- [docs/adr.md](../../adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior)

## Candidate Decisions

| Candidate | Decision | Result | Rationale |
| --- | --- | --- | --- |
| Expand [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) so the same ticket both validates the release gate and rewrites the governing refresh design | Drop | Keep [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) as the spike/outcome-recording ticket only | The active-plan text for [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) says it records whether issue-level `updated_at` is sufficient and, if not, the exact amendment needed. The detailed notes then say a failing result should route through a plan amendment before [M3-1](../../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery) begins. |
| Add a follow-on Milestone 1 design ticket that owns the actual refresh-contract rewrite after [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) | Keep | Add `M1-D3 - Refresh composite freshness contract amendment` | This keeps the spike/result ticket separate from the governing-design amendment and makes the post-spike design work explicit, reviewable, and dependency-visible. |
| Leave [M1-D2](../../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) unchanged even though the refresh contract it must audit has changed | Drop | Update [M1-D2](../../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) so it depends on the new design amendment | The adapter audit should enumerate the operations required by the settled refresh contract, not by the invalidated single-cursor assumption. |
| Keep [M3-1](../../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery) directly gated on [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) alone | Drop | Gate [M3-1](../../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery) on the new amendment ticket instead | [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) proves the old design is insufficient. [M3-1](../../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery) needs the replacement contract, not just the proof that a replacement is needed. |

## Proposed Amendment Summary

If accepted, this amendment would:

1. Add a new Milestone 1 design ticket, `M1-D3`, that owns the actual refresh
   design extension required after the negative [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike)
   result.
2. Clarify that [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike)
   stops at recording the spike result and the minimum amendment shape; it does
   not itself rewrite the governing refresh design.
3. Re-sequence [M1-D2](../../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary)
   so its refresh-operation audit uses the amended design contract rather than
   the invalidated single-cursor assumption.
4. Gate [M3-1](../../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery)
   on the new design-amendment ticket instead of treating the spike ticket as
   sufficient by itself.

## Proposed Active-Plan Changes

<a id="cr-1-proposed-m1-d3"></a>

### 1. Add a new Milestone 1 design ticket

Add this row to the Milestone 1 design-ticket table in
[docs/implementation-plan.md](../../implementation-plan.md):

| # | Status | Ticket | Deliverable | Dependencies | Reviewers | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `M1-D3` | Planned | Refresh composite freshness contract amendment | A governing design amendment that replaces the single issue-level `updated_at` refresh assumption with the v1 per-ticket composite freshness contract required after [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike), including the exact comment-change signal to support comment creation and comment edits, the required local freshness metadata/comparison contract, and the explicit v1 disposition for attachments and relations | [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) | Independent Stage 2 review session | [docs/design/refresh-freshness-validation.md](../../design/refresh-freshness-validation.md), [docs/design/0-top-level-design.md](../../design/0-top-level-design.md#62-refresh-flow), [OQ-1](../../adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior) |

### 2. Add detailed notes for `M1-D3`

Add a new detailed-ticket subsection with points in this shape:

- Rewrite the governing refresh design in
  [docs/design/0-top-level-design.md](../../design/0-top-level-design.md#62-refresh-flow)
  so `refresh` no longer relies on issue-level `updated_at` as the sole
  freshness cursor.
- Define the minimum v1 composite freshness contract needed to detect comment
  creation and comment edits before a ticket is treated as fresh.
- Decide and document the v1 handling for persisted attachments and relations:
  either prove the parent issue cursor is sufficient for them or include them
  in the same composite freshness design.
- Record the exact remote data requirements that
  [M1-D2](../../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary)
  must audit so the adapter-boundary ticket can settle the final Linear
  operation set against the amended contract rather than the invalidated one.

### 3. Narrow `M1-D1` to spike-and-record scope

Amend the detailed notes for
[M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike)
so they explicitly say:

- if the issue-level `updated_at` contract fails, [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike)
  records the evidence and the minimum amendment shape, but the governing
  refresh-design rewrite is performed in [M1-D3](#cr-1-proposed-m1-d3) rather
  than inside the spike ticket itself.

### 4. Re-sequence `M1-D2`

Update [M1-D2](../../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary)
to depend on
[M1-D3](#cr-1-proposed-m1-d3).

Adjust its deliverable and notes so the refresh portion reads as an audit of
the operations required by the amended composite-freshness design, not just the
original batched `updated_at` query.

### 5. Re-gate `M3-1`

Update [M3-1](../../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery)
so its refresh-design dependency is
[M1-D3](#cr-1-proposed-m1-d3)
rather than [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike).

Update the Milestone 3 preface and the [M3-1](../../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery)
detailed notes so they refer to the amended refresh contract rather than only
to the release-gate spike.

### 6. Update cross-plan wording

If accepted, update the following active-plan text so the new ownership is
clear:

- Milestone 1 exit criteria: replace "any blocking amendment is visible" with
  wording that requires the blocking amendment to be owned by a named design
  artifact before incremental refresh work starts.
- Milestone 2 note that currently says no additional design tickets are needed
  once [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike)
  settles the release gate; revise it so Milestone 2 stays on the adopted
  design and does not reopen the refresh contract outside
  [M1-D3](#cr-1-proposed-m1-d3).
- Risk register mitigation for [OQ-1](../../adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior):
  revise it so the mitigation chain is [M1-D1](../../implementation-plan.md#m1-d1---refresh-freshness-validation-spike)
  for validation plus [M1-D3](#cr-1-proposed-m1-d3)
  for the governing design response.

## Why This Amendment Fits the Planning Model

This is a material amendment under
[docs/policies/common/planning-model.md](../../policies/common/planning-model.md#5-material-amendments)
because it adds a named plan item and changes ticket dependencies in a way that
changes delivery shape. Drafting it as a planning change request keeps the live
plan stable until an explicit review/acceptance step decides whether to promote
the amendment into [docs/implementation-plan.md](../../implementation-plan.md).

## Drafting Notes

- This change request does **not** modify the active plan yet.
- If you accept this direction, the next step is an independent Stage 2 review
  of this change request, followed by an owner response and then promotion of
  the accepted amendment into [docs/implementation-plan.md](../../implementation-plan.md).
