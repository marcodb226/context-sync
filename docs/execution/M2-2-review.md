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
| M2-2-R4 | Medium | Todo | Correctness | In `make_ticket_ref_provider`, after a successful gateway resolution, `key_to_id` is updated with `resolved.issue.issue_key` (line 389) but **not** with the original URL key `key`. If the gateway returns a bundle whose `issue_key` differs from the queried key — the realistic production case where a URL references an old key and Linear resolves it to the current bundle — line 393 (`target_id = key_to_id[key]`) raises `KeyError` because `key` was never inserted into the index. This exception is outside the `try/except` block and propagates unchanged through the traversal engine, crashing the sync run. `FakeLinearGateway` always returns bundles with `issue_key` matching the queried key, so no existing test exercises this path. | [src/context_sync/_pipeline.py:389](../../src/context_sync/_pipeline.py#L389), [src/context_sync/_pipeline.py:393](../../src/context_sync/_pipeline.py#L393), [src/context_sync/_testing.py:169](../../src/context_sync/_testing.py#L169), [tests/test_pipeline.py:471](../../tests/test_pipeline.py#L471) | Any ticket body containing a Linear URL that references a renamed issue key triggers an unhandled `KeyError` that aborts the sync pass. The module docstring and `test_skips_unresolvable_key` both imply the provider never raises for non-network reasons, but this path does — and the failure is silently absent from the test suite. | After a successful resolution add the queried URL key to the index alongside the current key: `key_to_id[key] = resolved.issue.issue_id`. Add a test where `gateway.fetch_issue(key)` returns a bundle with a different `issue_key` and verify the provider returns the correct edge without raising. |

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

---

## Review Pass 2 – Reviewer Notes

- Pass 1 findings [M2-2-R1](M2-2-review.md#findings),
  [M2-2-R2](M2-2-review.md#findings), and
  [M2-2-R3](M2-2-review.md#findings) were independently verified against the
  code and the evidence is accurate. All three remain valid.
- Reproduced the pass-1 probe for [M2-2-R1](M2-2-review.md#findings): the
  `write_and_verify_ticket` call at
  [src/context_sync/_pipeline.py:281](../../src/context_sync/_pipeline.py#L281)
  is reached after both the alias mutation at line 260 and the file rename at
  line 264; a simulated raise there leaves the rename and manifest mutation
  in place.
- Identified a new correctness bug recorded as
  [M2-2-R4](M2-2-review.md#findings): in
  [src/context_sync/_pipeline.py](../../src/context_sync/_pipeline.py),
  after a successful `gateway.fetch_issue(key)` call the local `key_to_id`
  dict receives only `resolved.issue.issue_key`, not the URL key `key` that
  triggered the lookup. When the resolved bundle's `issue_key` differs from
  `key` (the production case: old key in a URL, gateway returns current key),
  the lookup at line 393 raises `KeyError` outside the `try/except` block.
  The traversal contract lets all provider exceptions propagate unchanged,
  so this crashes the sync run instead of silently skipping the edge.
  `FakeLinearGateway.fetch_issue` always returns the bundle registered under
  the queried key
  ([src/context_sync/_testing.py:169](../../src/context_sync/_testing.py#L169)),
  so no current test reaches line 393 with a mismatched key.
- Linear-boundary compliance remains clean: no direct `linear.gql.*` calls in
  [src/context_sync/_pipeline.py](../../src/context_sync/_pipeline.py).
- Validation commands confirmed to pass at the time of this review pass.

## Review Pass 2 – Residual Risks and Testing Gaps

- No test covers the `make_ticket_ref_provider` path where
  `gateway.fetch_issue(key)` returns a bundle with `issue_key ≠ key`. This
  is the exact scenario that triggers [M2-2-R4](M2-2-review.md#findings) and
  it does not require unusual infrastructure — only a `FakeLinearGateway`
  entry whose stored `issue_key` is registered under a different lookup key.
- Gaps noted in pass 1 (rollback test for rename failure, systemic-error
  propagation test, alias-history resolution test) remain open.

---

## Ticket Owner Response

> **Status**: Phase C complete

| ID | Verdict | Disposition | Notes |
| --- | --- | --- | --- |
| M2-2-R1 | Fix now | Accepted | Restructure `write_ticket` so `write_and_verify_ticket` is called before any manifest mutation or filesystem rename. On success, delete the old file and commit alias and manifest updates; on failure the old file and manifest state are untouched. Add regression test asserting that a failed write during a rename leaves the old file present and the manifest unchanged. |
| M2-2-R2 | Fix now | Accepted | Replace bare `except Exception` with `except RootNotFoundError` so only the expected not-found/not-visible outcome is swallowed. All other gateway exceptions, including `SystemicRemoteError`, propagate unchanged through the provider to the traversal engine. Add test that `SystemicRemoteError` propagates instead of being silently dropped. |
| M2-2-R3 | Fix now | Accepted | Add `aliases: dict[str, str] | None = None` parameter to `make_ticket_ref_provider`. Before falling back to `gateway.fetch_issue`, check whether the URL key is in `aliases`; if so, resolve the UUID locally and skip the remote call. Add test where a body references an old key mapped in `aliases` and verify the correct UUID edge is returned without a gateway call. |
| M2-2-R4 | Fix now | Accepted | After a successful `gateway.fetch_issue(key)` call, index both `resolved.issue.issue_key` and the queried `key` into `key_to_id` so the lookup on the next line (`target_id = key_to_id[key]`) cannot raise `KeyError` when the gateway returns a bundle whose current key differs from the queried key. Add test where the gateway returns a bundle with a different `issue_key` than the queried key and verify the correct edge is returned without error. |
