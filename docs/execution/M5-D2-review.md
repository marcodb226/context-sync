# M5-D2 Review

> **Status**: Phase C complete (2 review passes, all findings fixed)
> **Plan ticket**:
> [M5-D2](../implementation-plan.md#m5-d2---design-artifact-refresh-for-v110-workspace-model)
> **Execution record**:
> [docs/execution/M5-D2.md](M5-D2.md)

## Review Pass 1

> **LLM**: GPT-5
> **Effort**: N/A
> **Time spent**: ~25m

### Scope

Design review of
[M5-D2](../implementation-plan.md#m5-d2---design-artifact-refresh-for-v110-workspace-model)
("Design-artifact refresh for v1.1.0 workspace model"). The reviewed
deliverables are
[docs/design/linear-client-v1.0.0.md](../design/linear-client-v1.0.0.md),
[docs/design/dependency-map.md](../design/dependency-map.md),
[docs/adr.md](../adr.md),
[docs/design/0-top-level-design.md](../design/0-top-level-design.md), and the
Phase A execution record at [docs/execution/M5-D2.md](M5-D2.md). Cross-checks
also used [docs/workspace-setup.md](../workspace-setup.md),
[README.md](../../README.md), and the review guidance in
[docs/policies/common/reviews/design-review.md](../policies/common/reviews/design-review.md).

### Dependency-Satisfaction Verification

[M5-D2](../implementation-plan.md#m5-d2---design-artifact-refresh-for-v110-workspace-model)
depends only on
[M5-D1](../implementation-plan.md#m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110).
The active plan marks [M5-D1](../implementation-plan.md#m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110)
as `Done`, and the execution record at [docs/execution/M5-D2.md](M5-D2.md)
records the dependency as satisfied. Verified.

### Terminology Compliance

Checked the changed design prose against
[docs/policies/terminology.md](../policies/terminology.md). No banned-term
violations found.

### Design-Artifact Boundary Check

The refreshed design docs stay design-focused: they do not import review
findings, execution-log tables, or other process-state material into the
lasting design surface. References to
[M5-D2](../implementation-plan.md#m5-d2---design-artifact-refresh-for-v110-workspace-model)
in [docs/design/linear-client-v1.0.0.md](../design/linear-client-v1.0.0.md)
are clearly historical traceability rather than normative design behavior.

### Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M5-D2-R1 | Medium | Done | Documentation routing | The refresh retires [docs/design/linear-client-v1.0.0.md](../design/linear-client-v1.0.0.md) and updates [docs/design/dependency-map.md](../design/dependency-map.md) to describe the sibling-clone editable-install workspace model, but both files route readers seeking installation/workspace guidance to [README.md#installation](../../README.md#installation). That README section still documents end-user Git-SSH package installs for both repositories, while the actual workspace-clone/editable-install flow now lives under [README.md#developer-setup](../../README.md#developer-setup) and [docs/workspace-setup.md](../workspace-setup.md). The refreshed design layer therefore points readers at a section that contradicts the model it just established. | [docs/design/linear-client-v1.0.0.md:16](../design/linear-client-v1.0.0.md#L16) routes "Installation and workspace layout" to [README.md#installation](../../README.md#installation); [docs/design/dependency-map.md:141-146](../design/dependency-map.md#L141) says the install command and workspace setup are documented in [README.md#installation](../../README.md#installation); [README.md:29-39](../../README.md#L29) still documents Git-SSH installs; [README.md:295-314](../../README.md#L295) contains the actual sibling-workspace editable-install instructions. | A contributor or future [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring) implementor following the refreshed design-layer pointers can land on the wrong bootstrap instructions and set up a non-workspace install that does not match the documented current-state model. That undercuts the ticket's goal of making the design layer read as one coherent description of current reality. | Change the refreshed references so workspace-model guidance points to [docs/workspace-setup.md](../workspace-setup.md) and/or [README.md#developer-setup](../../README.md#developer-setup), or rewrite [README.md#installation](../../README.md#installation) to explicitly distinguish end-user package installation from repo-development workspace bootstrap before citing it as the authoritative workspace source. |
| M5-D2-R2 | Low | Done | Authoritative references | [M5-D2](../implementation-plan.md#m5-d2---design-artifact-refresh-for-v110-workspace-model) retires [docs/design/linear-client-v1.0.0.md](../design/linear-client-v1.0.0.md) as redundant and says the authoritative current sources are now the workspace docs, dependency map, library docs, and the v1.1.0 audit. But the active implementation plan still lists the retired file in its current `Governing artifacts` header. That leaves the live plan presenting a redirect stub as authoritative state even after the retirement landed. | [docs/implementation-plan.md:4-8](../implementation-plan.md#L4) still lists [docs/design/linear-client-v1.0.0.md](../design/linear-client-v1.0.0.md) as a governing artifact; [docs/design/linear-client-v1.0.0.md:1-10](../design/linear-client-v1.0.0.md#L1) marks the file retired and says the sibling-workspace/library docs are now authoritative; [docs/implementation-plan.md:974-980](../implementation-plan.md#L974) says the local API reference summary is redundant and that authoritative content now lives elsewhere. | Future sessions that begin from the active plan are still told to consult a retired document as current governing input. The redirect softens the damage, but it keeps the authoritative-source story muddled right after a ticket whose purpose was to make that story cleaner. | Replace the retired-doc entry in the active plan's governing-artifacts block with the stable sources that M5-D2 establishes now (for example [docs/workspace-setup.md](../workspace-setup.md) and/or [docs/design/linear-domain-coverage-audit-v1.1.0.md](../design/linear-domain-coverage-audit-v1.1.0.md)), or explicitly mark the retained reference as historical rather than governing. |

### Residual Risks and Testing Gaps

- The refreshed design docs are otherwise directionally sound: the ADR and
  top-level design now describe the current v1.1.0 sibling-workspace model and
  point boundary decisions at the
  [v1.1.0 audit](../design/linear-domain-coverage-audit-v1.1.0.md).
- I did not find a terminology violation or a design-artifact-boundary
  violation in the changed files.
- I did not run repository linting or tests during this review. The worktree
  changes for this review pass are docs-only, and the repository policy says
  not to run the declared validation commands for docs-only review work unless
  the user explicitly asks.

### Overall Assessment

The core factual corrections in [docs/adr.md](../adr.md) and
[docs/design/0-top-level-design.md](../design/0-top-level-design.md) are good
and move the design layer in the right direction. The remaining gaps are about
authoritative-source routing: one medium-severity pointer mismatch that sends
readers to the wrong README section, and one lower-severity plan-header
reference that still treats the retired summary as a governing artifact.

## Review Pass 2

> **LLM**: Claude Opus 4.6 (1M context)
> **Effort**: N/A
> **Time spent**: ~25m

### Scope

Independent design review of
[M5-D2](../implementation-plan.md#m5-d2---design-artifact-refresh-for-v110-workspace-model)
deliverables. Reviewed the full git diff (`c32bc1d..d4e6430`) across all four
changed design documents, the Phase A execution record at
[docs/execution/M5-D2.md](M5-D2.md), and the Review Pass 1 findings. Cross-
checked against [CR-26.04.07](../planning/change-requests/CR-26.04.07.md)
§M5-D2 detailed notes, [docs/workspace-setup.md](../workspace-setup.md),
[README.md](../../README.md), the M5-D1 ticket notes in
[docs/implementation-plan.md](../implementation-plan.md), and the design
review checklist at
[docs/policies/common/reviews/design-review.md](../policies/common/reviews/design-review.md).

### Dependency-Satisfaction Verification

[M5-D2](../implementation-plan.md#m5-d2---design-artifact-refresh-for-v110-workspace-model)
depends only on
[M5-D1](../implementation-plan.md#m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110).
The active plan marks
[M5-D1](../implementation-plan.md#m5-d1---linear-domain-coverage-audit-and-adapter-boundary--v110)
as `Done`, and the execution record at [docs/execution/M5-D2.md](M5-D2.md)
records the dependency as satisfied. Verified.

### Terminology Compliance

Checked the diff against
[docs/policies/terminology.md](../policies/terminology.md). No banned-term
violations found.

### Design-Artifact Boundary Check

The refreshed design documents remain design-focused. No review findings,
execution-log tables, or process-state material was imported into the lasting
design surface. The retirement notice in
[docs/design/linear-client-v1.0.0.md](../design/linear-client-v1.0.0.md)
links to the
[M5-D2](../implementation-plan.md#m5-d2---design-artifact-refresh-for-v110-workspace-model)
plan ticket for historical traceability only — not as a normative design
reference.

### Agreement with Review Pass 1

I independently verified and agree with both findings from Review Pass 1:

- **M5-D2-R1** (Medium): The `README.md#installation` pointer mismatch is
  confirmed. [README.md:29–39](../../README.md#L29) documents end-user Git-SSH
  package installs from the private GitHub repositories.
  [README.md:295–314](../../README.md#L295) documents the actual workspace-clone
  editable-install developer flow. The refreshed design docs in
  [docs/design/dependency-map.md:145–146](../design/dependency-map.md#L145) and
  the retired redirect table in
  [docs/design/linear-client-v1.0.0.md:16](../design/linear-client-v1.0.0.md#L16)
  both route to the wrong section. The Phase A execution file claims "Manual
  cross-document consistency check: verified that all four updated design
  documents describe the workspace model consistently" — but this check was
  link-resolution-level, not semantic. The targets resolve, but the content at
  `README.md#installation` contradicts the workspace model the refresh
  establishes.

- **M5-D2-R2** (Low): The governing-artifacts header in
  [docs/implementation-plan.md:8](../implementation-plan.md#L8) still lists
  the retired
  [docs/design/linear-client-v1.0.0.md](../design/linear-client-v1.0.0.md) as
  a current governing artifact.

### Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M5-D2-R3 | Medium | Done | Reference stability | The three refreshed design documents reference the v1.1.0 audit by its versioned filename (`linear-domain-coverage-audit-v1.1.0.md`) instead of the stable canonical index (`linear-domain-coverage-audit.md`). The M5-D1 ticket notes in the active plan ([docs/implementation-plan.md:926](../implementation-plan.md#L926)) explicitly reserve the unversioned path as a "compatibility index that points readers to the maintained versioned audits." Design documents describe enduring contracts — they mean "the current audit," not "the audit that happened to be current when M5-D2 landed." Using the versioned filename means any future `linear-client` upgrade requires mechanical updates to all three design documents for the same reference that the canonical index was designed to absorb. | [docs/adr.md:270](../adr.md#L270): `[docs/design/linear-domain-coverage-audit-v1.1.0.md](<design/linear-domain-coverage-audit-v1.1.0.md>)`; [docs/design/0-top-level-design.md:104](../design/0-top-level-design.md#L104): `[docs/design/linear-domain-coverage-audit-v1.1.0.md](<linear-domain-coverage-audit-v1.1.0.md>)`; [docs/design/dependency-map.md:152](../design/dependency-map.md#L152): `[docs/design/linear-domain-coverage-audit-v1.1.0.md](linear-domain-coverage-audit-v1.1.0.md)`; [docs/implementation-plan.md:926](../implementation-plan.md#L926) reserves the canonical path as a stable index. | The next dependency upgrade (e.g. v1.2.0) will require a mechanical find-and-replace across the ADR, top-level design, and dependency map — exactly the maintenance burden the canonical index was designed to eliminate. This also creates a window where the design docs name a superseded audit filename if the versioned file is renamed before the design docs are updated. | Change the three design-document references from `linear-domain-coverage-audit-v1.1.0.md` to the stable canonical `linear-domain-coverage-audit.md`. The implementation plan, execution artifacts, and review files should keep the versioned reference for traceability. |
| M5-D2-R4 | Low | Done | Redirect accuracy | The retired [docs/design/linear-client-v1.0.0.md](../design/linear-client-v1.0.0.md) redirect table routes "Live validation workspace" to [docs/design/dependency-map.md](../design/dependency-map.md), but that document contains no live-validation-workspace content. The original section described the `ARK` Linear team as a designated safe workspace for experimentation and validation spikes. That guidance was not migrated to any current design or operational document — it exists only in historical execution artifacts ([docs/execution/M1-D1.md](M1-D1.md), [docs/execution/M3-O1.md](M3-O1.md)) and [docs/design/refresh-freshness-validation.md](../design/refresh-freshness-validation.md). | [docs/design/linear-client-v1.0.0.md:23](../design/linear-client-v1.0.0.md#L23) routes to [docs/design/dependency-map.md](../design/dependency-map.md); searching `dependency-map.md` for `ARK`, `live validation`, or `validation workspace` returns no matches. | A reader following the redirect lands on a document with no matching content. The impact is low because the live-validation-workspace guidance is operational rather than design-contractual, but the redirect table's purpose is accurate routing. | Either add a brief "Live validation workspace" note to [docs/design/dependency-map.md](../design/dependency-map.md) (or another current operational doc), or change the redirect entry to state honestly that the content was not migrated and point to the historical execution artifacts where the ARK guidance was last recorded. |

### Residual Risks and Testing Gaps

- The ADR and top-level design now describe the current v1.1.0 workspace
  model consistently with each other. The dependency-map description is also
  consistent in substance, differing only in the README anchor target (covered
  by M5-D2-R1).
- No terminology violation or design-artifact-boundary violation found.
- The Phase A consistency check was link-resolution-level, not semantic. The
  links resolve, but the semantic mismatch at `README.md#installation` was
  not caught — this is the root of M5-D2-R1.
- Repository linting and tests were not run. The changes are docs-only, and
  repository policy exempts docs-only review work from declared validation
  commands unless explicitly requested.

### Overall Assessment

The factual corrections across [docs/adr.md](../adr.md),
[docs/design/0-top-level-design.md](../design/0-top-level-design.md), and
[docs/design/dependency-map.md](../design/dependency-map.md) are sound and
move the design layer from the v1.0.0-era "private GitHub repository" model to
the current v1.1.0 workspace model. The two new findings are about reference
durability: the design docs pin references to a versioned audit filename when a
stable index exists for exactly this purpose (M5-D2-R3), and one redirect-table
entry routes to a document that does not contain the claimed content
(M5-D2-R4). Combined with the two confirmed findings from Review Pass 1, the
ticket has four open items — two medium, two low — all in the
documentation-routing and reference-stability category.

## Ticket Owner Response

> **LLM**: Claude Opus 4.6 (1M context)
> **Effort**: N/A
> **Time spent**: ~20m

| ID | Verdict | Rationale |
| --- | --- | --- |
| M5-D2-R1 | Fix now | Agreed. The refreshed design docs should route workspace-model guidance to `README.md#developer-setup` and `docs/workspace-setup.md`, not to `README.md#installation` which documents end-user package installs. Fixed in `docs/design/dependency-map.md` and `docs/design/linear-client-v1.0.0.md`. |
| M5-D2-R2 | Fix now | Agreed. Replaced the retired `docs/design/linear-client-v1.0.0.md` entry in the implementation plan governing-artifacts header with `docs/workspace-setup.md`, which is the current authoritative source for the workspace model that the retired file used to describe. |
| M5-D2-R3 | Fix now | Agreed. Design documents describe enduring contracts and should use the stable canonical index (`linear-domain-coverage-audit.md`) rather than the versioned filename. Changed all three design-document references. Implementation plan, execution artifacts, and review files keep versioned references for traceability. |
| M5-D2-R4 | Fix now | Agreed. The `ARK` live-validation-workspace guidance was not migrated to any current design document. Updated the redirect entry to state that the content was not migrated and point to the historical execution artifacts where it was last recorded. |
