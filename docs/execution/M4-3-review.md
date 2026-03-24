# Review: [M4-3](../implementation-plan.md#m4-3---rename-root-ticket-id-to-key)

> **Status**: Phase C complete
> **Plan ticket**:
> [M4-3](../implementation-plan.md#m4-3---rename-root-ticket-id-to-key)
> **Execution record**:
> [docs/execution/M4-3.md](M4-3.md)

---

## Review Pass 1

> **Reviewer**: Phase B strict review
> **Date**: 2026-03-23

### Review Scope

Reviewed the M4-3 commit (`de293d9`) against the ticket scope defined in
[docs/implementation-plan.md](../implementation-plan.md#m4-3---rename-root-ticket-id-to-key),
the [M4-3 execution artifact](M4-3.md), and the
[terminology policy](../policies/terminology.md).

#### Artifacts reviewed

- [src/context_sync/_cli.py](../../src/context_sync/_cli.py) — CLI argument
  renames and `syncer` → `ctx` variable rename
- [src/context_sync/_sync.py](../../src/context_sync/_sync.py) — out-of-scope
  formatting change
- [src/context_sync/_testing.py](../../src/context_sync/_testing.py) —
  `make_syncer` → `make_context_sync` rename
- [tests/test_cli.py](../../tests/test_cli.py) — arg name and import updates
- [tests/test_e2e.py](../../tests/test_e2e.py) — `_make_args` defaults, imports,
  and variable names
- [tests/test_sync.py](../../tests/test_sync.py) — imports, variable names, and
  Path-variable disambiguation
- [tests/test_refresh.py](../../tests/test_refresh.py) — imports and variable
  names
- [tests/test_diff.py](../../tests/test_diff.py) — imports and variable names
- [tests/test_add_remove_root.py](../../tests/test_add_remove_root.py) —
  imports and variable names
- [docs/execution/M4-3.md](M4-3.md) — execution artifact

#### Reference checklists consulted

- [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md)
- [docs/policies/terminology.md](../policies/terminology.md)

### Findings (Pass 1)

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M4-3-R1 | Low | Done | CLI help text | The `sync` subcommand's positional-argument help text says "ticket to track" while the subcommand-level description says "Full-snapshot sync from a root ticket." The argument-level text dropped the "root" qualifier when the dest changed from `root_ticket` to `ticket`, creating a minor terminology gap: the `add` and `remove-root` commands still reference "root" in their argument help, but `sync` does not. | [src/context_sync/_cli.py:410-414](../../src/context_sync/_cli.py#L410-L414) — subcommand help says "root ticket"; [src/context_sync/_cli.py:413](../../src/context_sync/_cli.py#L413) — argument help says "ticket to track" | Users reading `sync --help` see inconsistent terminology between the command description and the positional argument description. Low practical impact since the sync command contextually implies root-ticket semantics. | Restore the "root" qualifier in the argument help text, e.g. `help="Issue key or Linear URL of the root ticket to track."`, or align the subcommand-level description to match. |
| M4-3-R2 | Low | Discarded | Scope | The commit includes two formatting-only changes in [src/context_sync/_sync.py](../../src/context_sync/_sync.py) that are outside M4-3's ticket scope: two multi-line `raise` statements in `remove_root()` were collapsed to single lines. The execution log attributes this to `ruff format` auto-formatting. | [src/context_sync/_sync.py:1442](../../src/context_sync/_sync.py#L1442) and [src/context_sync/_sync.py:1447](../../src/context_sync/_sync.py#L1447) — reformatted raise statements with no behavioral change | The change is purely cosmetic with zero behavioral risk, but it adds noise to the commit diff and makes it harder to identify the M4-3-scoped changes by inspection. | No code action needed; note for future discipline. Auto-formatter side effects in non-target files should ideally be committed separately or excluded from the ticket commit. |
| M4-3-R3 | Low | Done | Readability | In [tests/test_sync.py](../../tests/test_sync.py), six methods correctly renamed their `ctx` Path variable to `context_dir` to avoid shadowing the new `ctx` ContextSync variable. However, `test_workspace_mismatch_raises` at line 335 still uses `ctx = tmp_path / "ctx"` as a Path, while all other methods in the file use `ctx` exclusively for `ContextSync` instances. This is correct (no shadowing because the ContextSync instances are `ctx_a`/`ctx_b`) but creates a within-file naming inconsistency. | [tests/test_sync.py:335](../../tests/test_sync.py#L335) — `ctx` is a `Path`; compare to [tests/test_sync.py:370](../../tests/test_sync.py#L370) where `ctx` is a `ContextSync` | No runtime impact. A reader scanning the file may briefly misread `ctx` as a ContextSync instance at line 335. | Rename to `context_dir = tmp_path / "ctx"` for consistency with the six other methods that were already renamed. |

### Positive Observations (Pass 1)

- **Completeness**: The banned-term `syncer` has been fully eliminated from
  `src/` and `tests/`. Grep confirms zero remaining occurrences.
- **Mechanical correctness**: All `make_syncer` → `make_context_sync` and
  `syncer` → `ctx` renames are consistent and complete across all affected
  files. The `_make_args` defaults in
  [tests/test_e2e.py](../../tests/test_e2e.py) correctly collapsed the separate
  `root_ticket` / `ticket_ref` keys into a single `ticket` key.
- **Shadowing fix**: The Path-variable disambiguation in `test_sync.py` (six
  methods renamed from `ctx` to `context_dir`) was correctly scoped — only
  methods that would have had both a Path and ContextSync named `ctx` were
  changed.
- **Test validation**: 466 tests pass, ruff lint and format checks are clean.
- **No changelog entry needed**: Pre-1.0.0 repository; correctly noted in the
  execution file.
- **No temporary scaffolding**: The changes are final renames, not interim
  placeholders.

### Residual Risks (Pass 1)

- The `make_context_sync` rename in
  [src/context_sync/_testing.py](../../src/context_sync/_testing.py) is a
  breaking change for any downstream consumer that imports the test utility
  directly. Since this is a pre-1.0.0 internal test helper and no external
  consumers are known, the risk is negligible.
- The CLI positional argument dest changing from `root_ticket`/`ticket_ref` to
  `ticket` is a breaking change for any external tooling that constructs
  `argparse.Namespace` objects. Acceptable at 0.x per the plan.

---

## Review Pass 2

> **Reviewer**: Independent Phase B review
> **Date**: 2026-03-23
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/execution/M4-3.md](M4-3.md),
> [docs/execution/M4-R2.md](M4-R2.md),
> [docs/execution/M4-R2-review.md](M4-R2-review.md),
> [docs/policies/terminology.md](../policies/terminology.md),
> [src/context_sync/_cli.py](../../src/context_sync/_cli.py),
> [src/context_sync/_testing.py](../../src/context_sync/_testing.py),
> [src/context_sync/_sync.py](../../src/context_sync/_sync.py),
> [src/context_sync/_models.py](../../src/context_sync/_models.py),
> [src/context_sync/__init__.py](../../src/context_sync/__init__.py),
> [tests/test_cli.py](../../tests/test_cli.py),
> [tests/test_sync.py](../../tests/test_sync.py),
> [tests/test_e2e.py](../../tests/test_e2e.py),
> [tests/test_diff.py](../../tests/test_diff.py),
> [tests/test_package.py](../../tests/test_package.py),
> [tests/test_add_remove_root.py](../../tests/test_add_remove_root.py),
> [README.md](../../README.md)

### Review Scope (Pass 2)

Full independent review of M4-3 implementation against the ticket scope at
[docs/implementation-plan.md](../implementation-plan.md#m4-3---rename-root-ticket-id-to-key),
the [M4-R2 review](M4-R2.md) that shaped M4-3's broadened scope, the
[M4-3 execution artifact](M4-3.md), and the
[terminology policy](../policies/terminology.md). Reviewed all changed source
and test files, the README, and the `__init__.py` module docstring. Performed
repository-wide grep for banned terms and residual old names.

### Findings (Pass 2)

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M4-3-R4 | Low | Done | Terminology | The test method `test_syncer` in [tests/test_package.py:15](../../tests/test_package.py#L15) still contains the banned term "syncer" in its name. The prior review (Pass 1) claimed "zero remaining occurrences" in `tests/`, but this method name was missed. The method tests the `ContextSync` import, not a "syncer", so the name is both a terminology violation and misleading about what it verifies. | [tests/test_package.py:15](../../tests/test_package.py#L15) — `def test_syncer(self) -> None:` | The banned term persists in a test method name. While not user-facing, it contradicts the [terminology policy](../policies/terminology.md) and the M4-3 ticket's goal of eliminating `syncer` from the codebase. | Rename to `test_context_sync` or `test_core_import` to match what the method actually tests. |
| M4-3-R5 | Low | Done | Naming consistency | The private helper `_find_entry` in [tests/test_diff.py:41](../../tests/test_diff.py#L41) accepts a parameter named `ticket_id`, but it compares against `e.ticket_key`. M4-3's scope included renaming the `ticket_id` field to `ticket_key` on `SyncError` and `DiffEntry`. The test helper's parameter was not updated to match, creating a naming mismatch between the parameter and the field it looks up. | [tests/test_diff.py:41-46](../../tests/test_diff.py#L41-L46) — `def _find_entry(entries: list[DiffEntry], ticket_id: str) -> DiffEntry:` compares `e.ticket_key == ticket_id`; also line 46 error message says `ticket_key={ticket_id!r}` | A reader sees `ticket_id` as a parameter name in a file where the actual dataclass field is `ticket_key`, making the renamed field less discoverable. The error message also mixes both names. No runtime impact. | Rename the parameter from `ticket_id` to `ticket_key` and update the error message to match. |

### Reviewer Notes (Pass 2)

- I agree with all three findings from Pass 1. M4-3-R1 (help text root
  qualifier), M4-3-R2 (out-of-scope formatting), and M4-3-R3 (Path-variable
  consistency in `test_workspace_mismatch_raises`) are all valid observations.
  I did not create duplicate finding rows for them.

- The core M4-3 deliverables are correct and complete for the ticket's primary
  scope:
  - CLI positional argument dests are unified to `ticket` across `sync`, `add`,
    and `remove-root` in
    [src/context_sync/_cli.py](../../src/context_sync/_cli.py).
  - The `syncer` variable is fully eliminated from all CLI command handlers in
    [src/context_sync/_cli.py](../../src/context_sync/_cli.py).
  - `make_syncer` is renamed to `make_context_sync` in
    [src/context_sync/_testing.py](../../src/context_sync/_testing.py) with all
    docstring references updated.
  - All six test files have correct import and variable name updates.
  - The pre-existing library-level renames (`sync(key=...)`,
    `SyncError.ticket_key`, `DiffEntry.ticket_key`, docstring rewording,
    banned-term removal from `context_dir` property and `__init__.py` module
    docstring) are verified present in the current `main` state.

- The `__init__.py` module docstring at
  [src/context_sync/__init__.py:15-19](../../src/context_sync/__init__.py#L15-L19)
  now correctly uses `ctx` as the variable name and `ctx.sync(key="ACP-123")`
  as the example call, confirming that the M4-R2-R1 finding (from the M4-R2
  review) was addressed as part of the pre-existing work.

- The `context_dir` property docstring at
  [src/context_sync/_sync.py:270](../../src/context_sync/_sync.py#L270) now
  reads "The context directory this instance operates on." — the banned term
  from M4-R2's finding 6 was addressed.

- I verified that the `_id` → `_key` rename on `SyncError` and `DiffEntry` in
  [src/context_sync/_models.py](../../src/context_sync/_models.py) is correct:
  `ticket_key` at line 33 and line 92. The CLI formatter at
  [src/context_sync/_cli.py:90](../../src/context_sync/_cli.py#L90) and
  [src/context_sync/_cli.py:113-126](../../src/context_sync/_cli.py#L113-L126)
  correctly references `err.ticket_key` and `e.ticket_key`.

- The [README.md](../../README.md) already uses `TICKET` as the CLI
  placeholder and `ctx.sync(key=...)` in the library example. No
  remaining old terminology found.

- Repository-wide grep for `syncer` in `src/` returns zero matches, confirming
  complete elimination from production code. The single remaining match in
  `tests/` is the `test_syncer` method name captured in M4-3-R4.

- Repository-wide grep for `root_ticket` and `ticket_ref` in `tests/` returns
  only occurrences related to the `ticket_ref` traversal dimension (Tier 3
  configuration), `make_ticket_ref_provider`, and `per_root_tickets` data
  structures. These are unrelated to M4-3's rename scope; they are internal
  pipeline/traversal names for the Tier 3 edge-discovery concept, not the
  public API parameter names that M4-3 targeted. No findings warranted.

- I did not rerun lint, format, or test commands. The M4-3 execution artifact
  records that `ruff check`, `ruff format --check`, and `pytest` all passed
  cleanly, and no additional code changes have been made since that validation.

### Residual Risks and Testing Gaps (Pass 2)

- **No new residual risks beyond Pass 1.** The two new findings (M4-3-R4 and
  M4-3-R5) are low-severity naming leftovers with no runtime, behavioral, or
  security impact. They do not affect the correctness of the M4-3
  deliverables.

- **Testing gap: no negative test for old parameter names.** There is no test
  that verifies calling `sync(root_ticket_id=...)` or accessing
  `error.ticket_id` raises `TypeError` or `AttributeError`. This is a
  standard consequence of Python renames at 0.x and not a blocking concern,
  but a caller upgrading across this change would get no deprecation warning.
  Acceptable given the pre-1.0.0 status.

- **Execution artifacts reference old names in prose.** Historical execution
  artifacts under `docs/execution/` (such as
  [docs/execution/M1-1.md](M1-1.md),
  [docs/execution/M2-3.md](M2-3.md), and
  [docs/execution/M3-1.md](M3-1.md)) still mention `make_syncer` in their
  historical work logs. These are accurate records of what happened at the
  time and should not be retroactively edited. Not a finding, but noted for
  completeness.

## Ticket Owner Response

| ID | Verdict | Rationale |
| --- | --- | --- |
| M4-3-R1 | Fix now | Restored the "root" qualifier in the `sync` positional argument help text: `"Issue key or Linear URL of the root ticket to track."` at [src/context_sync/_cli.py:414](../../src/context_sync/_cli.py#L414). |
| M4-3-R2 | Discard | The `ruff format` side effect was a consequence of running the mandatory formatting check on the ticket scope. The two reformatted `raise` statements in [src/context_sync/_sync.py](../../src/context_sync/_sync.py) are correct formatter output with no behavioral impact. Excluding auto-formatter changes from the ticket commit would require manual staging that adds complexity without benefit at this project scale. Acknowledged as a process note. |
| M4-3-R3 | Fix now | Renamed the Path variable from `ctx` to `context_dir` in `test_workspace_mismatch_raises` at [tests/test_sync.py:335](../../tests/test_sync.py#L335) and updated both `context_dir=ctx` references to `context_dir=context_dir`. The file is now consistent: `ctx` is always a `ContextSync` instance, `context_dir` is always a `Path`. |
| M4-3-R4 | Fix now | Renamed `test_syncer` to `test_context_sync` at [tests/test_package.py:15](../../tests/test_package.py#L15). The method tests `ContextSync` importability; the new name matches the tested symbol. |
| M4-3-R5 | Fix now | Renamed the `ticket_id` parameter to `ticket_key` in `_find_entry` at [tests/test_diff.py:41](../../tests/test_diff.py#L41) and updated the error message to match. The parameter name now aligns with the `DiffEntry.ticket_key` field it looks up. |
