# Review: [M5-4](../implementation-plan.md#m5-4---adopt-linear-client-newtypes)

> **Status**: Phase C complete; all findings addressed
> **Plan ticket**:
> [M5-4](../implementation-plan.md#m5-4---adopt-linear-client-newtypes)
> **Execution record**:
> [docs/execution/M5-4.md](M5-4.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/python/coding-guidelines.md](../policies/common/python/coding-guidelines.md),
> [docs/policies/terminology.md](../policies/terminology.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/linear-client-issues.md](../linear-client-issues.md),
> [docs/design/linear-domain-coverage-audit-v1.1.0.md](../design/linear-domain-coverage-audit-v1.1.0.md)

## Review Pass 1

> **LLM**: GPT-5
> **Effort**: N/A
> **Time spent**: ~45m

### Scope

Implementation review of [M5-4](../implementation-plan.md#m5-4---adopt-linear-client-newtypes), covering the Phase A artifact at [docs/execution/M5-4.md](M5-4.md), the type vocabulary in [src/context_sync/_types.py](../../src/context_sync/_types.py), the public re-export surface in [src/context_sync/__init__.py](../../src/context_sync/__init__.py), the gateway import/usage path in [src/context_sync/_real_gateway.py](../../src/context_sync/_real_gateway.py), the boundary dataclasses in [src/context_sync/_gateway.py](../../src/context_sync/_gateway.py), the upstream type vocabulary in [linear-client src/linear_client/types.py](../../../linear-client/src/linear_client/types.py), and the governing ticket/design artifacts at [docs/implementation-plan.md](../implementation-plan.md), [docs/linear-client-issues.md](../linear-client-issues.md), and [docs/design/linear-domain-coverage-audit-v1.1.0.md](../design/linear-domain-coverage-audit-v1.1.0.md).

This pass applies the stricter governing principle behind the ticket and audit: context-sync should prefer `linear-client` semantic types wherever those types already exist, so the duplicated or weaker local vocabulary actually disappears instead of merely becoming acceptable to Pyright.

Independent verification during review:

- Activated-environment runtime check confirmed that with `linear-client` installed, `context_sync.IssueId is linear_client.IssueId`, `context_sync.IssueKey is linear_client.IssueKey`, `context_sync.CommentId is linear_client.CommentId`, `context_sync.AttachmentId is linear_client.AttachmentId`, and `context_sync.Timestamp is linear_client.IsoTimestamp` are all `False`.

### Dependency-Satisfaction Verification

[M5-4](../implementation-plan.md#m5-4---adopt-linear-client-newtypes) depends only on [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring). The active plan marks [M5-1](../implementation-plan.md#m5-1---real-linear-gateway-and-runtime-wiring) `Done`, and the execution artifact at [docs/execution/M5-4.md](M5-4.md) records that dependency as satisfied. Verified.

### Terminology Compliance

Checked the reviewed files against [docs/policies/terminology.md](../policies/terminology.md). No banned-term violations found.

### Changelog Review

[src/context_sync/version.py](../../src/context_sync/version.py#L11) is `0.1.0.dev0`, so this repository has not yet shipped a stable `>=1.0.0` release. The changelog gate does not apply.

### Upstream-Type Verification

The governing artifacts are consistent about the intended contract for the four duplicated aliases: [docs/implementation-plan.md](../implementation-plan.md#L910) and [docs/implementation-plan.md](../implementation-plan.md#L1131) both say `IssueId`, `IssueKey`, `CommentId`, and `AttachmentId` should be replaced with re-exports from `linear_client.types`; [docs/linear-client-issues.md](../linear-client-issues.md#L188) says the library types are authoritative and the duplicates must be dropped; and [docs/design/linear-domain-coverage-audit-v1.1.0.md](../design/linear-domain-coverage-audit-v1.1.0.md#L61) requires one shared `NewType` identity across the dependency boundary.

The implementation does successfully remove the old bridge imports from [src/context_sync/_real_gateway.py](../../src/context_sync/_real_gateway.py), and Pyright now sees a shared identity because [src/context_sync/_types.py](../../src/context_sync/_types.py#L34) imports the upstream aliases under `TYPE_CHECKING`. But the same module still defines fresh local `NewType` callables in the runtime branch, so the package does not actually prefer upstream types when they are available at import time.

The broader audit contract is also still open. [docs/design/linear-domain-coverage-audit-v1.1.0.md](../design/linear-domain-coverage-audit-v1.1.0.md#L76) says `Timestamp` should remain the local public name but alias upstream `IsoTimestamp`, and [docs/design/linear-domain-coverage-audit-v1.1.0.md](../design/linear-domain-coverage-audit-v1.1.0.md#L77) plus [docs/design/linear-domain-coverage-audit-v1.1.0.md](../design/linear-domain-coverage-audit-v1.1.0.md#L78) say the gateway boundary should adopt upstream `AssetUrl` and `IssueLinkType` rather than keeping weaker `str` types. The shipped code has not done those adoptions either.

### Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M5-4-R1 | Critical | Done | Shared type identity contract | [src/context_sync/_types.py](../../src/context_sync/_types.py) does not actually replace the duplicate aliases with upstream types at runtime. The upstream imports exist only in the `TYPE_CHECKING` branch, while the runtime branch still creates fresh local `NewType` aliases. Because [src/context_sync/__init__.py](../../src/context_sync/__init__.py) re-exports those `_types` names, the shipped public API still exposes context-sync-owned alias objects rather than the authoritative library aliases even when `linear-client` is installed. This is not a minor cleanliness gap; it misses the whole point of the ticket, which is to make the duplicated types disappear rather than merely placate static analysis. | [src/context_sync/_types.py:11](../../src/context_sync/_types.py#L11), [src/context_sync/_types.py:34](../../src/context_sync/_types.py#L34), [src/context_sync/_types.py:39](../../src/context_sync/_types.py#L39), [src/context_sync/__init__.py:99](../../src/context_sync/__init__.py#L99), [docs/implementation-plan.md:910](../implementation-plan.md#L910), [docs/implementation-plan.md:1131](../implementation-plan.md#L1131), [docs/linear-client-issues.md:188](../linear-client-issues.md#L188), [docs/design/linear-domain-coverage-audit-v1.1.0.md:61](../design/linear-domain-coverage-audit-v1.1.0.md#L61) | The repository still publishes duplicate runtime type objects for `IssueId`, `IssueKey`, `CommentId`, and `AttachmentId`, so the core deliverable has not happened. Code importing types from both packages still does not see one shared vocabulary at runtime, the ticket's governing rationale remains unresolved, and the current implementation enshrines a "Pyright is happy, therefore we're done" posture that directly contradicts the plan's intent. | Import the upstream aliases at runtime whenever `linear-client` is importable, and fall back to local `NewType` definitions only when the import genuinely fails. Add a regression test that, in an environment where `linear-client` is installed, asserts `context_sync.IssueId is linear_client.IssueId` and the same for `IssueKey`, `CommentId`, and `AttachmentId`. |
| M5-4-R2 | High | Done | Timestamp type unification | The broader type-surface contract still leaves `Timestamp` as a locally defined `NewType` instead of aliasing upstream `IsoTimestamp`. The review-time runtime check confirmed `context_sync.Timestamp is linear_client.IsoTimestamp` is `False`, and [src/context_sync/_types.py](../../src/context_sync/_types.py#L65) still defines `Timestamp = NewType("Timestamp", str)` directly. | [src/context_sync/_types.py:65](../../src/context_sync/_types.py#L65), [linear-client src/linear_client/types.py:92](../../../linear-client/src/linear_client/types.py#L92), [src/context_sync/_gateway.py:110](../../src/context_sync/_gateway.py#L110), [src/context_sync/_gateway.py:187](../../src/context_sync/_gateway.py#L187), [docs/design/linear-domain-coverage-audit-v1.1.0.md:76](../design/linear-domain-coverage-audit-v1.1.0.md#L76) | All gateway timestamp fields still use a context-sync-only runtime type object even though the audit explicitly chose a local-name-over-upstream-alias strategy. That leaves the timestamp vocabulary duplicated across the boundary in the same way this milestone was meant to eliminate for the ID types. | Make `Timestamp` a real alias/re-export of upstream `IsoTimestamp` when `linear-client` is available, while preserving the `Timestamp` public name for ergonomics. Add a regression test asserting `context_sync.Timestamp is linear_client.IsoTimestamp` in the installed-dependency environment. |
| M5-4-R3 | High | Done | Attachment URL typing | The gateway boundary still uses bare `str` for attachment URLs even though the audit explicitly selects upstream `AssetUrl`. [src/context_sync/_gateway.py](../../src/context_sync/_gateway.py#L186) keeps `AttachmentData.url: str`, and [src/context_sync/_real_gateway.py](../../src/context_sync/_real_gateway.py#L923) coerces the upstream value to `str` rather than preserving the stronger semantic type. | [src/context_sync/_gateway.py:186](../../src/context_sync/_gateway.py#L186), [src/context_sync/_real_gateway.py:923](../../src/context_sync/_real_gateway.py#L923), [linear-client src/linear_client/types.py:85](../../../linear-client/src/linear_client/types.py#L85), [docs/design/linear-domain-coverage-audit-v1.1.0.md:77](../design/linear-domain-coverage-audit-v1.1.0.md#L77) | The boundary throws away an upstream semantic type that already exists and that the governing audit explicitly chose. That weakens the public contract and leaves another "prefer upstream types when available" obligation unmet. | Change `AttachmentData.url` to use upstream `AssetUrl` and preserve that type in the gateway conversion path instead of collapsing it to bare `str`. Add focused tests on the dataclass surface or conversion helpers so future refactors do not silently regress to `str`. |
| M5-4-R4 | High | Done | Relation type typing | The gateway boundary still uses bare `str` for `RelationData.relation_type` even though the audit explicitly selects upstream `IssueLinkType`. [src/context_sync/_gateway.py](../../src/context_sync/_gateway.py#L209) keeps the field as `str`, and the normalization helper in [src/context_sync/_real_gateway.py](../../src/context_sync/_real_gateway.py#L196) passes the raw string through unchanged instead of preserving the upstream semantic type. | [src/context_sync/_gateway.py:209](../../src/context_sync/_gateway.py#L209), [src/context_sync/_real_gateway.py:196](../../src/context_sync/_real_gateway.py#L196), [linear-client src/linear_client/types.py:64](../../../linear-client/src/linear_client/types.py#L64), [docs/design/linear-domain-coverage-audit-v1.1.0.md:78](../design/linear-domain-coverage-audit-v1.1.0.md#L78) | Context-sync still widens a typed upstream relation vocabulary into an untyped string at the boundary. That loses the exact type information the audit selected, and it leaves another available `linear-client` semantic type unapplied in shipped code. | Change `RelationData.relation_type` to upstream `IssueLinkType` and preserve that type through normalization and refresh-relation paths. Add regression coverage so relation-type fields stay aligned with the upstream semantic vocabulary. |

### Residual Risks and Testing Gaps

- There is still no package-surface regression test proving that the exported aliases in [src/context_sync/__init__.py](../../src/context_sync/__init__.py) are the same objects as the corresponding aliases in `linear-client` when that dependency is installed. Existing package tests cover importability, not alias identity, which is exactly why the runtime-duplication gap slipped through.
- I did not rerun the full repository validation suite during review because the blocking issue is a structural contract mismatch visible from the shipped source and confirmed by the targeted activated-environment identity check above.

### Overall Assessment

This ticket is not review-clean yet. The current implementation improves Pyright ergonomics, but it does not deliver the actual type-surface cleanup the plan and audit require. The duplicate runtime aliases are still present, `Timestamp` still does not alias upstream `IsoTimestamp`, and the gateway still widens `AssetUrl` and `IssueLinkType` to bare strings. That is a contract miss, not a polish issue.

## Ticket Owner Response

> **LLM**: GPT-5
> **Effort**: N/A
> **Time spent**: ~35m

| ID | Verdict | Rationale |
| --- | --- | --- |
| [M5-4-R1](M5-4-review.md#findings) | Fix now | The review is correct that `TYPE_CHECKING`-only imports do not satisfy the ticket's runtime shared-identity goal. [src/context_sync/_types.py](../../src/context_sync/_types.py) will be updated to import the upstream aliases at runtime when `linear-client` is available, with local `NewType` fallbacks only when that import fails. Package-surface regression coverage will assert that [src/context_sync/__init__.py](../../src/context_sync/__init__.py) re-exports the same alias objects as `linear-client` in the installed-dependency environment. |
| [M5-4-R2](M5-4-review.md#findings) | Fix now | The audit at [docs/design/linear-domain-coverage-audit-v1.1.0.md:76](../design/linear-domain-coverage-audit-v1.1.0.md#L76) is the governing clarification for the broader type surface: `Timestamp` should keep its local public name but share runtime identity with upstream `IsoTimestamp`. [src/context_sync/_types.py](../../src/context_sync/_types.py) and the package-surface tests will be updated accordingly. |
| [M5-4-R3](M5-4-review.md#findings) | Fix now | The gateway boundary should preserve the stronger upstream semantic type for attachment URLs rather than collapsing it to bare `str`. [src/context_sync/_gateway.py](../../src/context_sync/_gateway.py) will move `AttachmentData.url` to `AssetUrl`, [src/context_sync/_real_gateway.py](../../src/context_sync/_real_gateway.py) will construct that alias in the conversion path, and focused regression coverage will lock the dataclass type surface in place. |
| [M5-4-R4](M5-4-review.md#findings) | Fix now | The gateway boundary should also preserve upstream `IssueLinkType` for relation types. [src/context_sync/_gateway.py](../../src/context_sync/_gateway.py) and [src/context_sync/_real_gateway.py](../../src/context_sync/_real_gateway.py) will be updated so normalization and relation refresh paths keep the shared semantic vocabulary, with regression tests covering the dataclass type hints and the normalized output surface. |
