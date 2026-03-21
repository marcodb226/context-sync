# Review: [M2-2](../implementation-plan.md#m2-2---ticket-fetch-normalization-and-render-pipeline)

> **Status**: Phase B complete
> **Plan ticket**:
> [M2-2](../implementation-plan.md#m2-2---ticket-fetch-normalization-and-render-pipeline)
> **Execution record**:
> [docs/execution/M2-2.md](M2-2.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/coding-guidelines-python.md](../policies/common/coding-guidelines-python.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/adr.md](../adr.md#2-persistence-format),
> [docs/adr.md](../adr.md#41-error-handling-and-safety),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#21-context-directory-contents),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#4-error-handling),
> [docs/design/linear-domain-coverage-audit.md](../design/linear-domain-coverage-audit.md)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M2-2-R1 | Medium | Todo | Failure Safety | `write_ticket()` renames the old file and mutates the in-memory manifest before `write_and_verify_ticket()` has succeeded. If the atomic write or post-write verification then fails, the old filename is already gone and the directory can be left with stale content under the new issue key even though the new render was never accepted. | [src/context_sync/_pipeline.py:251](../../src/context_sync/_pipeline.py#L251), [src/context_sync/_pipeline.py:281](../../src/context_sync/_pipeline.py#L281), [src/context_sync/_io.py:79](../../src/context_sync/_io.py#L79), [docs/implementation-plan.md:313](../implementation-plan.md#L313), [tests/test_pipeline.py:386](../../tests/test_pipeline.py#L386) | A failed rename-path rewrite can still change the local snapshot into a misleading state: `OLD-1.md` disappears, `NEW-1.md` exists, but it can still contain the old content. That breaks the ticket-local acceptance guarantee and gives later readers a mismatched key/content pair after an error. | Delay the rename and manifest mutation until after the new file content has been written and verified successfully, or roll both back on failure. Add a regression test that forces `write_and_verify_ticket()` to fail during a key change and asserts the old file/path and manifest entry remain intact. |
| M2-2-R2 | High | Todo | Error Handling | `make_ticket_ref_provider()` catches bare `Exception` when resolving unknown issue keys and silently skips the edge. That downgrades systemic gateway failures into "missing ref" behavior even though the failure model requires systemic remote failures to abort the run and the traversal contract says provider exceptions propagate unchanged. | [src/context_sync/_pipeline.py:384](../../src/context_sync/_pipeline.py#L384), [src/context_sync/_traversal.py:350](../../src/context_sync/_traversal.py#L350), [docs/design/0-top-level-design.md:263](../design/0-top-level-design.md#L263), [docs/adr.md:483](../adr.md#L483), [docs/execution/M2-2.md:137](M2-2.md#L137), [tests/test_pipeline.py:490](../../tests/test_pipeline.py#L490) | A lost network/auth/rate-limit-exhausted failure during Tier 3 discovery can be silently converted into "no edge here," letting `sync` or `refresh` continue with an incomplete reachable graph. That can wrongly omit or prune tickets while the run appears successful. | Catch only the expected not-found or not-visible resolution outcome for unknown keys, and let systemic or unexpected gateway exceptions propagate. Add a test that distinguishes "unresolvable key" from `SystemicRemoteError` (or equivalent systemic gateway failure). |
| M2-2-R3 | Medium | Todo | Alias Resolution | The Tier 3 URL resolver only indexes current issue keys from already-fetched bundles and otherwise falls back to `gateway.fetch_issue(key)`. It never consults locally known alias history, even though M2-2's detailed notes call for manifest-based alias resolution and the ADR says references should resolve through the manifest rather than relying on Linear redirects. | [src/context_sync/_pipeline.py:332](../../src/context_sync/_pipeline.py#L332), [src/context_sync/_pipeline.py:369](../../src/context_sync/_pipeline.py#L369), [docs/implementation-plan.md:328](../implementation-plan.md#L328), [docs/design/0-top-level-design.md:157](../design/0-top-level-design.md#L157), [docs/adr.md:186](../adr.md#L186), [docs/adr.md:205](../adr.md#L205), [tests/test_pipeline.py:453](../../tests/test_pipeline.py#L453) | After an observed issue-key change, older descriptions or comments that still contain the previous key can lose their `ticket_ref` edge unless Linear happens to keep resolving that old key remotely. That weakens the repository's local alias guarantee and can make the reachable graph depend on upstream redirect behavior instead of local snapshot state. | Teach `make_ticket_ref_provider()` to consult locally known aliases before remote resolution, for example by accepting a manifest-backed key-to-UUID resolver or alias map alongside `fetched`. Add a regression test where a body references an old key for an already-known ticket and still resolves to the current UUID. |

## Reviewer Notes

- Validation was reproducible from the repo-local virtualenv:
  `.venv/bin/ruff check src tests` passed,
  `.venv/bin/ruff format --check src tests` passed,
  and `.venv/bin/pytest -v` passed all 304 tests during review.
- Two review-time probes confirmed the runtime findings above:
  forcing `write_and_verify_ticket()` to raise during an issue-key rename left
  `NEW-1.md` in place with the stale old file content, and a custom gateway
  that raised `SystemicRemoteError` during unknown-key resolution produced `{}`
  instead of propagating the failure.
- A third review-time probe confirmed the alias-resolution gap:
  when one fetched ticket referenced `OLD-2` and another already-fetched ticket
  had current key `NEW-2`, `make_ticket_ref_provider()` returned no edge
  because it does not consult local alias history.
- I did not find a Linear-boundary violation in this ticket.
  [src/context_sync/_pipeline.py](../../src/context_sync/_pipeline.py)
  stays within the approved gateway surface from
  [docs/design/linear-domain-coverage-audit.md](../design/linear-domain-coverage-audit.md).

## Residual Risks and Testing Gaps

- The current rename-path tests cover success and exception propagation, but
  they do not assert that a failed write leaves the old filename and manifest
  state untouched.
- `make_ticket_ref_provider()` is only tested for the happy path, plain
  unresolved keys, self-references, and deduplication. There is no test that a
  systemic gateway failure propagates, and no test that a previously observed
  alias inside fetched content resolves locally.
- The current provider API does not expose any manifest or alias lookup input,
  so if the project intends Tier 3 URL resolution to honor local aliases, the
  contract itself likely needs a small interface adjustment rather than only a
  local implementation tweak.
