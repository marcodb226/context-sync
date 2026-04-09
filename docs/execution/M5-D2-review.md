# M5-D2 Review

> **Status**: Phase B complete (1 review pass, findings recorded)
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
| M5-D2-R1 | Medium | Todo | Documentation routing | The refresh retires [docs/design/linear-client-v1.0.0.md](../design/linear-client-v1.0.0.md) and updates [docs/design/dependency-map.md](../design/dependency-map.md) to describe the sibling-clone editable-install workspace model, but both files route readers seeking installation/workspace guidance to [README.md#installation](../../README.md#installation). That README section still documents end-user Git-SSH package installs for both repositories, while the actual workspace-clone/editable-install flow now lives under [README.md#developer-setup](../../README.md#developer-setup) and [docs/workspace-setup.md](../workspace-setup.md). The refreshed design layer therefore points readers at a section that contradicts the model it just established. | [docs/design/linear-client-v1.0.0.md:16](../design/linear-client-v1.0.0.md#L16) routes "Installation and workspace layout" to [README.md#installation](../../README.md#installation); [docs/design/dependency-map.md:141-146](../design/dependency-map.md#L141) says the install command and workspace setup are documented in [README.md#installation](../../README.md#installation); [README.md:29-39](../../README.md#L29) still documents Git-SSH installs; [README.md:295-314](../../README.md#L295) contains the actual sibling-workspace editable-install instructions. | A contributor or future [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring) implementor following the refreshed design-layer pointers can land on the wrong bootstrap instructions and set up a non-workspace install that does not match the documented current-state model. That undercuts the ticket's goal of making the design layer read as one coherent description of current reality. | Change the refreshed references so workspace-model guidance points to [docs/workspace-setup.md](../workspace-setup.md) and/or [README.md#developer-setup](../../README.md#developer-setup), or rewrite [README.md#installation](../../README.md#installation) to explicitly distinguish end-user package installation from repo-development workspace bootstrap before citing it as the authoritative workspace source. |
| M5-D2-R2 | Low | Todo | Authoritative references | [M5-D2](../implementation-plan.md#m5-d2---design-artifact-refresh-for-v110-workspace-model) retires [docs/design/linear-client-v1.0.0.md](../design/linear-client-v1.0.0.md) as redundant and says the authoritative current sources are now the workspace docs, dependency map, library docs, and the v1.1.0 audit. But the active implementation plan still lists the retired file in its current `Governing artifacts` header. That leaves the live plan presenting a redirect stub as authoritative state even after the retirement landed. | [docs/implementation-plan.md:4-8](../implementation-plan.md#L4) still lists [docs/design/linear-client-v1.0.0.md](../design/linear-client-v1.0.0.md) as a governing artifact; [docs/design/linear-client-v1.0.0.md:1-10](../design/linear-client-v1.0.0.md#L1) marks the file retired and says the sibling-workspace/library docs are now authoritative; [docs/implementation-plan.md:974-980](../implementation-plan.md#L974) says the local API reference summary is redundant and that authoritative content now lives elsewhere. | Future sessions that begin from the active plan are still told to consult a retired document as current governing input. The redirect softens the damage, but it keeps the authoritative-source story muddled right after a ticket whose purpose was to make that story cleaner. | Replace the retired-doc entry in the active plan's governing-artifacts block with the stable sources that M5-D2 establishes now (for example [docs/workspace-setup.md](../workspace-setup.md) and/or [docs/design/linear-domain-coverage-audit-v1.1.0.md](../design/linear-domain-coverage-audit-v1.1.0.md)), or explicitly mark the retained reference as historical rather than governing. |

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
