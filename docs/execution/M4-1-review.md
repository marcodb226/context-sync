# Review: [M4-1](../implementation-plan.md#m4-1---cli-surface-and-command-output-contracts)

> **Status**: Phase B complete
> **Plan ticket**:
> [M4-1](../implementation-plan.md#m4-1---cli-surface-and-command-output-contracts)
> **Execution record**:
> [docs/execution/M4-1.md](M4-1.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/coding-guidelines-python.md](../policies/common/coding-guidelines-python.md),
> [docs/policies/common/cli-conventions.md](../policies/common/cli-conventions.md),
> [docs/policies/common/cli-conventions-python.md](../policies/common/cli-conventions-python.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#2-cli-interface),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#4-error-handling)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M4-1-R1 | High | Todo | Runtime Wiring | Every CLI subcommand constructs `ContextSync(linear=...)`, but the public constructor still does not create a real gateway. When `linear` is provided, `ContextSync.__init__()` stores the raw client and leaves `self._gateway = None`, and each operation immediately raises `ContextSyncError` if `_gateway` is missing. Because the new `_run_sync()`, `_run_refresh()`, `_run_add()`, `_run_remove_root()`, and `_run_diff()` handlers all use that path, none of the documented CLI commands can complete a successful run in a real environment. | [src/context_sync/_cli.py:200](../../src/context_sync/_cli.py#L200), [src/context_sync/_cli.py:222](../../src/context_sync/_cli.py#L222), [src/context_sync/_cli.py:237](../../src/context_sync/_cli.py#L237), [src/context_sync/_cli.py:252](../../src/context_sync/_cli.py#L252), [src/context_sync/_cli.py:267](../../src/context_sync/_cli.py#L267), [src/context_sync/_sync.py:244](../../src/context_sync/_sync.py#L244), [src/context_sync/_sync.py:246](../../src/context_sync/_sync.py#L246), [src/context_sync/_sync.py:335](../../src/context_sync/_sync.py#L335), [src/context_sync/_sync.py:662](../../src/context_sync/_sync.py#L662), [src/context_sync/_sync.py:1186](../../src/context_sync/_sync.py#L1186), [src/context_sync/_sync.py:1349](../../src/context_sync/_sync.py#L1349), [src/context_sync/_sync.py:1470](../../src/context_sync/_sync.py#L1470), [docs/implementation-plan.md:499](../implementation-plan.md#L499), [tests/test_cli.py:377](../../tests/test_cli.py#L377) | The ticket is recorded as the CLI surface that lets human operators run `sync`, `refresh`, `add`, `remove-root`, and `diff`, but a real invocation can only reach the deliberate "No gateway available" failure path. The current CLI tests miss this entirely because they patch `_HANDLERS` instead of executing the shipped handlers. | Either wire the CLI through a real `Linear`-backed gateway before closing this ticket, or keep the ticket open and add handler-level tests that exercise the real dispatch path with an injectable fake gateway instead of patching `_HANDLERS` around the implementation. |
| M4-1-R2 | Medium | Todo | Error Contract | `--json` does not provide a machine-readable failure payload for bootstrap failures. `_create_linear_client()` logs an error and calls `sys.exit(1)` when `linear-client` cannot be imported or `Linear()` initialization fails, so `main()` never reaches its JSON error branch. That bypasses the ticket's promised "machine-readable output behavior for success and failure cases" for two common CLI failures: missing dependency and client/auth initialization failure. | [src/context_sync/_cli.py:170](../../src/context_sync/_cli.py#L170), [src/context_sync/_cli.py:182](../../src/context_sync/_cli.py#L182), [src/context_sync/_cli.py:191](../../src/context_sync/_cli.py#L191), [src/context_sync/_cli.py:466](../../src/context_sync/_cli.py#L466), [src/context_sync/_cli.py:470](../../src/context_sync/_cli.py#L470), [docs/implementation-plan.md:474](../implementation-plan.md#L474), [docs/execution/M4-1.md:13](M4-1.md#L13), [docs/execution/M4-1.md:87](M4-1.md#L87) | Automation that invokes `context-sync ... --json` cannot rely on parseable stdout for real startup failures. In those cases it gets stderr log text and an exit instead of the JSON error object the ticket says it defines. | Make `_create_linear_client()` raise a repository exception that `main()` can translate through the same text/JSON error surface as other operational failures. Add regression tests that cover `--json` import failure and `Linear()` initialization failure without patching away the real handler path. |
| M4-1-R3 | Medium | Todo | Input Validation | The parser accepts any integer for `--max-tickets-per-root` and the `--depth-*` overrides, but the library rejects non-positive caps and negative depths with `ValueError`. `main()` only catches `ContextSyncError`, so a configured environment will print a Python traceback for inputs like `--max-tickets-per-root 0` or `--depth-blocks -1` instead of a controlled CLI diagnostic. The test suite covers argparse flag/choice failures, but not these semantic validation paths. | [src/context_sync/_cli.py:303](../../src/context_sync/_cli.py#L303), [src/context_sync/_cli.py:367](../../src/context_sync/_cli.py#L367), [src/context_sync/_cli.py:466](../../src/context_sync/_cli.py#L466), [src/context_sync/_sync.py:255](../../src/context_sync/_sync.py#L255), [src/context_sync/_sync.py:257](../../src/context_sync/_sync.py#L257), [src/context_sync/_config.py:90](../../src/context_sync/_config.py#L90), [src/context_sync/_config.py:109](../../src/context_sync/_config.py#L109), [tests/test_cli.py:547](../../tests/test_cli.py#L547) | A malformed numeric argument escapes the CLI contract and turns into an uncaught traceback rather than a predictable usage or operational-error response. That is especially rough for shell users and breaks the non-interactive error story the ticket is supposed to define. | Validate positive integers at argparse time with a custom type/helper, or catch `ValueError` in `main()` and translate it into the same structured text/JSON failure surface. Add regression tests for zero and negative caps plus negative depth overrides. |

## Reviewer Notes

- Review scope covered [docs/execution/M4-1.md](M4-1.md),
  [src/context_sync/_cli.py](../../src/context_sync/_cli.py),
  [tests/test_cli.py](../../tests/test_cli.py), and the referenced library
  entry points in [src/context_sync/_sync.py](../../src/context_sync/_sync.py).
- I did not find a Linear-boundary violation in this ticket. CLI startup
  imports `linear_client.Linear` as allowed by
  [docs/design/0-top-level-design.md:132](../design/0-top-level-design.md#L132),
  and the subcommands still route operational behavior through
  [src/context_sync/_sync.py](../../src/context_sync/_sync.py) rather than
  introducing direct `linear.gql.*` usage.
- The execution record at [docs/execution/M4-1.md:37](M4-1.md#L37) and
  [docs/execution/M4-1.md:109](M4-1.md#L109) says `--verbose` / `-v` controls
  debug logging, but the shipped parser uses `--log-level` and reserves `-v`
  for `--version` at [src/context_sync/_cli.py:343](../../src/context_sync/_cli.py#L343)
  and [src/context_sync/_cli.py:349](../../src/context_sync/_cli.py#L349).
  I did not record that as a standalone finding because the runtime defects
  above are more urgent, but Phase C should correct the execution artifact.
- I did not rerun the repository lint, format, or test commands during this
  review. The current worktree diff is docs-only, and the repository policy
  says not to run the repo validation commands for docs-only work unless the
  user explicitly asks.

## Residual Risks and Testing Gaps

- [tests/test_cli.py](../../tests/test_cli.py) validates parser shape and
  patched `main()` behavior, but it never executes the real `_run_sync()`,
  `_run_refresh()`, `_run_add()`, `_run_remove_root()`, or `_run_diff()`
  handlers against a fake gateway. The end-to-end CLI wiring is therefore
  still effectively smoke-untested.
- There is no test coverage for the startup failure modes inside
  [src/context_sync/_cli.py](../../src/context_sync/_cli.py), especially the
  `--json` behavior when `linear-client` is missing or `Linear()` cannot be
  constructed.
- There is no regression test for semantically invalid numeric input. The
  current suite checks invalid flags and invalid `--missing-root-policy`
  values, but not zero or negative depth/cap arguments.
