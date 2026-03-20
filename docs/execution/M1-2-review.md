# Review: [M1-2](../implementation-plan.md#m1-2---manifest-lock-and-rendering-primitives)

> **Status**: Phase B complete
> **Plan ticket**:
> [M1-2](../implementation-plan.md#m1-2---manifest-lock-and-rendering-primitives)
> **Execution record**:
> [docs/execution/M1-2.md](M1-2.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/code-review.md](../policies/common/reviews/code-review.md),
> [docs/policies/common/coding-guidelines.md](../policies/common/coding-guidelines.md),
> [docs/policies/common/coding-guidelines-python.md](../policies/common/coding-guidelines-python.md),
> [docs/policies/common/data-modeling.md](../policies/common/data-modeling.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/adr.md](../adr.md#2-persistence-format),
> [docs/adr.md](../adr.md#61-snapshot-consistency-contract),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#21-context-directory-contents),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#22-ticket-file-rendering),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#7-risks-and-mitigations-tool-specific)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M1-2-R1 | High | Todo | Locking | `inspect_lock()` treats lock-read failures as if no lock exists. If the lock file is present but unreadable, the function returns `None` instead of surfacing a lock error, even though the design requires callers to inspect lock metadata before deciding whether they may proceed and requires `diff` to fail unless the lock is demonstrably stale. | [src/context_sync/_lock.py:239](../../src/context_sync/_lock.py#L239), [docs/design/0-top-level-design.md:178](../design/0-top-level-design.md#L178), [docs/design/0-top-level-design.md:182](../design/0-top-level-design.md#L182), [tests/test_lock.py:136](../../tests/test_lock.py#L136) | An unreadable lock can be mistaken for “no lock”, which weakens the single-writer contract and can let `diff` or a mutating flow proceed when they should stop. This is exactly the kind of fail-open behavior the lock metadata design was meant to avoid. | Treat read failures as `StaleLockError` or another explicit lock-read failure instead of returning `None`, and add a test that covers unreadable lock files. |
| M1-2-R2 | Medium | Todo | Rendering | The renderer does not actually nest replies under their parent comments. It emits the root comment once and then appends every non-root comment in one flat chronological list, regardless of reply depth, even though the ADR and top-level design require nested replies to be embedded directly under their parent rather than flattened into global thread order. | [src/context_sync/_renderer.py:323](../../src/context_sync/_renderer.py#L323), [docs/design/0-top-level-design.md:197](../design/0-top-level-design.md#L197), [docs/adr.md:229](../adr.md#L229), [tests/test_renderer.py:332](../../tests/test_renderer.py#L332) | Deep reply chains render with the right parent IDs in markers but the wrong human-readable structure. That is a user-visible contract mismatch, and it also makes the machine-owned comment structure less trustworthy for later parsing or drift checks. | Render threads recursively by parent-child relationship, preserving chronological order within each sibling set, and add a test that proves a reply-to-reply is rendered beneath its immediate parent rather than merely after it. |
| M1-2-R3 | Medium | Todo | Verification | The post-write verification path only checks the two section markers, not the thread and comment markers that the renderer contract also declares as required machine-readable structure. `expected_markers()` always returns the same four section markers even when the ticket contains threads and replies. | [src/context_sync/_renderer.py:99](../../src/context_sync/_renderer.py#L99), [src/context_sync/_io.py:120](../../src/context_sync/_io.py#L120), [docs/design/0-top-level-design.md:199](../design/0-top-level-design.md#L199), [docs/adr.md:233](../adr.md#L233), [tests/test_io.py:40](../../tests/test_io.py#L40) | A regression that drops or mangles `context-sync:thread` or `context-sync:comment` markers would still pass the ticket-write verification step. That leaves the code blind to drift in exactly the machine-owned structure later flows are supposed to rely on. | Extend the expected-marker set to include thread and comment markers derived from the rendered bundle whenever comments are present, and add verification-failure tests for missing thread/comment markers. |
| M1-2-R4 | Medium | Todo | Schema Validation | The manifest and lock schemas document finite state domains, but the models do not enforce them. `ManifestRootEntry.state`, `ManifestSnapshot.mode`, and `LockRecord.mode` are all plain `str` fields even though their own docstrings describe specific allowed values. | [src/context_sync/_manifest.py:39](../../src/context_sync/_manifest.py#L39), [src/context_sync/_manifest.py:48](../../src/context_sync/_manifest.py#L48), [src/context_sync/_manifest.py:76](../../src/context_sync/_manifest.py#L76), [src/context_sync/_manifest.py:90](../../src/context_sync/_manifest.py#L90), [src/context_sync/_lock.py:52](../../src/context_sync/_lock.py#L52), [src/context_sync/_lock.py:63](../../src/context_sync/_lock.py#L63), [tests/test_manifest.py:30](../../tests/test_manifest.py#L30), [tests/test_lock.py:27](../../tests/test_lock.py#L27) | These are disk-boundary models that later code will branch on. Accepting impossible values such as `state="bogus"` or `mode="surprise"` weakens the “fail loudly” contract for corrupted or hand-edited repository state and makes later control flow depend on undefined cases. | Replace the free-form strings with `Literal[...]` or enums for the documented value sets, and add rejection tests for invalid `state` and `mode` values. |

## Reviewer Notes

- Validation is reproducible from the repo-local virtualenv:
  `.venv/bin/ruff check src tests` passed,
  `.venv/bin/ruff format --check src tests` passed,
  and `.venv/bin/pytest -v` passed all 237 tests during review.
- Review-time probes in the virtualenv confirmed the main contract gaps above:
  invalid manifest and lock modes are currently accepted, an unreadable lock
  file is treated as absent, and `expected_markers()` returns only section
  markers even for tickets with comments.
- The implementation is otherwise in solid shape on the happy path. Atomic
  writes, deterministic ordering, manifest round-trip coverage, and the basic
  lock acquisition/preemption behavior all line up with the ticket intent.

## Residual Risks and Testing Gaps

- The current test suite is strong on deterministic happy-path rendering and
  parsing, but it is still relatively light on boundary-corruption cases. The
  review findings all came from cases where the repository state or nested
  structure becomes slightly irregular, not from the main golden-path tests.
- This review used repository artifacts, local code inspection, review-time
  probes, and the declared lint/format/test commands. No live Linear calls
  were needed or attempted.
