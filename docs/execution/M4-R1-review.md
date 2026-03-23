# Review: [M4-R1](../implementation-plan.md#m4-r1---cli-interface-review)

> **Status**: Phase C complete
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
| M4-R1-R1 | High | Done | Deliverable Completeness | The plan ticket explicitly requires that the deliverable "must include expanded user-facing documentation (in [README.md](../../README.md) and/or a dedicated operator guide) that explains when to use each command, what each interface does under the hood, and why the distinctions exist, or, if the surface is simplified, documents the new simpler model." The execution artifact delivers a recommendation to simplify but does not produce any updated user-facing documentation. The follow-on tracking section says a plan amendment is required before implementation, but even without implementation the ticket scope calls for documentation that explains the current surface or the proposed future surface to operators. | [docs/implementation-plan.md:558-563](../implementation-plan.md#L558), [docs/execution/M4-R1.md:229-237](M4-R1.md#L229), [README.md:71-90](../../README.md#L71) | The ticket's primary operator-comprehension deliverable is missing. Operators still see the same five-command listing without guidance on when to use `sync` vs `add`, which was the exact confusion the review was supposed to resolve for them. The review identifies the problem clearly but leaves the user-facing artifact unchanged. | Either update [README.md](../../README.md) with interim documentation that explains the current surface and guides operators on when to use each command (even if the simplification has not yet landed), or record a clear deferral with the exact follow-on ticket/amendment that will deliver the documentation. Do not leave the plan requirement unaddressed. |
| M4-R1-R2 | Medium | Done (FW-10) | Follow-on Tracking | The review's "Follow-on tracking required before implementation" section (§ lines 229-257) lists seven items that must be addressed through a plan amendment, but the execution artifact does not draft the amendment, file it, or name the plan-item ID that will carry it. The execution model's review-ticket follow-on tracking rule (§4.5 rule 3) requires that new work not already tracked be routed through the planning model as separate follow-on tickets or future-work items. The plan detailed notes for [M4-R1](../implementation-plan.md#m4-r1---cli-interface-review) reinforce this: "add it as one or more follow-on tickets through a plan amendment rather than silently widening a `Done` ticket or leaving the recommendation only in the review artifact." Only [FW-9](../future-work.md#fw-9-scoped-diff-targets) was actually exported. | [docs/execution/M4-R1.md:229-257](M4-R1.md#L229), [docs/implementation-plan.md:564-570](../implementation-plan.md#L564), [docs/future-work.md:236-269](../../docs/future-work.md#L236), [docs/policies/common/execution-model.md:218](../policies/common/execution-model.md#L218) | The core recommendation (remove `add`, rename `remove-root` to `remove`, unify CLI placeholder) is stranded in the review artifact with no durable plan-level tracking. A future planner must discover it by reading this review artifact rather than finding it in the implementation plan or future-work artifact where it would be actionable. | Draft the plan amendment or create a concrete future-work entry for the CLI simplification and route the seven enumerated items into the planning model before closing Phase A. |
| M4-R1-R3 | Medium | Done | Scope Gap | The plan detailed notes ask the review to "evaluate `remove-root` vs a potential `sync --remove TICKET` or `unsync TICKET` surface." The execution artifact's §4 ("Root removal should stay explicit") evaluates `sync --remove` and rejects it, which is good. However, the `unsync` alternative is not discussed at all. The plan note asked for both to be evaluated. | [docs/implementation-plan.md:552-553](../implementation-plan.md#L552), [docs/execution/M4-R1.md:136-151](M4-R1.md#L136) | Minor scope gap. The omission does not undermine the overall recommendation (the `remove` rename is well-reasoned), but the plan explicitly requested an `unsync` evaluation and a strict review should note it was not delivered. | Add a brief paragraph to the review conclusions explaining why `unsync` was or was not considered and why `remove` is preferred over `unsync`. |
| M4-R1-R4 | Medium | Done | Design Completeness | The review recommends that `sync <TICKET>` on an existing snapshot "should reconcile the full tracked set plus the supplied ticket, not only the new ticket's neighborhood." The current [ContextSync.sync()](../../src/context_sync/_sync.py#L290) already does this: it adds the root, loads all roots, and recomputes the full reachable graph. The review does not acknowledge that the current implementation already satisfies this requirement, which could mislead a downstream implementer into thinking new library work is needed. Separately, the review recommends that `sync` subsume `add`'s role but does not address the traversal-configuration persistence gap: `sync` accepts and persists `--max-tickets-per-root` and `--depth-*` overrides ([src/context_sync/_cli.py:416-424](../../src/context_sync/_cli.py#L416)), while `add` deliberately uses the manifest's existing configuration. If `sync` becomes the only root-expanding command, the review should explicitly state whether a bare `sync TICKET` (no overrides) should preserve existing manifest configuration or whether every `sync` call should allow overrides. | [docs/execution/M4-R1.md:106-111](M4-R1.md#L106), [src/context_sync/_sync.py:290-310](../../src/context_sync/_sync.py#L290), [src/context_sync/_cli.py:407-424](../../src/context_sync/_cli.py#L407), [docs/execution/M4-R1.md:73-84](M4-R1.md#L73) | An implementer reading only the review recommendation could misunderstand the current state and do redundant work on the reconciliation behavior, while the more consequential question (what happens to traversal-config persistence when overrides are not supplied) is left open. | Clarify that the current `sync` already reconciles all roots, and explicitly address the traversal-configuration-persistence semantics for the unified `sync` command. This is needed before the plan amendment can be properly scoped. |
| M4-R1-R5 | Low | Discarded | Execution Artifact Structure | The execution file status header reads "Phase A complete; pending independent Phase B review" but the implementation-plan row for [M4-R1](../implementation-plan.md#m4-r1---cli-interface-review) still says `In progress`. The execution model §4.1 rule 9 says the execution file status header should be updated to reflect Phase A completion, and §4.1 rule 2 says the plan row should be updated. There is a minor inconsistency: the execution file says Phase A is complete but the plan row was never advanced past `In progress`. Per the execution model, the plan row should stay `In progress` until post-review closeout, so the plan row is actually correct, but the execution file header is slightly misleading about the actual lifecycle state. | [docs/execution/M4-R1.md:3](M4-R1.md#L3), [docs/implementation-plan.md:499](../implementation-plan.md#L499) | Low. The inconsistency is cosmetic and does not affect the substantive review. | No action needed; the plan row `In progress` is the correct status per the execution model. |
| M4-R1-R6 | Low | Done | Cross-Reference Completeness | The review's policy-fit assessment table at [M4-R1.md:197-206](M4-R1.md#L197) is thorough for the common CLI policy modules but does not evaluate the Python CLI conventions module's `Package Identity` requirement. The execution artifact's "Review references read" list includes [docs/policies/common/python/cli-conventions.md](../policies/common/python/cli-conventions.md) but the policy-fit table omits an explicit row for it. The current implementation does comply (version is sourced from [src/context_sync/version.py](../../src/context_sync/version.py) and [pyproject.toml](../../pyproject.toml) derives it dynamically), so this is a documentation gap in the review rather than a missed violation. | [docs/execution/M4-R1.md:197-206](M4-R1.md#L197), [docs/policies/common/python/cli-conventions.md](../policies/common/python/cli-conventions.md), [src/context_sync/version.py](../../src/context_sync/version.py), [pyproject.toml](../../pyproject.toml) | Minor completeness gap in the policy-fit assessment. No actual policy violation. | Add a row to the policy-fit assessment table for the Python CLI conventions `Package Identity` requirement, confirming compliance. |

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

---

## Second Review Pass

> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/design-review.md](../policies/common/reviews/design-review.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#2-cli-interface),
> [docs/execution/M4-R1.md](M4-R1.md),
> [src/context_sync/_cli.py](../../src/context_sync/_cli.py),
> [src/context_sync/_diff.py](../../src/context_sync/_diff.py)

### Agreement with First Pass

I agree with [M4-R1-R1](#m4-r1-r1) through [M4-R1-R4](#m4-r1-r4). The first
pass correctly identified the missing user-facing documentation, the missing
plan-level follow-on tracking, the omitted `unsync` comparison, and the
underspecified unified-`sync` traversal semantics.

[M4-R1-R5](#m4-r1-r5) and [M4-R1-R6](#m4-r1-r6) remain low-severity artifact
completeness issues. I did not find new evidence that changes their
disposition. This second pass adds two more medium-severity findings.

### Additional Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M4-R1-R7 | Medium | Done | Output Ergonomics | The plan ticket explicitly requires this review to cover output ergonomics and operator comprehension, but the execution artifact limits itself to command overlap, policy-fit, and follow-on tracking. Its review method says it compared the parser/help contract, yet the artifact never evaluates the rendered top-level or subcommand help text, the human-readable success/failure surfaces, or the design-mandated `diff` lock-refusal message. The current terminal-facing help still leads with internal implementation wording such as "Full-snapshot sync" and "Incremental refresh", which is exactly the distinction the review says operators should not have to reason about. | [docs/implementation-plan.md:499](../implementation-plan.md#L499), [docs/implementation-plan.md:523–527](../implementation-plan.md#L523), [docs/execution/M4-R1.md:41–50](M4-R1.md#L41), [docs/execution/M4-R1.md:192–206](M4-R1.md#L192), [src/context_sync/_cli.py:408–465](../../src/context_sync/_cli.py#L408), [docs/design/0-top-level-design.md:134](../design/0-top-level-design.md#L134) | The ticket can close with a cleaner proposed verb model while leaving the actual in-terminal discovery and failure surfaces under-reviewed. Operators who rely on `context-sync --help` or lock-failure text could still see the old implementation-oriented story even after the plan-level simplification is accepted. | Add an explicit output-ergonomics section to [docs/execution/M4-R1.md](M4-R1.md) that evaluates rendered help output, human-readable success/failure text, and the `diff` lock-refusal wording. Classify any required follow-up as documentation-only clarification versus amendment-required command-surface work. |
| M4-R1-R8 | Medium | Discarded | Alternatives Analysis | The detailed ticket notes explicitly ask the review to evaluate whether the `sync`/`add` overlap should be resolved by a unified `sync` that is incremental when possible or by a factored surface such as `sync --full`. The execution artifact recommends removing `add`, but it never actually decides whether the full-vs-incremental distinction should stay entirely hidden or become an explicit operator choice; instead, it defers that question to a later plan amendment. That leaves one of the ticket's central requested tradeoff analyses unresolved. | [docs/implementation-plan.md:547–550](../implementation-plan.md#L547), [docs/execution/M4-R1.md:67–68](M4-R1.md#L67), [docs/execution/M4-R1.md:125–133](M4-R1.md#L125), [docs/execution/M4-R1.md:232–244](M4-R1.md#L232) | The future amendment still lacks the key semantic recommendation needed to scope the unified `sync` command: should operators ever see a `--full` concept, or should execution strategy remain entirely internal? Without that call, planners must reopen one of the core alternatives analyses that this review ticket was supposed to perform. | Extend [docs/execution/M4-R1.md](M4-R1.md) with a short alternatives subsection comparing hidden-strategy, `sync --full`, and current-model options, then recommend one explicitly so the amendment can carry a settled CLI contract. |

### Second-Pass Reviewer Notes

- Review scope: re-read [docs/execution/M4-R1.md](M4-R1.md) against the
  [M4-R1 detailed notes](../implementation-plan.md#L521), then inspected the
  actual operator-facing help and error surfaces in
  [src/context_sync/_cli.py](../../src/context_sync/_cli.py) and the `diff`
  lock-refusal contract in
  [src/context_sync/_diff.py](../../src/context_sync/_diff.py) plus
  [docs/design/0-top-level-design.md](../design/0-top-level-design.md#L134).
- I rendered the parser help from the repository virtualenv to verify what an
  operator actually sees, rather than relying only on static source reading.
- The first pass already covered the biggest execution-phase misses. This pass
  focused on whether the review ticket itself fully satisfied its stated scope.
- I did not rerun lint, format, or test commands. This review-pass update is a
  docs-only change to the review artifact, and the validation-scope gate says
  not to run repository-wide validation for docs-only review work unless
  explicitly requested.

### Second-Pass Residual Risks and Testing Gaps

- If Phase C addresses only [M4-R1-R1](#m4-r1-r1) through
  [M4-R1-R4](#m4-r1-r4), the operator-facing help and failure-text surfaces may
  still remain under-reviewed.
- The plan amendment for CLI simplification is likely to stall or reopen design
  debate unless [M4-R1-R8](#m4-r1-r8) is answered with an explicit recommendation
  about whether full-vs-incremental behavior should ever be user-visible.

## Ticket Owner Response

| ID | Verdict | Rationale |
| --- | --- | --- |
| [M4-R1-R1](#m4-r1-r1) | Fix now | The plan explicitly requires user-facing documentation. Add an interim "When to use each command" section to [README.md](../../README.md) that explains the current five-command surface and guides operators on `sync` vs `add`, even before the simplification lands. This satisfies the plan deliverable for the current surface. |
| [M4-R1-R2](#m4-r1-r2) | Fix now | The CLI-scoped follow-on items are stranded in the review artifact without plan-level tracking. Create [FW-10](../future-work.md#fw-10-cli-simplification-amendment) in [docs/future-work.md](../future-work.md) to capture the CLI simplification amendment as durable backlog (items 1–5: remove `add`, rename `remove-root`, unify placeholder, confirm reconciliation, settle full-vs-incremental). API-scoped consequences (library method boundaries, naming/terminology cleanup) are owned by [M4-R2](../implementation-plan.md#m4-r2---api-interface-review) and do not belong in a post-release future-work item. |
| [M4-R1-R3](#m4-r1-r3) | Fix now | The plan notes explicitly asked for an `unsync` evaluation. Add a paragraph to [docs/execution/M4-R1.md](M4-R1.md) §4 explaining why `remove` is preferred over `unsync`: `unsync` implies reversing `sync` (undoing snapshot creation), while the actual operation is narrower (dropping one root from a multi-root set). `remove` communicates the correct semantic. |
| [M4-R1-R4](#m4-r1-r4) | Fix now | The reviewer is correct on both points. (1) The current [ContextSync.sync()](../../src/context_sync/_sync.py#L290) already reconciles all roots; the review should acknowledge this to prevent redundant downstream implementation. (2) The traversal-configuration-persistence question is a real design gap: when `sync` subsumes `add`, a bare `sync TICKET` (no overrides) should preserve the manifest's existing traversal configuration for that root rather than overwriting it with CLI defaults. Add both clarifications to [docs/execution/M4-R1.md](M4-R1.md). |
| [M4-R1-R5](#m4-r1-r5) | Discard | The reviewer explicitly recommends no action. The plan row `In progress` is the correct status per the execution model until post-review closeout. The execution file header saying "Phase A complete" describes the phase lifecycle, not the plan-row lifecycle, so the apparent inconsistency is actually two different status domains reporting correctly. |
| [M4-R1-R6](#m4-r1-r6) | Fix now | Add a row for the Python CLI conventions `Package Identity` requirement to the policy-fit assessment table in [docs/execution/M4-R1.md](M4-R1.md), confirming compliance. |
| [M4-R1-R7](#m4-r1-r7) | Fix now | The plan ticket scope includes output ergonomics and operator comprehension. Add an explicit output-ergonomics section to [docs/execution/M4-R1.md](M4-R1.md) evaluating: (a) rendered top-level and subcommand help text, (b) human-readable success/failure output, and (c) the `diff` lock-refusal message. Classify each gap as documentation-only or amendment-required. |
| [M4-R1-R8](#m4-r1-r8) | Discard | The four-command surface (`sync`, `refresh`, `remove`, `diff`) is settled. The full-vs-incremental distinction stays internal — there is no `--full` flag. The §3a alternatives analysis already documents the reasoning. There is nothing left to track. |
