# Review: [M3-3](../implementation-plan.md#m3-3---diff-mode-and-lock-aware-drift-reporting)

> **Status**: Phase B complete
> **Plan ticket**:
> [M3-3](../implementation-plan.md#m3-3---diff-mode-and-lock-aware-drift-reporting)
> **Execution record**:
> [docs/execution/M3-3.md](M3-3.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/coding-guidelines-python.md](../policies/common/coding-guidelines-python.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/adr.md](../adr.md#53-diff-non-mutating-drift-inspection),
> [docs/adr.md](../adr.md#2-persistence-format),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#32-diffresult),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#64-diff-flow)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M3-3-R1 | Medium | Todo | Freshness Contract | `diff()` can report a tracked file as `current` even when its on-disk `format_version` is already too old for the accepted refresh-cursor contract. The M1-D3 design says a file whose `format_version` is too old must be treated as not fresh, but the new diff path never reads or checks `format_version`; it only compares the three cursor components and optional `ticket_key`. | [src/context_sync/_sync.py:1493](../../src/context_sync/_sync.py#L1493), [src/context_sync/_sync.py:1501](../../src/context_sync/_sync.py#L1501), [src/context_sync/_sync.py:1545](../../src/context_sync/_sync.py#L1545), [src/context_sync/_diff.py:113](../../src/context_sync/_diff.py#L113), [docs/design/0-top-level-design.md:463](../design/0-top-level-design.md#L463), [docs/adr.md:182](../adr.md#L182) | Operators can run `diff` and see a clean snapshot even though the next `refresh` must rewrite that file immediately for format-compatibility reasons. In review-time reproduction, changing a tracked ticket file to `format_version: 0` while leaving the cursor untouched made `await diff()` return `status="current"` with `changed_fields=[]`. | Reuse the same local-freshness gate that `refresh` applies, or add an explicit `format_version` check before returning `current`. A file whose format is too old should be classified as stale (or a dedicated local-validation status if the API grows one). Add a regression test that downgrades `format_version` without changing remote metadata and asserts `diff()` does not report `current`. |
| M3-3-R2 | High | Todo | Local Identity Validation | `diff()` collapses identity-breaking local corruption into ordinary drift statuses instead of surfacing a validation failure. The per-ticket read loop catches frontmatter parse failures and substitutes `{}` as if the file were merely stale, and the later comparison logic never validates `ticket_uuid` against the manifest UUID at all. As a result, a malformed ticket file becomes a normal `stale` entry with no `errors`, and a file whose `ticket_uuid` is missing or wrong can still be reported as `current` if its cursor happens to match. | [src/context_sync/_sync.py:1490](../../src/context_sync/_sync.py#L1490), [src/context_sync/_sync.py:1503](../../src/context_sync/_sync.py#L1503), [src/context_sync/_sync.py:1521](../../src/context_sync/_sync.py#L1521), [src/context_sync/_diff.py:113](../../src/context_sync/_diff.py#L113), [src/context_sync/_diff.py:135](../../src/context_sync/_diff.py#L135), [src/context_sync/_io.py:25](../../src/context_sync/_io.py#L25), [docs/design/0-top-level-design.md:466](../design/0-top-level-design.md#L466), [docs/adr.md:184](../adr.md#L184), [docs/adr.md:194](../adr.md#L194) | This breaks the core diagnostic promise of `diff`: it can say the snapshot is healthy when the local file no longer represents the tracked ticket. In review-time reproduction, changing `ticket_uuid` to a different value, or removing `ticket_uuid` entirely, still made `await diff()` return `status="current"` with `changed_fields=[]`; replacing the frontmatter with malformed YAML produced a plain `stale` entry and `errors=[]` instead of any validation failure. | Validate that parsed frontmatter still identifies the tracked ticket before using it as the local baseline. At minimum, require a matching `ticket_uuid` and treat malformed or identity-mismatched files as explicit `DiffResult.errors` entries or a raised validation error instead of folding them into normal freshness output. Add regression tests for malformed frontmatter, missing `ticket_uuid`, and mismatched `ticket_uuid`. |

## Reviewer Notes

- Review scope was the `M3-3` implementation commit `9a6fe15` plus the
  repository artifacts it touched.
- Review-time reproduction for [M3-3-R1](M3-3-review.md#findings):
  after a normal `sync()`, editing the tracked file to set `format_version: 0`
  and then calling `await diff()` returned one entry with
  `status="current"` and `changed_fields=[]`.
- Review-time reproduction for [M3-3-R2](M3-3-review.md#findings):
  after a normal `sync()`, editing the tracked file so frontmatter contained
  `ticket_uuid: uuid-other` or omitted `ticket_uuid` entirely still made
  `await diff()` return `status="current"` with `changed_fields=[]`; replacing
  the frontmatter with malformed YAML produced `status="stale"` and an empty
  `errors` list.
- I did not find a Linear-boundary violation in this ticket.
  [src/context_sync/_sync.py](../../src/context_sync/_sync.py)
  continues to route remote reads through the gateway abstraction.
- I did not rerun the repository lint/format/test commands during this review.
  The current worktree diff is docs-only, and this repository's validation
  gate says not to run the repo validation commands for docs-only work unless
  the user explicitly asks.

## Residual Risks and Testing Gaps

- [tests/test_diff.py](../../tests/test_diff.py) exercises lock handling,
  `missing_locally`, `missing_remotely`, and changed-field detection, but it
  does not cover format-version incompatibility or local identity corruption.
- There is no regression test for malformed frontmatter in `diff()` even
  though the current implementation has a special "treat as stale" fallback at
  [src/context_sync/_sync.py:1503](../../src/context_sync/_sync.py#L1503).
- The new `DiffResult.errors` surface remains effectively unexercised by the
  `M3-3` test suite. [tests/test_diff.py](../../tests/test_diff.py) asserts
  `errors == []` for the empty-manifest case, but no test covers a ticket-level
  diff error path or validates how local corruption should be reported.
