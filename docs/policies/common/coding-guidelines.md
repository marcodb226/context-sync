# Coding Guidelines

## Scope

These guidelines apply to all Python source files in this project. Shell scripts and GitHub Actions workflow YAML files are also in scope for the general principles (documentation, explicitness, no silent failures). These guidelines also include repository-level release conventions that apply when the project publishes versioned releases. Language-specific sections apply only to the language named.

---

## General Principles

- **Documentation is a first-class deliverable.** Every source file must include a clear header docstring. Any arcane or non-obvious block of code must be annotated to summarize intent, side effects (if any), and outcome. Readable code with good comments is preferred over clever code with none.
- **Repository file references in Markdown must be clickable links.** In docs/execution/review Markdown files, when referencing a repository file, use a Markdown link. The rendered link text must be the path from repo root (for example: `docs/design/github-integration.md`), while the link target must be a relative path that is reachable from the current document.

- **All interfaces must be fully documented.** Public and internal interfaces alike must document expected inputs, outputs, raised exceptions, and relevant side effects. Docstrings must be concrete enough that behavior is understandable without reading the implementation.

- **DRY (Don't Repeat Yourself).** If the same behavior is needed in multiple places, extract shared helpers or modules rather than duplicating logic. If duplication is intentionally kept, document the reason in a code comment at both sites.

- **Use logging intentionally.** Emit meaningful operational events at `INFO` level and detailed diagnostic context at `DEBUG` level. Never log secrets, credentials, or tokens — not even partially. Log enough context that a failure is diagnosable without a debugger.

- **Fail loudly.** Defensive checks must not fail silently. When required state is missing or an operation cannot proceed safely, raise an explicit, descriptive exception and log context as appropriate. Never return quietly and defer failure downstream.

- **No hardcoded secrets.** Never hardcode credentials, API tokens, or secrets in source files or configuration files committed to the repository. All secrets must be read from environment variables at runtime. Maintain a documented `.env.example` file that enumerates required variables without values.

- **Never expose secrets in logs or error output.** Do not log secrets, tokens, or any value that could be used to authenticate — not even a prefix or suffix for debugging. Use opaque identifiers (e.g., the last 4 characters of a token ID, not the token itself) if correlation is needed.

- **Validate at system boundaries.** All external inputs — API payloads, webhook events, human-provided configuration — must be validated before entering internal logic. Raw unvalidated data must not be passed downstream.

---

## Repository Versioning and Changelog

These rules apply to repositories that publish versioned releases.

### Semantic Versioning

- Use Semantic Versioning (`MAJOR.MINOR.PATCH`) for release versions.
- Until the first stable release, use `0.y.z`.
- For `0.y.z` releases:
  - `y` increments may include breaking changes.
  - `z` increments are for non-breaking fixes or adjustments.
- The first stable public release is `1.0.0`.
- For `>=1.0.0` releases:
  - `MAJOR` for breaking changes to documented public behavior.
  - `MINOR` for backward-compatible features.
  - `PATCH` for backward-compatible bug fixes.

### Changelog

- Maintain a top-level `CHANGELOG.md` once the project starts publishing stable releases (`>=1.0.0`).
- Before the first stable release (`<1.0.0`), changelog maintenance may be optional.
- In repositories that have already shipped a stable release (`>=1.0.0`), any change to externally observable behavior relative to the previous release must be reflected in the upcoming `CHANGELOG.md`.
- Changelog-required behavior changes include changes to public interfaces, documented configuration semantics, externally visible error behavior, and other user-visible or operator-visible behavior.
- Each release entry should summarize user-visible changes.
- Prefer durable change categories such as Added, Changed, Fixed, Removed, Deprecated, and Security.

---

## Python-Specific

### Formatting and Linting

- Use **Ruff** as the single tool for both formatting and linting. No other formatter or linter is required.
- All code must pass `ruff check` and `ruff format --check` with no errors before merging.
- Ruff failures are blocking, not informational. A ticket must not be marked complete while either Ruff command is failing.
- "Pre-existing" or "out-of-scope" Ruff failures are not a waiver. If baseline Ruff is already failing, restore a passing Ruff baseline first (or treat that baseline break as a blocking prerequisite) before closing other tickets.
- Ruff configuration lives in `pyproject.toml`. Do not override it per-file unless there is a documented reason.

### Type Annotations

- **All structured data must be strongly typed.** Every class, dataclass, and container used to hold structured data must have explicit type annotations on all fields. Bare `dict`, `tuple`, or `list` used as ad-hoc data structures are not permitted — define a typed class instead.
- All function and method signatures must include type annotations for parameters and return types. No exceptions for internal helpers.
- Use **Pydantic** (`BaseModel` / `BaseSettings`) for data crossing trust or serialization boundaries (configuration, API payloads, persisted data). Use **`dataclass`** for internal state containers and private implementation structs. Do not use plain `dict` or untyped `dataclass` as structured data models at any boundary. See [`docs/policies/common/data-modeling.md`](<data-modeling.md>) for the full decision heuristic and examples.
- Use `from __future__ import annotations` at the top of files where forward references are needed, rather than quoting type names.
- Use `typing.Protocol` for structural interfaces rather than abstract base classes where duck typing is the intent.

### Async

- This project is async-first. All I/O — Linear API calls, GitHub API calls, file reads/writes in agent context, and any network operation — must use `async`/`await`. Do not use synchronous I/O in async contexts.
- Never call blocking functions (e.g., `time.sleep`, synchronous `requests`, synchronous file reads in a hot path) from within a coroutine. Use `asyncio.sleep` and `aiofiles` equivalents instead. If a blocking call is unavoidable, run it via `asyncio.get_event_loop().run_in_executor`.
- Use `asyncio.gather` for concurrent independent operations. Do not `await` them sequentially when they can run in parallel.
- Every async entry point (e.g., the polling loop) must handle `asyncio.CancelledError` cleanly and release resources before exiting.
- Do not mix sync and async code at module boundaries except at the outermost entry point (`asyncio.run`).

### Module Docstrings

- Module header docstrings must begin with triple quotes on their own first line:
  - Line 1: `"""`
  - Line 2+: header content
- Exception: single-line docstrings are allowed (`"""Short summary."""`) when the interface is simple and no additional detail is needed.

### Exception Handling

- Raise specific exception types. Define custom exception classes for domain errors (e.g., `TicketNotReadyError`, `ApprovalCheckFailed`) rather than raising bare `Exception` or `RuntimeError`.
- Distinguish retriable from non-retriable errors at the raise site. Retriable errors (transient API failures, rate limits) should be subclasses of a common `RetriableError` base so callers can handle them uniformly.
- Catch only the exceptions you can handle. Never use bare `except:` or `except Exception:` as a catch-all without re-raising or logging with full context.
- All retry logic must have a maximum iteration count. Do not implement unbounded retry loops. See the [ADR](<../../adr.md>) Runaway Loop Prevention section for the general policy.

### Testing

- Every new module must have a corresponding test file. Unit tests are required; integration tests are strongly encouraged where external APIs are involved.
- Use **pytest** as the test framework. Use `pytest-asyncio` for async test cases.
- Test failures are blocking for ticket completion in the same way lint/format failures are blocking.
- Mock external API calls (Linear, GitHub) in unit tests. Do not make live API calls in the unit test suite.
- Test the unhappy path explicitly. Every function that can raise must have at least one test that exercises the error condition.
- Test files live in a `tests/` directory mirroring the source tree. A module at `src/foo/bar.py` has its tests at `tests/foo/test_bar.py`.

### Security

- All variables that hold secrets (API tokens, passwords, credentials of any kind) must be typed as `pydantic.SecretStr`, never as `str`. This prevents secrets from being inadvertently serialized, logged, or exposed in stack traces. Access the underlying value only at the point of use via `.get_secret_value()`, and only in contexts where the value must be transmitted (e.g., an HTTP header). Do not store or pass the unwrapped value further than necessary.
- Validate all external inputs at system boundaries (Linear webhook payloads, GitHub webhook payloads, human-provided configuration) using Pydantic models. Do not pass raw unvalidated data into internal logic.

### Linear-Specific Domain Layer Boundary

- Changes that interact with Linear must stay within the `linear-client` domain layer. Any deviation requires an explicit exception documented in the applicable design artifact for the ticket.
