# Review: [M4-1](../implementation-plan.md#m4-1---cli-surface-and-command-output-contracts)

> **Status**: Phase B complete (two review passes)
> **Plan ticket**:
> [M4-1](../implementation-plan.md#m4-1---cli-surface-and-command-output-contracts)
> **Execution record**:
> [docs/execution/M4-1.md](M4-1.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/python/coding-guidelines.md](../policies/common/python/coding-guidelines.md),
> [docs/policies/common/cli-conventions.md](../policies/common/cli-conventions.md),
> [docs/policies/common/python/cli-conventions.md](../policies/common/python/cli-conventions.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#2-cli-interface),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#4-error-handling)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M4-1-R1 | High | Done | Runtime Wiring | Every CLI subcommand constructs `ContextSync(linear=...)`, but the public constructor still does not create a real gateway. When `linear` is provided, `ContextSync.__init__()` stores the raw client and leaves `self._gateway = None`, and each operation immediately raises `ContextSyncError` if `_gateway` is missing. Because the new `_run_sync()`, `_run_refresh()`, `_run_add()`, `_run_remove_root()`, and `_run_diff()` handlers all use that path, none of the documented CLI commands can complete a successful run in a real environment. | [src/context_sync/_cli.py:200](../../src/context_sync/_cli.py#L200), [src/context_sync/_cli.py:222](../../src/context_sync/_cli.py#L222), [src/context_sync/_cli.py:237](../../src/context_sync/_cli.py#L237), [src/context_sync/_cli.py:252](../../src/context_sync/_cli.py#L252), [src/context_sync/_cli.py:267](../../src/context_sync/_cli.py#L267), [src/context_sync/_sync.py:244](../../src/context_sync/_sync.py#L244), [src/context_sync/_sync.py:246](../../src/context_sync/_sync.py#L246), [src/context_sync/_sync.py:335](../../src/context_sync/_sync.py#L335), [src/context_sync/_sync.py:662](../../src/context_sync/_sync.py#L662), [src/context_sync/_sync.py:1186](../../src/context_sync/_sync.py#L1186), [src/context_sync/_sync.py:1349](../../src/context_sync/_sync.py#L1349), [src/context_sync/_sync.py:1470](../../src/context_sync/_sync.py#L1470), [docs/implementation-plan.md:499](../implementation-plan.md#L499), [tests/test_cli.py:377](../../tests/test_cli.py#L377) | The ticket is recorded as the CLI surface that lets human operators run `sync`, `refresh`, `add`, `remove-root`, and `diff`, but a real invocation can only reach the deliberate "No gateway available" failure path. The current CLI tests miss this entirely because they patch `_HANDLERS` instead of executing the shipped handlers. | Either wire the CLI through a real `Linear`-backed gateway before closing this ticket, or keep the ticket open and add handler-level tests that exercise the real dispatch path with an injectable fake gateway instead of patching `_HANDLERS` around the implementation. |
| M4-1-R2 | Medium | Done | Error Contract | `--json` does not provide a machine-readable failure payload for bootstrap failures. `_create_linear_client()` logs an error and calls `sys.exit(1)` when `linear-client` cannot be imported or `Linear()` initialization fails, so `main()` never reaches its JSON error branch. That bypasses the ticket's promised "machine-readable output behavior for success and failure cases" for two common CLI failures: missing dependency and client/auth initialization failure. | [src/context_sync/_cli.py:170](../../src/context_sync/_cli.py#L170), [src/context_sync/_cli.py:182](../../src/context_sync/_cli.py#L182), [src/context_sync/_cli.py:191](../../src/context_sync/_cli.py#L191), [src/context_sync/_cli.py:466](../../src/context_sync/_cli.py#L466), [src/context_sync/_cli.py:470](../../src/context_sync/_cli.py#L470), [docs/implementation-plan.md:474](../implementation-plan.md#L474), [docs/execution/M4-1.md:13](M4-1.md#L13), [docs/execution/M4-1.md:87](M4-1.md#L87) | Automation that invokes `context-sync ... --json` cannot rely on parseable stdout for real startup failures. In those cases it gets stderr log text and an exit instead of the JSON error object the ticket says it defines. | Make `_create_linear_client()` raise a repository exception that `main()` can translate through the same text/JSON error surface as other operational failures. Add regression tests that cover `--json` import failure and `Linear()` initialization failure without patching away the real handler path. |
| M4-1-R3 | Medium | Done | Input Validation | The parser accepts any integer for `--max-tickets-per-root` and the `--depth-*` overrides, but the library rejects non-positive caps and negative depths with `ValueError`. `main()` only catches `ContextSyncError`, so a configured environment will print a Python traceback for inputs like `--max-tickets-per-root 0` or `--depth-blocks -1` instead of a controlled CLI diagnostic. The test suite covers argparse flag/choice failures, but not these semantic validation paths. | [src/context_sync/_cli.py:303](../../src/context_sync/_cli.py#L303), [src/context_sync/_cli.py:367](../../src/context_sync/_cli.py#L367), [src/context_sync/_cli.py:466](../../src/context_sync/_cli.py#L466), [src/context_sync/_sync.py:255](../../src/context_sync/_sync.py#L255), [src/context_sync/_sync.py:257](../../src/context_sync/_sync.py#L257), [src/context_sync/_config.py:90](../../src/context_sync/_config.py#L90), [src/context_sync/_config.py:109](../../src/context_sync/_config.py#L109), [tests/test_cli.py:547](../../tests/test_cli.py#L547) | A malformed numeric argument escapes the CLI contract and turns into an uncaught traceback rather than a predictable usage or operational-error response. That is especially rough for shell users and breaks the non-interactive error story the ticket is supposed to define. | Validate positive integers at argparse time with a custom type/helper, or catch `ValueError` in `main()` and translate it into the same structured text/JSON failure surface. Add regression tests for zero and negative caps plus negative depth overrides. |

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

---

## Second Review Pass

### Agreement with First Review

I agree with all three findings from the first review pass:

- **M4-1-R1** (gateway wiring): Confirmed. The `ContextSync(linear=...)` path
  stores the raw client and sets `self._gateway = None`; every method
  immediately raises `ContextSyncError` before doing any work. The CLI is
  structurally inert in a real environment. I agree this is High severity.
- **M4-1-R2** (JSON bootstrap failure): Confirmed. `_create_linear_client()`
  calls `sys.exit(1)` directly, bypassing `main()`'s JSON error surface. I
  agree this is Medium severity.
- **M4-1-R3** (input validation): Confirmed. `ValueError` from the library
  propagates as an uncaught traceback. I agree this is Medium severity.

I also agree with the first reviewer's note about the execution artifact
claiming `--verbose` / `-v` when the code uses `--log-level` and `-v` /
`--version`. I have promoted that to a formal finding below (M4-1-R9) since
the execution record is the Phase B handoff artifact and its inaccuracy could
mislead an independent reviewer or Phase C responder.

### Additional Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M4-1-R4 | Medium | Done | Correctness | `_run_sync` passes `dimensions` and `max_tickets_per_root` to both the `ContextSync()` constructor and the `.sync()` per-call overrides. The `.sync()` overrides always take precedence, making the constructor values dead for this call. `_build_dimensions(args)` is also called twice, producing two throwaway dicts. The four other handlers correctly rely on constructor defaults only, so this handler is inconsistent with the rest of the dispatch surface. | [src/context_sync/_cli.py:201–211](../../src/context_sync/_cli.py#L201), [src/context_sync/_sync.py:290–294](../../src/context_sync/_sync.py#L290), [src/context_sync/_sync.py:342–347](../../src/context_sync/_sync.py#L342) | No runtime bug today because both paths receive the same values, but a maintenance change to one path without the other would introduce silent divergence. The redundancy also obscures the design intent — a reader must trace both the constructor and the method to understand which value actually governs behavior. | Pass `dimensions` and `max_tickets_per_root` only to `.sync()` (as per-call overrides) and let the constructor use defaults. Alternatively, pass them only to the constructor and call `.sync()` without overrides. Either approach removes the ambiguity. |
| M4-1-R5 | Low | Done | Code Quality | `_run_sync` uses a two-step `result = syncer.sync(...); result = await result` pattern that rebinds the name `result` from the coroutine to the resolved value. All four other handlers use the idiomatic `result = await syncer.method(...)` one-liner. | [src/context_sync/_cli.py:207–212](../../src/context_sync/_cli.py#L207), [src/context_sync/_cli.py:227](../../src/context_sync/_cli.py#L227), [src/context_sync/_cli.py:242](../../src/context_sync/_cli.py#L242), [src/context_sync/_cli.py:257](../../src/context_sync/_cli.py#L257), [src/context_sync/_cli.py:272](../../src/context_sync/_cli.py#L272) | Minor readability issue — the two-step form suggests a deliberate reason (e.g., interleaving work before the await) that does not exist, and the name reuse can confuse readers or static analyzers. | Collapse to `result = await syncer.sync(...)` to match the other handlers. |
| M4-1-R6 | Medium | Done | Error Contract | `_emit()` silently falls back to text output when `json_output` is `None` and `use_json` is `True`. The guard `if use_json and json_output is not None` means JSON mode produces human-readable text instead of JSON (or an error) when a caller passes `None` for the JSON payload. No current handler triggers this path, but the function's signature and docstring accept `None` as a valid value for `json_output`, so a future handler or refactor could hit it without warning. | [src/context_sync/_cli.py:130–146](../../src/context_sync/_cli.py#L130) | A `--json` invocation that silently emits text instead of JSON breaks the machine-readable output contract. Downstream automation parsing stdout as JSON would get a parse failure with no diagnostic about why the mode downgraded. | Either raise an error when `use_json=True` and `json_output is None` (fail-loud per coding guidelines), or remove the `None` optionality from the parameter and require callers to always supply the JSON payload. |
| M4-1-R7 | Low | Done | Code Quality | The handler dispatch table `_HANDLERS` is typed `dict[str, object]`, which erases the handler callable signature and forces a `# type: ignore[operator]` suppression at the `asyncio.run(handler(args))` call site. | [src/context_sync/_cli.py:427](../../src/context_sync/_cli.py#L427), [src/context_sync/_cli.py:467](../../src/context_sync/_cli.py#L467) | The type suppression disables static verification that every registered handler accepts `argparse.Namespace` and returns `int`. A mistyped handler would only surface at runtime. | Define a `Handler` type alias (e.g., `Callable[[argparse.Namespace], Coroutine[Any, Any, int]]`) and annotate `_HANDLERS` with it. Remove the `# type: ignore`. |
| M4-1-R8 | Medium | Done | Operational | The `--log-level OFF` code path calls `logging.disable(logging.CRITICAL)`, which is a process-global operation that silences all loggers in the current process, not just `context-sync` loggers. Separately, the `logging.basicConfig()` call (without `force=True`) is a no-op on any call after the first in the same process. Both issues are benign for a standalone `context-sync` invocation but break library callers who import and call `main()` as a function, and they make test-driven repeated `main()` calls unreliable for log-level verification. | [src/context_sync/_cli.py:453–460](../../src/context_sync/_cli.py#L453) | Library consumers who call `main(["diff", "--log-level", "OFF"])` lose their own logging for the rest of the process. Repeated `main()` calls in tests with different log levels silently keep the first call's configuration. | For `OFF`, set the `context_sync` package logger level to `CRITICAL + 1` instead of using `logging.disable()`. For `basicConfig`, either pass `force=True` (acceptable for a CLI entry point) or configure the package-level logger directly instead of relying on `basicConfig`. |
| M4-1-R9 | Low | Done | Documentation | The execution record at [docs/execution/M4-1.md](M4-1.md) claims `--verbose` / `-v` sets the root logger to DEBUG (lines 37 and 109), but the shipped parser reserves `-v` for `--version` and uses `--log-level` for diagnostic verbosity. The first reviewer noted this discrepancy in prose but did not record it as a finding. | [docs/execution/M4-1.md:37](M4-1.md#L37), [docs/execution/M4-1.md:109](M4-1.md#L109), [src/context_sync/_cli.py:343–354](../../src/context_sync/_cli.py#L343) | The execution record is the Phase B handoff artifact. An inaccurate claim about the CLI's flag surface could mislead Phase C or a future reviewer into thinking the implementation is wrong when the record is what is outdated. | Correct the execution record in Phase C: replace the `--verbose` / `-v` references with `--log-level` and note that `-v` is `--version` per [docs/policies/common/cli-conventions.md](../policies/common/cli-conventions.md). |

### Second-Pass Reviewer Notes

- Review scope: full re-read of [src/context_sync/_cli.py](../../src/context_sync/_cli.py),
  [tests/test_cli.py](../../tests/test_cli.py),
  [docs/execution/M4-1.md](M4-1.md), the design references at
  [docs/design/0-top-level-design.md §2](../design/0-top-level-design.md#2-cli-interface)
  and [§4](../design/0-top-level-design.md#4-error-handling), the library
  constructor and method entry points in
  [src/context_sync/_sync.py](../../src/context_sync/_sync.py), the config
  validation in [src/context_sync/_config.py](../../src/context_sync/_config.py),
  and the error hierarchy in
  [src/context_sync/_errors.py](../../src/context_sync/_errors.py).
- I confirmed the Linear-boundary check from the first review. No direct
  `linear.gql.*` usage in the CLI module; all operational behavior routes
  through [src/context_sync/_sync.py](../../src/context_sync/_sync.py).
- The `_VersionedParser` subclass at
  [src/context_sync/_cli.py:312](../../src/context_sync/_cli.py#L312) correctly
  includes the tool name and version in both help and error output, satisfying
  [docs/policies/common/cli-conventions.md](../policies/common/cli-conventions.md).
- The `-v` / `--version` reservation and `--log-level` (not `--verbose`)
  approach correctly follow
  [docs/policies/common/cli-conventions.md](../policies/common/cli-conventions.md).
- Changelog review: version is `0.1.0.dev0` (pre-stable), so the changelog
  gate does not apply.
- I did not rerun lint/format/test commands. The current worktree diff is
  docs-only.

### Second-Pass Residual Risks and Testing Gaps

The residual risks identified by the first review pass remain. Additional gaps:

- There is no test for `_build_dimensions()` in isolation — the test suite
  verifies argparse parsing of `--depth-*` flags but never exercises the
  function that transforms parsed args into the dict passed to the library.
- There is no test for `_emit()` edge cases, specifically the
  `use_json=True, json_output=None` fallback path identified in M4-1-R6.
- There is no test that exercises `main()` with different `--log-level`
  values in the same process to surface the `basicConfig` idempotency gap
  identified in M4-1-R8.

## Ticket Owner Response

| ID | Verdict | Rationale |
| --- | --- | --- |
| M4-1-R1 | Fix now | The CLI handlers currently only exercise the `_create_linear_client()` → `ContextSync(linear=...)` path, which has no real gateway. The real gateway adapter is out of scope for M4-1, but handler-level tests that exercise the shipped handlers against `FakeLinearGateway` via `_gateway_override` are within scope and will close the wiring gap the review identified. Refactor handlers to accept an optional gateway override so tests can inject a fake without patching. |
| M4-1-R2 | Fix now | Replace `sys.exit()` calls in `_create_linear_client()` with a `ContextSyncError` raise so `main()` routes both import-failure and init-failure through the same text/JSON error surface. Add regression tests for both paths. |
| M4-1-R3 | Fix now | Catch `ValueError` in `main()` alongside `ContextSyncError` and route it through the same structured error surface. Add tests for `--max-tickets-per-root 0` and `--depth-blocks -1`. |
| M4-1-R4 | Fix now | Pass `dimensions` and `max_tickets_per_root` only to `.sync()` as per-call overrides; let the constructor use defaults. |
| M4-1-R5 | Fix now | Collapse to `result = await syncer.sync(...)` to match the other handlers. |
| M4-1-R6 | Fix now | Remove the `None` optionality from `json_output` and make it a required `dict`. Callers always have a payload available from `asdict()`. |
| M4-1-R7 | Fix now | Define a `_Handler` type alias with the proper async callable signature and annotate `_HANDLERS`. Remove the `# type: ignore`. |
| M4-1-R8 | Fix now | Replace `logging.disable()` with a package-level logger configuration. Use `force=True` in `basicConfig` so repeated `main()` calls in tests work correctly. |
| M4-1-R9 | Fix now | Correct the execution record: replace `--verbose` / `-v` references with `--log-level` and note that `-v` is `--version` per [docs/policies/common/cli-conventions.md](../policies/common/cli-conventions.md). |
