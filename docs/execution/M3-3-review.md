# Review: [M3-3](../implementation-plan.md#m3-3---diff-mode-and-lock-aware-drift-reporting)

> **Status**: Phase C complete
> **Plan ticket**:
> [M3-3](../implementation-plan.md#m3-3---diff-mode-and-lock-aware-drift-reporting)
> **Execution record**:
> [docs/execution/M3-3.md](M3-3.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/python/coding-guidelines.md](../policies/common/python/coding-guidelines.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/adr.md](../adr.md#53-diff-non-mutating-drift-inspection),
> [docs/adr.md](../adr.md#2-persistence-format),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#32-diffresult),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#64-diff-flow)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M3-3-R1 | Medium | Done | Freshness Contract | `diff()` can report a tracked file as `current` even when its on-disk `format_version` is already too old for the accepted refresh-cursor contract. The M1-D3 design says a file whose `format_version` is too old must be treated as not fresh, but the new diff path never reads or checks `format_version`; it only compares the three cursor components and optional `ticket_key`. | [src/context_sync/_sync.py:1493](../../src/context_sync/_sync.py#L1493), [src/context_sync/_sync.py:1501](../../src/context_sync/_sync.py#L1501), [src/context_sync/_sync.py:1545](../../src/context_sync/_sync.py#L1545), [src/context_sync/_diff.py:113](../../src/context_sync/_diff.py#L113), [docs/design/0-top-level-design.md:463](../design/0-top-level-design.md#L463), [docs/adr.md:182](../adr.md#L182) | Operators can run `diff` and see a clean snapshot even though the next `refresh` must rewrite that file immediately for format-compatibility reasons. In review-time reproduction, changing a tracked ticket file to `format_version: 0` while leaving the cursor untouched made `await diff()` return `status="current"` with `changed_fields=[]`. | Reuse the same local-freshness gate that `refresh` applies, or add an explicit `format_version` check before returning `current`. A file whose format is too old should be classified as stale (or a dedicated local-validation status if the API grows one). Add a regression test that downgrades `format_version` without changing remote metadata and asserts `diff()` does not report `current`. |
| M3-3-R2 | High | Done | Local Identity Validation | `diff()` collapses identity-breaking local corruption into ordinary drift statuses instead of surfacing a validation failure. The per-ticket read loop catches frontmatter parse failures and substitutes `{}` as if the file were merely stale, and the later comparison logic never validates `ticket_uuid` against the manifest UUID at all. As a result, a malformed ticket file becomes a normal `stale` entry with no `errors`, and a file whose `ticket_uuid` is missing or wrong can still be reported as `current` if its cursor happens to match. | [src/context_sync/_sync.py:1490](../../src/context_sync/_sync.py#L1490), [src/context_sync/_sync.py:1503](../../src/context_sync/_sync.py#L1503), [src/context_sync/_sync.py:1521](../../src/context_sync/_sync.py#L1521), [src/context_sync/_diff.py:113](../../src/context_sync/_diff.py#L113), [src/context_sync/_diff.py:135](../../src/context_sync/_diff.py#L135), [src/context_sync/_io.py:25](../../src/context_sync/_io.py#L25), [docs/design/0-top-level-design.md:466](../design/0-top-level-design.md#L466), [docs/adr.md:184](../adr.md#L184), [docs/adr.md:194](../adr.md#L194) | This breaks the core diagnostic promise of `diff`: it can say the snapshot is healthy when the local file no longer represents the tracked ticket. In review-time reproduction, changing `ticket_uuid` to a different value, or removing `ticket_uuid` entirely, still made `await diff()` return `status="current"` with `changed_fields=[]`; replacing the frontmatter with malformed YAML produced a plain `stale` entry and `errors=[]` instead of any validation failure. | Validate that parsed frontmatter still identifies the tracked ticket before using it as the local baseline. At minimum, require a matching `ticket_uuid` and treat malformed or identity-mismatched files as explicit `DiffResult.errors` entries or a raised validation error instead of folding them into normal freshness output. Add regression tests for malformed frontmatter, missing `ticket_uuid`, and mismatched `ticket_uuid`. |
| M3-3-R3 | Medium | Done | Error Surface | `DiffResult.errors` is declared in the model and specified in the design contract ([docs/design/0-top-level-design.md §3.2](../design/0-top-level-design.md#L254) and [§4 error table](../design/0-top-level-design.md#L261)) but is never populated by `diff()`. The `errors` list is created at [src/context_sync/_sync.py:1517](../../src/context_sync/_sync.py#L1517) and returned empty on every code path. Per-ticket issues (frontmatter parse failures at [src/context_sync/_sync.py:1503](../../src/context_sync/_sync.py#L1503), potential `OSError` from `read_text` at [src/context_sync/_sync.py:1501](../../src/context_sync/_sync.py#L1501)) are either absorbed into normal status classifications or propagate as unhandled exceptions that abort the entire operation. | [src/context_sync/_sync.py:1517](../../src/context_sync/_sync.py#L1517), [src/context_sync/_models.py:92](../../src/context_sync/_models.py#L92), [docs/design/0-top-level-design.md:254](../design/0-top-level-design.md#L254), [docs/design/0-top-level-design.md:270](../design/0-top-level-design.md#L270) | Operators receive no structured per-ticket error signal from `diff`. A single ticket with a read-permission error or corrupt file aborts the entire operation instead of being reported in `errors` while the remaining tickets are classified normally. This also means M3-3-R2's recommended fix (report identity failures through `DiffResult.errors`) has no working channel to target. | Catch `OSError` in the per-ticket read loop alongside the existing exception types and append a `SyncError` to the `errors` list for any ticket whose local file cannot be read or parsed, then continue the loop. Wire up the `errors` surface so downstream consumers (M4-1 CLI) can report per-ticket problems without losing the rest of the diff output. Add a test that exercises a ticket-level error during diff and asserts it appears in `DiffResult.errors`. |
| M3-3-R4 | Low | Done | Async Concurrency | The three independent metadata-batch calls at [src/context_sync/_sync.py:1511–1513](../../src/context_sync/_sync.py#L1511) are awaited sequentially. `get_refresh_issue_metadata`, `get_refresh_comment_metadata`, and `get_refresh_relation_metadata` take the same input list and do not depend on each other's results. The Python coding guidelines ([docs/policies/common/python/coding-guidelines.md §Async](../policies/common/python/coding-guidelines.md#async)) say "do not `await` them sequentially when they can run in parallel." | [src/context_sync/_sync.py:1511](../../src/context_sync/_sync.py#L1511), [src/context_sync/_sync.py:1512](../../src/context_sync/_sync.py#L1512), [src/context_sync/_sync.py:1513](../../src/context_sync/_sync.py#L1513), [docs/policies/common/python/coding-guidelines.md](../policies/common/python/coding-guidelines.md) | Diff latency is roughly three serial round-trips to the Linear API instead of one parallel round-trip. For large manifests this multiplies wall-clock wait time unnecessarily, and it extends the window during which diff holds API capacity that could delay a concurrent mutating writer. | Use `asyncio.gather` (or `asyncio.TaskGroup`) to run the three metadata calls concurrently. Note that `refresh` at [src/context_sync/_sync.py:974–976](../../src/context_sync/_sync.py#L974) has the same sequential pattern; fixing both together would be consistent. |
| M3-3-R5 | Low | Done | Design Contract | `changed_fields` values use internal cursor-component names (`"issue_updated_at"`, `"comments_signature"`, `"relations_signature"`, `"issue_key"`) rather than the human-facing field names shown in the design pseudocode ([docs/design/0-top-level-design.md §3.2](../design/0-top-level-design.md#L251): `# e.g., ["status", "comments"]`). The cursor-component names are a reasonable implementation choice that reflects what `diff` actually compares, but they diverge from the documented example and are less intuitive for operators. | [src/context_sync/_diff.py:117–138](../../src/context_sync/_diff.py#L117), [docs/design/0-top-level-design.md:251](../design/0-top-level-design.md#L251), [src/context_sync/_models.py:83](../../src/context_sync/_models.py#L83) | [M4-1](../implementation-plan.md#m4-1---cli-surface-and-command-output-contracts) (CLI surface) will display these values to operators. An operator seeing `"comments_signature"` must infer that comment content changed, whereas `"comments"` would be immediately clear. The design example creates an expectation that downstream consumers may rely on. | Either update the design pseudocode example to reflect the cursor-component naming convention (making the implementation authoritative), or translate the cursor-component names into human-facing field names before populating `changed_fields`. If the cursor names are kept, document the mapping in the `DiffEntry` docstring so M4-1 can translate at the CLI layer. |

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

---

## Review Pass 2 — Reviewer Notes

- Review scope: the same `M3-3` implementation commit `9a6fe15`, the repository
  artifacts it touched, and the governing design/ADR sections. This pass
  focused on the error surface, async concurrency, and design-contract alignment
  rather than re-examining the freshness and identity validation paths already
  covered by the first pass.
- I agree with both M3-3-R1 and M3-3-R2 from the first pass. The
  `format_version` gap and the identity validation gap are real and
  well-evidenced. I did not create new finding rows for them.
- M3-3-R3 (dead `errors` surface) is a prerequisite for properly fixing
  M3-3-R2. The first pass's recommendation to "treat malformed or
  identity-mismatched files as explicit `DiffResult.errors` entries" requires a
  working errors channel, which does not currently exist.
- For M3-3-R3, I verified that `OSError` is not caught by the `except` clause
  at [src/context_sync/_sync.py:1503](../../src/context_sync/_sync.py#L1503)
  (which only handles `ValueError`, `KeyError`, `ManifestError`). A file with
  changed permissions after sync would raise an unhandled `OSError` and abort
  the entire diff for all tickets.
- For M3-3-R4, the same sequential-await pattern exists in `refresh` at
  [src/context_sync/_sync.py:974–976](../../src/context_sync/_sync.py#L974).
  Both are new code (M3-1 and M3-3 respectively) that should have used
  concurrent gathering per the Python coding guidelines.
- For M3-3-R5, the design pseudocode example `["status", "comments"]` is
  illustrative rather than normative, but the mismatch is worth resolving
  before M4-1 builds a CLI display layer on top of it.
- No Linear-boundary violation found in this pass, consistent with the first
  pass's conclusion.
- I did not rerun the repository lint/format/test commands during this review.
  The worktree diff is docs-only.

## Review Pass 2 — Residual Risks and Testing Gaps

- The `except (ValueError, KeyError, ManifestError)` handler at
  [src/context_sync/_sync.py:1503](../../src/context_sync/_sync.py#L1503) does
  not cover `OSError`. A permission-denied or I/O error on any single ticket
  file aborts the full multi-ticket diff operation with an unhandled exception.
- No test exercises `DiffResult.errors` with a non-empty error list. The
  errors surface is dead code, so no test *can* exercise it without first
  wiring it up.
- [tests/test_diff.py](../../tests/test_diff.py) does not test the concurrent
  behavior of the three metadata calls, but this is difficult to test in unit
  isolation and is primarily a latency concern.
- The `refresh` flow at
  [src/context_sync/_sync.py:974–976](../../src/context_sync/_sync.py#L974)
  shares the sequential-await pattern flagged in M3-3-R4. Fixing only the
  `diff` path would leave the same guideline violation in `refresh`.

---

## Ticket Owner Response

| ID | Verdict | Rationale |
| --- | --- | --- |
| M3-3-R1 | Fix now | Add `format_version` check to `diff()` before returning `current`. A file whose format is too old is classified as `stale`. Regression test added. |
| M3-3-R2 | Fix now | Validate `ticket_uuid` against the manifest UUID. Missing or mismatched identity is reported through `DiffResult.errors`. Regression tests added for missing, mismatched, and malformed-frontmatter cases. |
| M3-3-R3 | Fix now | Catch `OSError` in the per-ticket read loop and append a `SyncError` to the `errors` list. This also provides the channel needed for M3-3-R2's identity failures. Regression test added. |
| M3-3-R4 | Fix now | Use `asyncio.gather` for the three independent metadata calls in both `diff()` and `refresh()`. |
| M3-3-R5 | Fix now | Update the design pseudocode example to match the cursor-component naming convention used in the implementation, and document the mapping in the `DiffEntry` docstring. |
