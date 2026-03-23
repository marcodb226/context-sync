# Review: [M4-R1](../implementation-plan.md#m4-r1---cli-interface-review)

> **Status**: Phase B complete (one review pass)
> **Plan ticket**:
> [M4-R1](../implementation-plan.md#m4-r1---cli-interface-review)
> **Execution record**:
> [docs/execution/M4-R1.md](M4-R1.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/design-review.md](../policies/common/reviews/design-review.md),
> [docs/policies/common/cli-conventions.md](../policies/common/cli-conventions.md),
> [docs/policies/common/python/cli-conventions.md](../policies/common/python/cli-conventions.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#2-cli-interface),
> [README.md](../../README.md),
> [src/context_sync/_cli.py](../../src/context_sync/_cli.py),
> [src/context_sync/_sync.py](../../src/context_sync/_sync.py)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M4-R1-R1 | High | Todo | Deliverable Completeness | The plan ticket explicitly requires that the deliverable "must include expanded user-facing documentation (in [README.md](../../README.md) and/or a dedicated operator guide) that explains when to use each command, what each interface does under the hood, and why the distinctions exist, or, if the surface is simplified, documents the new simpler model." The execution artifact delivers a recommendation to simplify but does not produce any updated user-facing documentation. The follow-on tracking section says a plan amendment is required before implementation, but even without implementation the ticket scope calls for documentation that explains the current surface or the proposed future surface to operators. | [docs/implementation-plan.md:558-563](../implementation-plan.md#L558), [docs/execution/M4-R1.md:229-237](M4-R1.md#L229), [README.md:71-90](../../README.md#L71) | The ticket's primary operator-comprehension deliverable is missing. Operators still see the same five-command listing without guidance on when to use `sync` vs `add`, which was the exact confusion the review was supposed to resolve for them. The review identifies the problem clearly but leaves the user-facing artifact unchanged. | Either update [README.md](../../README.md) with interim documentation that explains the current surface and guides operators on when to use each command (even if the simplification has not yet landed), or record a clear deferral with the exact follow-on ticket/amendment that will deliver the documentation. Do not leave the plan requirement unaddressed. |
| M4-R1-R2 | Medium | Todo | Follow-on Tracking | The review's "Follow-on tracking required before implementation" section (§ lines 229-257) lists seven items that must be addressed through a plan amendment, but the execution artifact does not draft the amendment, file it, or name the plan-item ID that will carry it. The execution model's review-ticket follow-on tracking rule (§4.5 rule 3) requires that new work not already tracked be routed through the planning model as separate follow-on tickets or future-work items. The plan detailed notes for [M4-R1](../implementation-plan.md#m4-r1---cli-interface-review) reinforce this: "add it as one or more follow-on tickets through a plan amendment rather than silently widening a `Done` ticket or leaving the recommendation only in the review artifact." Only [FW-9](../future-work.md#fw-9-scoped-diff-targets) was actually exported. | [docs/execution/M4-R1.md:229-257](M4-R1.md#L229), [docs/implementation-plan.md:564-570](../implementation-plan.md#L564), [docs/future-work.md:236-269](../../docs/future-work.md#L236), [docs/policies/common/execution-model.md:218](../policies/common/execution-model.md#L218) | The core recommendation (remove `add`, rename `remove-root` to `remove`, unify CLI placeholder) is stranded in the review artifact with no durable plan-level tracking. A future planner must discover it by reading this review artifact rather than finding it in the implementation plan or future-work artifact where it would be actionable. | Draft the plan amendment or create a concrete future-work entry for the CLI simplification and route the seven enumerated items into the planning model before closing Phase A. |
| M4-R1-R3 | Medium | Todo | Scope Gap | The plan detailed notes ask the review to "evaluate `remove-root` vs a potential `sync --remove TICKET` or `unsync TICKET` surface." The execution artifact's §4 ("Root removal should stay explicit") evaluates `sync --remove` and rejects it, which is good. However, the `unsync` alternative is not discussed at all. The plan note asked for both to be evaluated. | [docs/implementation-plan.md:552-553](../implementation-plan.md#L552), [docs/execution/M4-R1.md:136-151](M4-R1.md#L136) | Minor scope gap. The omission does not undermine the overall recommendation (the `remove` rename is well-reasoned), but the plan explicitly requested an `unsync` evaluation and a strict review should note it was not delivered. | Add a brief paragraph to the review conclusions explaining why `unsync` was or was not considered and why `remove` is preferred over `unsync`. |
| M4-R1-R4 | Medium | Todo | Design Completeness | The review recommends that `sync <TICKET>` on an existing snapshot "should reconcile the full tracked set plus the supplied ticket, not only the new ticket's neighborhood." The current [ContextSync.sync()](../../src/context_sync/_sync.py#L290) already does this: it adds the root, loads all roots, and recomputes the full reachable graph. The review does not acknowledge that the current implementation already satisfies this requirement, which could mislead a downstream implementer into thinking new library work is needed. Separately, the review recommends that `sync` subsume `add`'s role but does not address the traversal-configuration persistence gap: `sync` accepts and persists `--max-tickets-per-root` and `--depth-*` overrides ([src/context_sync/_cli.py:416-424](../../src/context_sync/_cli.py#L416)), while `add` deliberately uses the manifest's existing configuration. If `sync` becomes the only root-expanding command, the review should explicitly state whether a bare `sync TICKET` (no overrides) should preserve existing manifest configuration or whether every `sync` call should allow overrides. | [docs/execution/M4-R1.md:106-111](M4-R1.md#L106), [src/context_sync/_sync.py:290-310](../../src/context_sync/_sync.py#L290), [src/context_sync/_cli.py:407-424](../../src/context_sync/_cli.py#L407), [docs/execution/M4-R1.md:73-84](M4-R1.md#L73) | An implementer reading only the review recommendation could misunderstand the current state and do redundant work on the reconciliation behavior, while the more consequential question (what happens to traversal-config persistence when overrides are not supplied) is left open. | Clarify that the current `sync` already reconciles all roots, and explicitly address the traversal-configuration-persistence semantics for the unified `sync` command. This is needed before the plan amendment can be properly scoped. |
| M4-R1-R5 | Low | Todo | Execution Artifact Structure | The execution file status header reads "Phase A complete; pending independent Phase B review" but the implementation-plan row for [M4-R1](../implementation-plan.md#m4-r1---cli-interface-review) still says `In progress`. The execution model §4.1 rule 9 says the execution file status header should be updated to reflect Phase A completion, and §4.1 rule 2 says the plan row should be updated. There is a minor inconsistency: the execution file says Phase A is complete but the plan row was never advanced past `In progress`. Per the execution model, the plan row should stay `In progress` until post-review closeout, so the plan row is actually correct, but the execution file header is slightly misleading about the actual lifecycle state. | [docs/execution/M4-R1.md:3](M4-R1.md#L3), [docs/implementation-plan.md:499](../implementation-plan.md#L499) | Low. The inconsistency is cosmetic and does not affect the substantive review. | No action needed; the plan row `In progress` is the correct status per the execution model. |
| M4-R1-R6 | Low | Todo | Cross-Reference Completeness | The review's policy-fit assessment table at [M4-R1.md:197-206](M4-R1.md#L197) is thorough for the common CLI policy modules but does not evaluate the Python CLI conventions module's `Package Identity` requirement. The execution artifact's "Review references read" list includes [docs/policies/common/python/cli-conventions.md](../policies/common/python/cli-conventions.md) but the policy-fit table omits an explicit row for it. The current implementation does comply (version is sourced from [src/context_sync/version.py](../../src/context_sync/version.py) and [pyproject.toml](../../pyproject.toml) derives it dynamically), so this is a documentation gap in the review rather than a missed violation. | [docs/execution/M4-R1.md:197-206](M4-R1.md#L197), [docs/policies/common/python/cli-conventions.md](../policies/common/python/cli-conventions.md), [src/context_sync/version.py](../../src/context_sync/version.py), [pyproject.toml](../../pyproject.toml) | Minor completeness gap in the policy-fit assessment. No actual policy violation. | Add a row to the policy-fit assessment table for the Python CLI conventions `Package Identity` requirement, confirming compliance. |

## Reviewer Notes

- Review scope: I reviewed [docs/execution/M4-R1.md](M4-R1.md) as a review-ticket
  execution artifact, verifying it against the plan scope at
  [docs/implementation-plan.md:521-570](../implementation-plan.md#L521), the
  execution model's review-ticket requirements (§4.5), the design review
  checklist at
  [docs/policies/common/reviews/design-review.md](../policies/common/reviews/design-review.md),
  and the actual source code at
  [src/context_sync/_cli.py](../../src/context_sync/_cli.py) and
  [src/context_sync/_sync.py](../../src/context_sync/_sync.py).
- I used the M4-1 and M4-2 review artifacts
  ([docs/execution/M4-1-review.md](M4-1-review.md),
  [docs/execution/M4-2-review.md](M4-2-review.md)) as additional context since
  M4-R1 explicitly references them as inputs.
- The substantive CLI analysis in the execution artifact is strong. The
  identification of `add` as the least coherent command, the reasoning for
  keeping `refresh` separate, and the argument for explicit destructive verbs
  are all well-grounded in the source code and design documents. The core
  recommendation (four-command surface) is sound.
- The primary gap is operational: the review identifies the right problems and
  proposes the right solution, but the plan-level follow-through is incomplete.
  The documentation deliverable required by the plan is missing
  ([M4-R1-R1](#m4-r1-r1)), and the follow-on work is not routed into the
  planning model ([M4-R1-R2](#m4-r1-r2)).
- I independently verified the policy-fit claims against the shipped parser at
  [src/context_sync/_cli.py](../../src/context_sync/_cli.py) and confirmed
  compliance with the reserved flags, output mode, logging, and help output
  conventions. The one omission is the Python-specific package identity module
  ([M4-R1-R6](#m4-r1-r6)), which is compliant but not explicitly recorded.
- The [FW-9](../future-work.md#fw-9-scoped-diff-targets) export is well-formed:
  the future-work entry has the required structure, a references section linking
  back to this execution artifact, and the execution artifact links forward to
  the FW entry. No issue there.
- I did not rerun the repository lint, format, or test commands. The M4-R1
  change set is docs-only (execution artifact, future-work entry, plan-row
  status update), and the validation-scope gate says not to run repo-wide
  validation for docs-only changes unless explicitly requested.

## Residual Risks and Testing Gaps

- The biggest residual risk is that the CLI simplification recommendation
  remains stranded in the review artifact without plan-level tracking. If the
  amendment is not filed before the next planning pass, the recommendation may
  be lost or rediscovered too late.
- The user-facing documentation gap ([M4-R1-R1](#m4-r1-r1)) means operators
  still lack guidance on the `sync` vs `add` distinction today. Even if the
  simplification lands soon, the interim state is confusing.
- The traversal-configuration-persistence question ([M4-R1-R4](#m4-r1-r4)) is
  a design decision that must be resolved before the plan amendment can be
  properly scoped. Getting it wrong could change the `sync` command's behavior
  in a way that surprises existing users.
