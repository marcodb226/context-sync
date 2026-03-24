# M4-3 Review - API terminology cleanup

> **Reviewer**: Phase B strict review
> **Date**: 2026-03-23

## Review Scope

Reviewed the M4-3 commit (`de293d9`) against the ticket scope defined in
[docs/implementation-plan.md](../implementation-plan.md#m4-3---rename-root-ticket-id-to-key),
the [M4-3 execution artifact](M4-3.md), and the
[terminology policy](../policies/terminology.md).

### Artifacts reviewed

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

### Reference checklists consulted

- [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md)
- [docs/policies/terminology.md](../policies/terminology.md)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M4-3-R1 | Low | Todo | CLI help text | The `sync` subcommand's positional-argument help text says "ticket to track" while the subcommand-level description says "Full-snapshot sync from a root ticket." The argument-level text dropped the "root" qualifier when the dest changed from `root_ticket` to `ticket`, creating a minor terminology gap: the `add` and `remove-root` commands still reference "root" in their argument help, but `sync` does not. | [src/context_sync/_cli.py:410-414](../../src/context_sync/_cli.py#L410-L414) — subcommand help says "root ticket"; [src/context_sync/_cli.py:413](../../src/context_sync/_cli.py#L413) — argument help says "ticket to track" | Users reading `sync --help` see inconsistent terminology between the command description and the positional argument description. Low practical impact since the sync command contextually implies root-ticket semantics. | Restore the "root" qualifier in the argument help text, e.g. `help="Issue key or Linear URL of the root ticket to track."`, or align the subcommand-level description to match. |
| M4-3-R2 | Low | Todo | Scope | The commit includes two formatting-only changes in [src/context_sync/_sync.py](../../src/context_sync/_sync.py) that are outside M4-3's ticket scope: two multi-line `raise` statements in `remove_root()` were collapsed to single lines. The execution log attributes this to `ruff format` auto-formatting. | [src/context_sync/_sync.py:1442](../../src/context_sync/_sync.py#L1442) and [src/context_sync/_sync.py:1447](../../src/context_sync/_sync.py#L1447) — reformatted raise statements with no behavioral change | The change is purely cosmetic with zero behavioral risk, but it adds noise to the commit diff and makes it harder to identify the M4-3-scoped changes by inspection. | No code action needed; note for future discipline. Auto-formatter side effects in non-target files should ideally be committed separately or excluded from the ticket commit. |
| M4-3-R3 | Low | Todo | Readability | In [tests/test_sync.py](../../tests/test_sync.py), six methods correctly renamed their `ctx` Path variable to `context_dir` to avoid shadowing the new `ctx` ContextSync variable. However, `test_workspace_mismatch_raises` at line 335 still uses `ctx = tmp_path / "ctx"` as a Path, while all other methods in the file use `ctx` exclusively for `ContextSync` instances. This is correct (no shadowing because the ContextSync instances are `ctx_a`/`ctx_b`) but creates a within-file naming inconsistency. | [tests/test_sync.py:335](../../tests/test_sync.py#L335) — `ctx` is a `Path`; compare to [tests/test_sync.py:370](../../tests/test_sync.py#L370) where `ctx` is a `ContextSync` | No runtime impact. A reader scanning the file may briefly misread `ctx` as a ContextSync instance at line 335. | Rename to `context_dir = tmp_path / "ctx"` for consistency with the six other methods that were already renamed. |

## Positive Observations

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

## Residual Risks

- The `make_context_sync` rename in
  [src/context_sync/_testing.py](../../src/context_sync/_testing.py) is a
  breaking change for any downstream consumer that imports the test utility
  directly. Since this is a pre-1.0.0 internal test helper and no external
  consumers are known, the risk is negligible.
- The CLI positional argument dest changing from `root_ticket`/`ticket_ref` to
  `ticket` is a breaking change for any external tooling that constructs
  `argparse.Namespace` objects. Acceptable at 0.x per the plan.
