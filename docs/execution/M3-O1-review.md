# Review: [M3-O1](../implementation-plan.md#m3-o1---comments-signature-input-settlement)

> **Status**: Phase B complete
> **Plan ticket**:
> [M3-O1](../implementation-plan.md#m3-o1---comments-signature-input-settlement)
> **Execution record**:
> [docs/execution/M3-O1.md](M3-O1.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/reviews/design-review.md](../policies/common/reviews/design-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/adr.md](../adr.md#61-snapshot-consistency-contract),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#62-refresh-flow),
> [docs/design/linear-domain-coverage-audit.md](../design/linear-domain-coverage-audit.md),
> [docs/execution/M1-D2-review.md](M1-D2-review.md),
> [docs/execution/M1-D3-review.md](M1-D3-review.md)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M3-O1-R1 | Medium | Todo | Refresh Contract | The ticket accepts a concrete `deleted=<bool_or_unknown>` mapping for `comments_signature`, but the probe evidence only validates `updatedAt`, `resolvedAt`, and reply-parent behavior. There is no recorded behavioral probe for soft-archived comments or hard-deleted comments, even though the accepted decision now treats `archivedAt` as a reliable soft-delete signal and query absence as the operational meaning of `unknown`. That goes beyond what the recorded evidence actually proves. | [docs/execution/M3-O1.md:44](M3-O1.md#L44), [docs/execution/M3-O1.md:67](M3-O1.md#L67), [docs/execution/M3-O1.md:129](M3-O1.md#L129), [docs/adr.md:401](../adr.md#L401), [docs/design/0-top-level-design.md:427](../design/0-top-level-design.md#L427) | [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery) now risks implementing deleted-comment freshness as if it were fully settled when the repository only proved the edit / resolve / reply parts of the contract. If Linear omits archived comments from the query, delays archive visibility, or distinguishes hard delete from access loss differently than assumed here, refresh correctness for comment removal can still drift. | Either add one more probe covering soft archive and hard delete behavior and record the exact query outcome, or narrow the accepted decision to the validated subset and carry deletion handling forward as the ADR's documented best-effort case until that probe exists. |
| M3-O1-R2 | Low | Todo | Documentation Drift | `M3-O1` resolves the pre-[M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery) `comments_signature` gate, but the authoritative boundary audit in [docs/design/linear-domain-coverage-audit.md](../design/linear-domain-coverage-audit.md) still reads as if that gate is unresolved and does not point readers to the new accepted outcome. Because [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery) is explicitly told to use the [M1-D2](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) adapter contract, leaving that audit stale creates avoidable contradiction across the repository artifacts. | [docs/design/linear-domain-coverage-audit.md:111](../design/linear-domain-coverage-audit.md#L111), [docs/implementation-plan.md:392](../implementation-plan.md#L392), [docs/execution/M3-O1.md:107](M3-O1.md#L107), [docs/execution/M1-D2-review.md:23](M1-D2-review.md#L23) | A later implementer can read the audit artifact and conclude the gate is still open, re-run the same investigation, or treat the adapter-boundary prerequisites as unsettled even though the plan now marks [M3-O1](../implementation-plan.md#m3-o1---comments-signature-input-settlement) done. That is exactly the kind of cross-document drift this repo is trying to avoid. | Update [docs/design/linear-domain-coverage-audit.md](../design/linear-domain-coverage-audit.md) so its pre-[M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery) gate section points to the accepted [M3-O1](M3-O1.md) outcome, or fold the accepted field-availability decision directly into that audit. |

## Reviewer Notes

- The ticket does settle the core question that motivated it: the execution
  record now contains concrete live evidence that comment-level `updatedAt`
  exists in raw GraphQL and advances on body edit, resolve / unresolve, and
  child-reply creation. That meaningfully closes the main uncertainty carried
  forward from
  [M1-D2-R1](M1-D2-review.md#L23) and
  [M1-D3-R2](M1-D3-review.md#L87).
- The operational artifact is otherwise readable and useful for later work:
  it states the background, the chosen resolution path, the measured probe
  outcomes, the accepted decision, and the direct unblock for
  [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery).
- I did not rerun live probes during review. This was a docs-only operational
  review pass based on repository artifacts and cross-document consistency
  checks.

## Residual Risks and Testing Gaps

- The exact GraphQL query / mutation shapes used for schema introspection and
  the live probes are not recorded in-repo. The summary tables are helpful, but
  a later maintainer who needs to re-run the check will still need to recreate
  the probe mechanics from scratch.
- The accepted decision currently gives stronger guidance for deletion handling
  than the recorded probes support, which is why [M3-O1-R1](M3-O1-review.md#findings)
  matters even though the main `updatedAt` question is convincingly settled.
- No repository-wide automated validation was run for this review because the
  ticket deliverable is documentation / operational evidence rather than
  executable code.
