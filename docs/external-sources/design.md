# Design Spec: Async Linear Client Library (OAuth and Client-Credentials)

## Introduction

We don't want to reinvent the wheel and we would definitely prefer to use an existing library, but I double-checked the open-source landscape, and while there is an official TypeScript SDK (`@linear/sdk`) and a few synchronous Python wrappers (for example `linear-python` and `linear-api` which rely on the synchronous `requests` library), there is no widely adopted, fully async Python client tailored for rigorous environments like Temporal.

This file defines shared/cross-layer design requirements. Layer-specific details are defined in:
- [docs/design/domain-layer.md](domain-layer.md)
- [docs/design/gql-layer.md](gql-layer.md)

## Purpose

Provide a **fully async** Python library for interacting with Linear over GraphQL, suitable for use inside **Temporal Activities** (network I/O) and other async services. The library must support two authentication models:

- **Client-credentials** (primary focus): fully bootstrapped in agent code, no human interaction at runtime.
- **OAuth authorization-code plus refresh** (secondary): requires an initial human authorization step, then refreshes automatically.

The library must expose an instance of a class that can:

- Read issues (tickets)
- Update issues
- Create issues
- Link issues
- Run arbitrary GraphQL queries and mutations
- Support paginated GraphQL connections
- Resolve the authenticated principal as a domain `User` (`await linear.me()`)

In addition to raw GraphQL access, the library must expose:
- a first-class domain abstraction layer (`Issue`, `User`, `Status`, `Team`, `Label`, `Comment`, `Attachment`, `FileUpload`, `IssueLink`) via top-level `Linear` factories as the primary interface, and
- a first-class GraphQL services namespace at `linear.gql.*` as the fallback layer for lower-level operations.

## Cross-Layer Context

The previous library shape exposed typed GraphQL service models (for example `IssueModel`, `UserModel`, `StatusModel`) as the main ergonomics path. In practice, higher-level code ended up juggling multiple identifiers and representations for the same concept (issue id versus issue key, status name versus status id, user name versus user id). This produced:

- Duplicate parameters across nearly every call.
- Multiple “dimensions” of the same data flowing through the API.
- An object graph represented as primitive fields instead of first-class relationships (`issue.status` as string/id pairs instead of a `Status` instance).
- Higher-level wrappers that still left mapping burden on callers.

The current design resolves that by keeping both layers explicit:

- A domain abstraction layer (`linear_client.domain.*`) as the primary developer-facing API.
- A GraphQL services layer (`linear.gql.*`) for raw and service-level GraphQL operations when domain APIs are not sufficient.

## Cross-Layer Goals

1. **Clearly separate the two layers**

   - The **domain abstraction layer** is the primary layer and exposes first-class domain objects and business-oriented operations.
   - The **GraphQL services layer** (`Linear.gql.*`) is the lower-level fallback layer and owns raw GraphQL access, GraphQL services, typed GraphQL models/DTOs, and transport/auth integration.
   - Responsibilities and APIs between the two layers must remain explicit and non-overlapping.

2. **First-class names and relationships**

   - Use names that match Linear’s domain: `Issue`, `User`, `Status`, `Team`, `Label`, `Comment`, `Attachment`, `FileUpload`, `IssueLink`.
   - Represent relationships as objects:
     - `Issue.assignee` is a `User`
     - `Issue.creator` is a `User` (read-only relationship)
     - `Issue.status` is a `Status`
     - `Issue.team` is a `Team`
     - `Label.parent` and `Label.children` represent label hierarchy relationships.

3. **Lazy loading with smart getters**

   - Domain objects may be constructed partially (for example `User(name="Marco")`).
   - No network calls occur during construction.
   - Accessing a value via a smart getter may trigger fetch.
   - Callers can explicitly avoid fetches using sync `peek_*` methods (for example `peek_id()`).

4. **Move issue-centric operations onto Issue (no setters)**

   - Issue instance methods should be the primary mutation surface.
   - Mutations are explicit and trigger GraphQL immediately:
     - `Issue.create()` creates a draft issue object in Linear
     - `Issue.assign(user)` changes the assignee
     - `Issue.transition(status)` changes the status
     - `Issue.update(...)` changes other fields
   - At the domain abstraction layer, expose simple collection operations on `Team`:
     - `Team.search_issues(...) -> IssueSearchPage`
     - `Team.list_statuses()`
     - `Team.list_users()`
   - Keep `Linear.gql.*` for advanced/flexible query scenarios.

5. **Add missing first-class support for comments, attachments, and file uploads**

   - The design must include `Comment`, `Attachment`, and `FileUpload` as first-class objects.
   - `fetch()` populates object metadata only and must not download file bytes.
   - `FileUpload.download(path=...)` downloads file bytes to the local file system (requires a destination path).

6. **Preserve low-level GraphQL abstractions**

   - Raw GraphQL classes, documents, and transport/auth layers remain; this change is about the public domain abstraction layer.
   - Existing low-level classes are repositioned under `Linear.gql.*` naming, without changing their core responsibilities.

7. **Reconcile provisional objects into canonical identity-mapped objects**

   - Domain construction stays no-I/O, so objects created from non-id selectors (for example `User(name=...)`) are provisional until id resolution.
   - Once a provisional object resolves an id, the domain layer must reconcile it with the per-client identity map for `(type, id)`.
   - If a canonical instance already exists for that id, behavior must converge on that canonical instance instead of allowing long-lived duplicate instances to drift.

8. **Expose issue creator and timestamp metadata as first-class reads**

   - Both layers must expose issue creator and issue lifecycle timestamps.
   - `creator` is read-only metadata (no mutation surface for changing creator).
   - Timestamp metadata must include:
     - `created_at`
     - `updated_at` (canonical last-modified timestamp)
     - `completed_at`
     - `canceled_at`
     - `started_at`
     - `due_date`

9. **Use shared cursor-page contracts for page-returning collection reads**

   - Domain page-returning collection reads use `CursorPage[T]` with concrete
     specializations such as `IssueSearchPage`.
   - GraphQL service page-returning collection reads use
     `CursorPageModel[TModel]` with concrete specializations such as
     `IssueSearchPageModel`.
   - The `v1.1.0` reference shape is page-first:
     `Team.search_issues(...) -> IssueSearchPage` and
     `linear.gql.issues.search(...) -> IssueSearchPageModel`.

## Cross-Layer Non-goals

- Providing backward compatibility for existing `*Model` classes (for example `IssueModel`) or existing `*Service` classes and their method signatures. These may be renamed, reshaped, or made internal as needed to support the domain-object API.
- Transitional compatibility shims for legacy domain-layer APIs. The design uses an immediate cutoff to the domain-object API.
- Rewriting transport, retry, auth providers, token store, or raw GraphQL execution APIs.
- Changing existing GraphQL service/model behavior in ways unrelated to the documented two-layer API contracts (for example selector semantics, label scope/hierarchy semantics, and domain bridge contracts).
- Changing existing environment variable names or configuration precedence
  rules. Adding new optional env vars is allowed only if it does not change
  the meaning or defaults of existing ones.
- Perfect identity disambiguation for ambiguous selectors (for example multiple users with the same display name). Deterministic resolution rules and explicit ambiguity errors are sufficient.

## Layer Ownership and Filesystem Split

### Layering

**Domain abstraction layer (top-level `Linear` API)**

- Exposes first-class domain objects as the primary developer API.
- Domain classes (uppercase): `Issue`, `User`, `Status`, `Team`, `Comment`, `Attachment`, `FileUpload`, `Label`, `IssueLink`.
- Domain factory methods remain top-level on `Linear`, for example:
  - `linear.issue(...) -> Issue`
  - `linear.user(...) -> User`
  - `linear.status(...) -> Status`
  - `linear.team(...) -> Team`
  - `linear.comment(...) -> Comment`
  - `linear.attachment(...) -> Attachment`
  - `linear.file_upload(...) -> FileUpload`
  - `linear.label(...) -> Label`
  - `await linear.me() -> User`
- Domain objects call repositories; repositories call `Linear.gql.*`.
- Cursor-backed domain collection reads use shared page types. In `v1.1.0`,
  the reference example is `Team.search_issues(...) -> IssueSearchPage`.

**GraphQL services layer (`Linear.gql.*`)**

- Owns all low-level/raw GraphQL access.
- Contains facade/service/model capabilities under the explicit `gql` package.
- Includes:
  - raw operations: `linear.gql.gql(...)`, `linear.gql.query(...)`, `linear.gql.mutate(...)`, `linear.gql.paginate_connection(...)`
  - GraphQL services: `linear.gql.issues`, `linear.gql.users`, `linear.gql.statuses`, `linear.gql.labels`
  - GraphQL typed models (or equivalent internal DTOs) used by that layer
  - GraphQL documents and mapping helpers
- Page-returning service reads use shared Pydantic page models. In `v1.1.0`,
  the reference example is
  `linear.gql.issues.search(...) -> IssueSearchPageModel`.

### Filesystem structure (explicit split)

```text
src/linear_client/
  domain/                     # Domain abstraction layer
    issue.py
    user.py
    status.py
    team.py
    label.py
    comment.py
    attachment.py
    file_upload.py
    issue_link.py
    bridges.py
    repos/
      ...

  gql/                        # GraphQL services layer
    facade.py
    models.py
    services/
      issues.py
      users.py
      statuses.py
      labels.py
```


**Adjusted service layer responsibilities**

- GraphQL services remain the home for list/search/resolve operations and raw access, under `Linear.gql.*`.
- `Linear.gql.*` stays primitive-selector oriented (no domain-object coupling).
- Domain objects call into GraphQL services via repositories.

### GraphQL Service API Positioning and Evolution

- Existing GraphQL-oriented service APIs are retained as the low-level layer, but repositioned under `Linear.gql.*`.
- `Linear.gql.*` remains primitive-selector based; domain-object input adaptation belongs in repositories/domain layer.
- Do not introduce parallel `*ServiceV2` types solely for namespace changes.
- Domain-layer evolution happens above this layer via repositories and first-class objects.

## Requirements

### Functional

1. **Async-only API**
   - All public operations are `async def`.
   - Uses `httpx.AsyncClient` for HTTP.
   - Suitable for Temporal Activities; do not call from Temporal Workflows.

2. **Authentication modes**
   - **Client-credentials**: obtain access token via token endpoint; cache and refresh/re-acquire as needed.
   - **OAuth**: support initial authorization-code exchange (human bootstrap) and refresh tokens afterward.

3. **Token persistence**
   - Support persistent token storage in a JSON file so restarts do not require re-authentication.
   - Token store location is controlled by an environment variable (see below).
   - The JSON file format must support both auth modes (same file).

4. **Official domain API (domain abstraction layer: top-level factories + domain objects)**
   - The library must provide top-level factories on `Linear`:
     - `issue`, `user`, `status`, `team`, `label`, `comment`, `attachment`, `file_upload`
   - The library must provide `async Linear.me() -> User`, resolving the authenticated principal from credentials.
   - Domain objects must support lazy fetch/get/peek semantics and explicit instance-oriented mutations where applicable.
   - Team-scoped domain collection methods must include:
     - `Team.search_issues(...) -> IssueSearchPage`
     - `Team.list_statuses`
     - `Team.list_users`
     - `Team.list_labels` (UI-visible labels for that team context: team-owned + global/workspace)
   - Domain `Label` objects must expose hierarchy relationships (`parent`, `children`) as first-class object references, backed by identity-mapped `Label` instances.

5. **GraphQL operations (GraphQL services layer fallback: `linear.gql.*`)**
   - Provide:
     - `linear.gql.query(...)` for GraphQL queries
     - `linear.gql.mutate(...)` for GraphQL mutations
     - `linear.gql.paginate_connection(...)` helper for Relay-style connections (`edges`, `node`, `pageInfo`, `endCursor`, `hasNextPage`, `after`)
   - Provide a convenience `gql(...)` method as a single entry point for callers that do not want to distinguish query versus mutation.

6. **Official GraphQL service APIs (GraphQL services layer fallback: `linear.gql.*`)**
   - The library must provide `linear.gql.issues` as a stable, documented public interface with:
     - `get`
     - `search` (returns `IssueSearchPageModel`)
     - `create`
     - `update`
     - `next_status` (advance an issue to a target workflow status by name or id)
     - `assign`
     - `link` (link type required argument)
   - The library must provide `linear.gql.users` as a stable, documented public interface with:
     - `list` (retrieve users with optional filtering and pagination)
     - `resolve_id` (map exact user `name` or `email` to user id; provide one selector only)
   - The library must provide `linear.gql.statuses` as a stable, documented public interface with:
     - `resolve_id` (map a status name to a status id within team scope)
     - `list` (retrieve all workflow statuses for a team)
   - The library must provide `linear.gql.labels` as a stable, documented public interface with explicit label-scope behavior:
     - `list` with optional `local_only: bool = True` argument
       - `local_only=True` (default): strict team-owned labels only
       - `local_only=False`: labels visible in issue-creation context for the team (team-owned + global/workspace)
       - archived/removed labels are excluded
     - `LabelModel` returned by labels service must include hierarchy metadata:
       - `parent_id: str | None` (direct parent selector when available from schema)
       - `child_ids: list[str]` (derived from the returned label collection by grouping on `parent_id`)
     - Hierarchy support must not require a separate list API; it is part of `labels.list(...)`.

7. **Configuration precedence**
   - All env-backed settings must have constructor overrides.
   - If a value is provided both via constructor and environment, constructor value wins.

### Non-functional

1. **Reliability**
   - Retry policy for transport errors and retryable HTTP status codes.
   - Respect `Retry-After` when present.
   - Avoid blind retries of mutations by default (to reduce duplicate side effects); allow opt-in.

2. **Observability**
   - Structured logging hooks (callers can pass a logger or the library uses standard Python logging).
   - Log request attempts and retries without leaking secrets.

3. **Reusability and configurability**
   - Do not hardcode team ids, workflow state ids, labels, or other org-specific constants in the library.
   - Provide reusable building blocks (transport, auth providers, token store) that can be composed.
   - The `issues` service must remain parameterized (caller supplies ids/names); any defaults may come from constructor/global config and must be overridable.

4. **Documentation quality (code)**
   - Every Python file must have clear header documentation describing:
     - the module’s purpose,
     - key types and responsibilities,
     - usage notes (especially Temporal constraints, if applicable).
   - All public classes, functions, and methods must have complete docstrings:
     - parameters and types,
     - return types,
     - raised exceptions,
     - behavioral notes (retry semantics, caching, side effects).
   - Public interfaces must be understandable without reading implementation details.

5. **Testability**
   - Unit tests must be defined and run as part of CI.
   - All external HTTP interactions must be mockable.
   - Core behaviors (token file parsing, retries, error mapping, auth flows) must have unit coverage.

6. **Separation of concerns**
   - Library configuration is separate from worker runtime configuration.
   - The library still consumes the **same environment variables** as today (no renames).

7. **Packaging flexibility**
   - The library must be usable as:
     - a standard Python package installed via tooling (recommended), and
     - a vendored copy (copying the package source directory into another repo) without code changes.
   - `pyproject.toml` is the single source of truth for dependency metadata.

8. **Dependency metadata**
   - Source checkouts should install dependencies through package metadata (for example `pip install .` or `pip install -e .[test]`).
   - Vendored/copy-source consumers must provide the runtime dependencies declared in `pyproject.toml`.

9. **Secret safety**
   - Sensitive values (for example `client_secret`, `oauth_code`, `access_token`, and `refresh_token`) must be represented in memory with Pydantic secret types (`SecretStr`) so accidental `print`/`repr` output is redacted by default.

10. **Strong typing by default**
   - Public service APIs should return strongly typed models whenever practical.
   - Avoid generic `dict` return types for service-layer methods unless dynamic/raw payload behavior is explicitly required.
   - Keep low-level raw GraphQL methods (`query`, `mutate`, `gql`) as dictionary-based escape hatches.

11. **Integration harness UX and error handling**
   - The real-network integration harness CLI must handle configuration/client/runtime failures gracefully.
   - It must print clear, actionable user-facing error messages (for example missing `<PREFIX>LINEAR_CLIENT_ID`) and avoid uncaught Python tracebacks for expected failures.
   - It must return stable non-zero exit codes for error classes so operators can automate failure handling.

12. **Documentation delivery (package + site)**
   - The project must maintain high-fidelity package documentation from the same canonical sources used by engineering (design docs + docstrings).
   - A MkDocs site should be the primary documentation experience.
   - GitHub Pages publication is a future goal and is deferred until the repository is public.

---

## Global Configuration (Constructor-First)

The library configuration model is constructor-first. Callers instantiate `Linear(...)` with explicit parameters, and those values become the source of truth on the object.

### Constructor parameters (global)

The primary constructor should accept global configuration parameters such as:

- `auth_mode` (`"oauth"` | `"client_credentials"`, default `"oauth"`)
- `client_id`
- `client_secret`
- `oauth_scope`
- `oauth_token_path` (default `~/.linear_client_oauth.json`)
- `oauth_url` (default `https://api.linear.app/oauth/token`)
- `oauth_skew_seconds`
- `oauth_code` (OAuth bootstrap only)
- `oauth_redirect_uri` (OAuth bootstrap only)
- `api_url` (default Linear GraphQL endpoint)
- `file_base_dir` (optional default directory prefix for domain-layer file download/local caching flows)
- `env_prefix` (maps to `LINEAR_ENV_PREFIX` behavior)

All resolved constructor values should be available on object/config properties and used by internal components. Implementation code should reference these resolved properties rather than reading environment variables directly during operation.

### Precedence rules

- Constructor arguments are authoritative.
- If a constructor value is not provided, resolve from environment variables (with optional prefix).
- If neither constructor nor environment provides a value, use documented library defaults where available.

### Environment variables (defaults source)

Environment variables are retained as a defaults mechanism for constructor parameters, not as the primary interface.

#### Namespacing

- `LINEAR_ENV_PREFIX`
  - If set, the library reads Linear configuration from variables prefixed with that value.
  - Example: if `LINEAR_ENV_PREFIX="PM_"`, then `<PREFIX>LINEAR_CLIENT_ID` resolves to `PM_LINEAR_CLIENT_ID`.
  - If empty or unset, variables are read without a prefix.
- `<PREFIX>`
  - In this document, `<PREFIX>` means “the resolved environment prefix”.
  - Variables written as `<PREFIX>LINEAR_*` are prefix-aware and are read with the resolved prefix when present.

#### Auth and token management

All of the following are read with the optional prefix applied:

- `<PREFIX>LINEAR_CLIENT_ID` (required)
- `<PREFIX>LINEAR_CLIENT_SECRET` (required)
- `<PREFIX>LINEAR_OAUTH_SCOPE` (required in `client_credentials` mode; comma-separated list)
- `<PREFIX>LINEAR_OAUTH_TOKEN_PATH` (optional; defaults to `~/.linear_client_oauth.json`)
- `<PREFIX>LINEAR_OAUTH_URL` (optional; defaults to Linear’s token endpoint)
- `<PREFIX>LINEAR_OAUTH_SKEW_SECONDS` (optional; defaults to a small safety margin)
- `<PREFIX>LINEAR_OAUTH_CODE` (optional; OAuth bootstrap only)
- `<PREFIX>LINEAR_OAUTH_REDIRECT_URI` (optional; OAuth bootstrap only)

> If `auth_mode="client_credentials"`, the library must not require `oauth_code` or `oauth_redirect_uri`.

#### GraphQL API endpoint

- `<PREFIX>LINEAR_API_URL` (optional; defaults to Linear GraphQL endpoint)

#### General library behavior

- `<PREFIX>LINEAR_LOG_LEVEL` (optional; shared library default log level for tooling/consumers that expose log-level configuration; valid values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `OFF`)

#### Domain-layer file handling

- `<PREFIX>LINEAR_FILE_BASE_DIR` (optional; default directory prefix for domain-layer file download/local caching paths)

#### Non-prefixed variables (do not use `<PREFIX>`)

- `LINEAR_ENV_PREFIX` (prefix selector itself)

The following two variables are not consumed by the library, they're only consumed by the harness,
but we're listing them here for completeness:
- `LINEAR_HARNESS_AUTH_MODE` (integration harness default auth mode override)
- `LINEAR_HARNESS_LOG_LEVEL` (integration harness-specific log-level override)
- `LINEAR_HARNESS_TEAM_KEY` (integration harness default `--team-key` when CLI flag is omitted)
- `LINEAR_HARNESS_ASSIGNEE` (integration harness default `--assignee` when CLI flag is omitted)


---

## Public API

### Primary entry point

Provide a single primary class that callers instantiate.

Example usage:

```python
from linear_client import Linear

async with Linear(auth_mode="oauth") as linear:
    team = linear.team(key="ABC")
    statuses = await team.list_statuses()
```

**Class: `Linear`**
- `def __init__(..., *, auth_mode: Literal["oauth", "client_credentials"] = "oauth", client_id: str | None = None, client_secret: str | None = None, oauth_scope: str | None = None, oauth_token_path: str | None = None, oauth_url: str | None = None, oauth_skew_seconds: int | None = None, oauth_code: str | None = None, oauth_redirect_uri: str | None = None, api_url: str | None = None, env_prefix: str | None = None, ...)`
  - Resolves each parameter from constructor first, then environment, then library defaults (where defined).
  - Stores resolved values on object/config properties for downstream components.
- `async def __aenter__(self) -> Linear`
- `async def __aexit__(...) -> None`
- Domain factory methods:
  - `linear.issue(...)`
  - `linear.user(...)`
  - `linear.status(...)`
  - `linear.team(...)`
  - `linear.label(...)`
  - `linear.comment(...)`
  - `linear.attachment(...)`
  - `linear.file_upload(...)`
- `linear.gql` namespace (fallback layer):
  - `linear.gql.gql(...)`
  - `linear.gql.query(...)`
  - `linear.gql.mutate(...)`
  - `linear.gql.paginate_connection(...)`

Layer-specific API details are documented in the layer docs:
- Domain abstraction layer (domain object contracts and mutation/collection behavior):
  - [docs/design/domain-layer.md](domain-layer.md)
- GraphQL services layer (`linear.gql.*`) full method signatures and selector rules:
  - [docs/design/gql-layer.md](gql-layer.md)
- Shared cursor-pagination contract for `v1.1.0`:
  - domain `Team.search_issues(...) -> IssueSearchPage`
  - GraphQL `linear.gql.issues.search(...) -> IssueSearchPageModel`

---

## Temporal Usage Constraints

Temporal Workflows must be **deterministic** because they are frequently **replayed** from history. Network calls and other external side effects can change between replays, which can cause Workflow failures or duplicate side effects.

**Therefore:**
- Use this Linear client inside **Temporal Activities** (and other non-Workflow async code).
- In Workflows, call Activities that wrap Linear operations (Workflow → `execute_activity(...)` → Activity uses Linear client).

This is a standard Temporal pattern and is not typically a meaningful limitation; it is how Temporal achieves reliability and replayability.

---

## Authentication Details

### Mode selection

- `auth_mode` is selected via constructor parameter:
  - `client_credentials` → use client-credentials flow.
  - `oauth` → use OAuth authorization-code bootstrap plus refresh flow.
- Default `auth_mode` is `oauth`.
- `auth_mode` is not configured through an environment variable.

### Client-credentials (primary)

**Inputs**
- `client_id` (fallback env: `<PREFIX>LINEAR_CLIENT_ID`)
- `client_secret` (fallback env: `<PREFIX>LINEAR_CLIENT_SECRET`)
- `oauth_scope` (comma-separated scopes; required; fallback env: `<PREFIX>LINEAR_OAUTH_SCOPE`)
  - E.g. `read,write,app:assignable,app:mentionable`
- `oauth_url` (optional token endpoint; fallback env: `<PREFIX>LINEAR_OAUTH_URL`)
  - Default: `https://api.linear.app/oauth/token`
- `oauth_token_path` (optional; fallback env: `<PREFIX>LINEAR_OAUTH_TOKEN_PATH`)
  - Default: `~/.linear_client_oauth.json`
- `oauth_skew_seconds` (optional; fallback env: `<PREFIX>LINEAR_OAUTH_SKEW_SECONDS`)

**Behavior**
- On startup, attempt to load token from `oauth_token_path`.
- If token missing or expired (with skew), request a new token using client-credentials.
- Cache token in memory; persist to JSON file when obtained/renewed.
- If multiple coroutines request a token concurrently:
  - Ensure only one token acquisition occurs (async lock per process).

**Acquisition**
- Use `httpx.AsyncClient` to POST to `oauth_url`.
- Send `application/x-www-form-urlencoded` parameters:
  - `grant_type=client_credentials`
  - `scope=<oauth_scope>`
  - `client_id=<client_id>`
  - `client_secret=<client_secret>`
- Note: Linear also supports HTTP Basic auth for client authentication; this library uses body parameters by default.
- Parse and store `access_token` and expiry (`expires_in` or equivalent mapped to `expires_at`).

### OAuth authorization-code plus refresh (secondary)

**Inputs**
- `client_id` (fallback env: `<PREFIX>LINEAR_CLIENT_ID`)
- `client_secret` (fallback env: `<PREFIX>LINEAR_CLIENT_SECRET`)
- `oauth_url` (fallback env: `<PREFIX>LINEAR_OAUTH_URL`)
- `oauth_token_path` (optional; fallback env: `<PREFIX>LINEAR_OAUTH_TOKEN_PATH`; default `~/.linear_client_oauth.json`)
- Bootstrap-only:
  - `oauth_redirect_uri` (fallback env: `<PREFIX>LINEAR_OAUTH_REDIRECT_URI`)
  - `oauth_code` (fallback env: `<PREFIX>LINEAR_OAUTH_CODE`)
- `oauth_skew_seconds` (optional; fallback env: `<PREFIX>LINEAR_OAUTH_SKEW_SECONDS`)

**Bootstrap rules**
- If a token JSON file exists and matches the required canonical schema, use it
  and ignore `oauth_code`.
- If a token JSON file exists but does not match the required canonical schema,
  fail with actionable guidance instead of inferring a legacy shape.
- If no token JSON exists, require `oauth_code` and exchange it for tokens.
- Persist resulting tokens.

**Refresh**
- Refresh access token when expired (with skew).
- Persist refreshed access token, and persist rotated refresh token if provided.

**Exchange and refresh**
- Use `httpx.AsyncClient` to POST to `oauth_url`:
  - auth-code exchange: `grant_type=authorization_code` with `code` and `redirect_uri`
  - refresh: `grant_type=refresh_token` with `refresh_token`
- Map response into the shared token JSON format.

### Token acquisition concurrency and sharing

- Within a single process: guard refresh/acquisition with an async lock.
- Across processes: recommended configuration is one token file per container. If sharing a path is supported, add a file lock.

---

## Token JSON File Format (shared across auth modes)

`oauth_token_path` (constructor parameter; fallback env: `<PREFIX>LINEAR_OAUTH_TOKEN_PATH`) points to a single JSON file that must support **either** OAuth tokens **or** client-credentials tokens.

This is an intentional `v1.1.0` compatibility cleanup: legacy token-file
parsing is not part of the supported contract for this release.

### Design goals

- One file format that works for both modes.
- Safe to read and write atomically.
- Minimal secret leakage risk (no client secret, no auth code stored).
- One explicit contract for `v1.1.0`, without legacy-shape inference.

### Canonical schema (required in `v1.1.0`)

```json
{
  "version": 1,
  "mode": "oauth",
  "updated_at": "2026-02-27T12:34:56Z",
  "access_token": "lin_...",
  "expires_at": 1760000000,
  "refresh_token": "lin_refresh_..."
}
```

Field definitions:

- `version` (int, required): token file schema version.
- `mode` (string, required): `oauth` or `client_credentials`.
- `updated_at` (string, optional): ISO-8601 timestamp of last write (UTC recommended).
- `access_token` (string, required): bearer token used for Linear GraphQL API calls.
- `expires_at` (int, required): UNIX epoch seconds when `access_token` expires.
- `refresh_token` (string, optional):
  - Required for `mode="oauth"` after bootstrap.
  - Must be absent or null for `mode="client_credentials"` unless Linear explicitly provides one in that mode.

### Client-credentials example

```json
{
  "version": 1,
  "mode": "client_credentials",
  "updated_at": "2026-02-27T12:34:56Z",
  "access_token": "lin_...",
  "expires_at": 1760000000
}
```

### Load and migration rules

- Persisted token files must use the canonical explicit schema above.
- `version` must be present and currently must equal `1`.
- `mode` must be present and must be `oauth` or `client_credentials`.
- `access_token` and `expires_at` must be present.
- For `mode="oauth"`, `refresh_token` is part of the expected persisted
  contract after bootstrap/refresh.
- If the file exists but omits required fields, uses an unsupported `version`,
  or relies on legacy/inferred shape rules, the library must fail loudly with
  actionable guidance to delete, migrate, or re-bootstrap the file.
- Unknown extra fields may be ignored so future schema additions do not require
  immediate parser breakage.

### Persistence rules

- Must write atomically:
  - Write to `oauth_token_path + ".tmp"` and then rename/replace.
- Must set restrictive permissions on the token file using a best-effort policy:
  - On POSIX systems, attempt to set mode `0o600`.
  - On non-POSIX systems, rely on platform-default ACLs.
  - If permission tightening is not possible due to platform/filesystem/runtime constraints, log a warning and continue.
- Must never write:
  - `<PREFIX>LINEAR_CLIENT_SECRET`
  - `<PREFIX>LINEAR_OAUTH_CODE`

---

## Internal Architecture

### Components

1. **Config**
   - `LinearConfig`: resolved constructor-first values (constructor overrides, env fallbacks, library defaults).
   - Must not include Temporal worker configuration.

2. **Auth providers**
   - `AuthProvider` interface:
     - `async def get_access_token(self) -> str`
   - Implementations:
     - `ClientCredentialsAuthProvider`
     - `OAuthAuthProvider` (authorization-code bootstrap plus refresh)

3. **Token store**
   - `TokenStore` interface:
     - `async def load(self) -> TokenData | None`
     - `async def save(self, token: TokenData) -> None`
   - JSON-file implementation at `oauth_token_path`.
   - Must write atomically (write temp file then rename).
   - Must require the canonical explicit token-file schema and reject
     legacy/inferred file shapes with actionable errors.

4. **Domain abstraction layer (`linear_client.domain.*`)**
   - Owns first-class domain objects, repositories, and identity-aware materialization behavior.
   - Detailed domain abstraction layer architecture is defined in [docs/design/domain-layer.md](domain-layer.md).

5. **GraphQL services layer (`linear.gql.*`)**
   - Owns transport-backed GraphQL execution, service-level selector validation, and typed GraphQL models.
   - Detailed GraphQL services layer architecture is defined in [docs/design/gql-layer.md](gql-layer.md).

6. **Facade**
   - `Linear` ties shared components together and exposes both layers:
     - top-level domain factories for the domain abstraction layer
     - `linear.gql` for the GraphQL services layer fallback path
     - `linear.me()` for current-principal lookup as a domain `User`
   - `Linear` owns the per-client domain identity map.

---

## Retry and Error Handling

### Retry policy

- Shared policy: retries are explicit, bounded, and safe by default.
- Mutation retries must remain opt-in.
- Retry/backoff semantics and GraphQL execution details are defined in the GraphQL services layer:
  - [docs/design/gql-layer.md](gql-layer.md)

### Errors

- Shared policy: errors must be typed, actionable, and secret-safe.
- Detailed transport/HTTP/GraphQL error mapping is defined in the GraphQL services layer:
  - [docs/design/gql-layer.md](gql-layer.md)

---

## Logging

- Use standard Python `logging`.
- Preserve secret safety in all layers.
- Layer-specific logging guidance:
  - Domain abstraction layer (fetch/resolution/mutation behavior): [docs/design/domain-layer.md](domain-layer.md)
  - GraphQL services layer (transport, operation names, rate-limit headers): [docs/design/gql-layer.md](gql-layer.md)

---

## Repository Structure (standard library layout)

This repo should be structured so it works well as an installable package **and** can be used by vendoring the package directory.

Recommended layout (using the modern `src/` pattern):

```
linear-client/
  pyproject.toml
  README.md
  LICENSE

  src/
    linear_client/
      __init__.py
      linear.py
      config.py
      transport.py
      errors.py
      token_store.py
      gql/
        __init__.py
        facade.py
        models.py
        services/
          __init__.py
          issues.py
          users.py
          statuses.py
          labels.py
      domain/
        __init__.py
        base.py
        issue.py
        user.py
        status.py
        team.py
        label.py
        comment.py
        attachment.py
        file_upload.py
        issue_link.py
        bridges.py
        repos/
          __init__.py
          base.py
          issue_repo.py
          user_repo.py
          status_repo.py
          team_repo.py
          label_repo.py
          comment_repo.py
          attachment_repo.py
          file_upload_repo.py
      auth/
        base.py
        client_credentials.py
        oauth.py

  tests/
    unit/
      linear_client/
        gql/
          test_linear_facade.py
          test_models.py
          test_issues_service.py
          test_users_service.py
          test_statuses_service.py
          test_labels_service.py
        domain/
          test_issue_user_status_team.py
          test_fetch_resolution.py
          test_identity_map.py
          test_issue_mutations.py
          test_issue_labels.py
          test_team_collections.py
          test_comments_attachments_uploads.py
          test_bridges.py
          test_label.py
        test_config.py
        test_token_store.py
        test_auth_client_credentials.py
        test_auth_oauth.py
        test_transport_retries.py
        test_transport_errors.py
      scripts/
        test_integration_harness.py

  docs/
    design/
      design.md
      domain-layer.md
      gql-layer.md
```

Vendoring option:
- Copy `src/linear_client/` into another repo (for example into `vendor/linear_client/`) and ensure it is on `PYTHONPATH`.
- The code must not depend on repo-relative paths; only package-relative imports.
- Vendored/copy-source consumers must provide the runtime dependencies declared in `pyproject.toml`.

Notes:
- Unit tests should not perform real network calls.
- Use HTTP mocking (for example, `respx` for `httpx`) or `httpx.MockTransport`.
- Use `pytest` plus `pytest-asyncio` for async tests.

---

## Migration and Harness Refactor Policy

The current design intentionally does not preserve backward compatibility for legacy domain/service signatures.

- The manual testing harness (scripts, ad-hoc runners, and examples) must use domain objects (`Issue`, `User`, `Status`, etc.) and instance methods (`create`, `assign`, `transition`, `update`, `add_comment`, etc.).
- Unit tests must validate:
  - lazy-loading behavior and smart getters (including `await user.id`)
  - identity-map behavior (single instance per `(type, id)` within a client)
  - comment and attachment flows via first-class domain objects
- Legacy harness modes/usages that depend on old `*Model` or pre-domain service signatures are removed rather than shimmed.

---

## Unit Test Requirements

At minimum, define unit tests for:

1. **Config and environment resolution**
   - `LINEAR_ENV_PREFIX` application
   - required variable validation
   - constructor-over-environment precedence
   - `auth_mode` validation/default behavior

2. **Token store**
   - OAuth and client-credentials round-trip behavior
   - atomic writes
   - rejection of invalid or legacy token-file shapes with actionable error
     behavior

3. **Auth providers**
   - client-credentials acquisition/refresh behavior
   - OAuth bootstrap/refresh behavior
   - concurrency lock behavior

4. **Dependency sync tool**
   - generated-file behavior and header contracts
   - runtime/dev artifact validity behavior

5. **Integration harness**
   - expected-failure UX and stable exit-code behavior

6. **Layer-specific test matrices**
   - Domain abstraction layer domain-object/repository/identity-map coverage:
     - [docs/design/domain-layer.md](domain-layer.md)
   - GraphQL services layer transport/services/facade coverage:
     - [docs/design/gql-layer.md](gql-layer.md)

---

## Documentation (MkDocs)

### Scope

The documentation system must cover both:

- Package-facing usage and API behavior (install, configuration, examples, reference).
- Design and architecture behavior (cross-layer contract plus layer-specific details).

Published MkDocs source content is isolated under `docs/pub` (configured as `docs_dir`).
Internal engineering specifications (for example `docs/design/*`,
`docs/planning/*`, `docs/execution/*`, and `docs/archive/*`) are
intentionally kept outside published MkDocs source and must not be included in
the public site build by default.

Canonical design content remains in:

- [docs/design/design.md](design.md)
- [docs/design/domain-layer.md](domain-layer.md)
- [docs/design/gql-layer.md](gql-layer.md)

### Documentation architecture

1. **Primary output**
   - Maintain a multi-page static documentation site built with MkDocs.
   - MkDocs configuration must use:
     - `docs_dir: docs/pub`
     - `site_dir: site`
   - Keep section ownership explicit (cross-layer, domain abstraction layer, GraphQL services layer fallback, integration/testing/operations docs).
   - Future goal: publish/deploy that site to the repository GitHub Pages endpoint once the repository is public.

2. **API reference source**
   - API reference should be generated from Python docstrings to avoid drift between code and docs.
   - The generated reference should link back to conceptual docs in the design set.

### Baseline MkDocs stack

- `mkdocs` (site generator)
- `mkdocs-material` (theme)
- `mkdocstrings[python]` (API reference from docstrings)

### Implementation steps

1. Add documentation dependencies to dev tooling.
2. Create `mkdocs.yml` with:
   - site metadata
   - `docs_dir: docs/pub`
   - `site_dir: site`
   - navigation mapped to docs content under `docs/pub`
   - Markdown/theme/plugin configuration
   - explicit exclusion of internal specification docs from public navigation/build inputs
3. Add reference pages for public modules/classes/functions generated from docstrings.
4. Add local commands:
   - `mkdocs serve` for local preview
   - `mkdocs build` for production artifact
5. Documentation CI build automation is optional while repository hosting/publication is deferred.
   - If deferred, track publication/build automation work in [docs/future-work.md](../future-work.md).
6. Add a release/checklist gate to ensure docs build succeeds and API reference generation has no unresolved symbols.

Canonical release gate checklist:

- [docs/release-checklist.md](../release-checklist.md)

### Documentation quality policy

Repo-local documentation and code-documentation policy now lives in
[`docs/policies/coding-guidelines.md`](../policies/coding-guidelines.md).

This design set still defines document ownership:

- Cross-layer behavior belongs in [docs/design/design.md](design.md).
- Layer-specific behavior belongs in the layer docs.

---

## Versioning and Release Workflow

Repository-wide Semantic Versioning and changelog rules live in
[`docs/policies/common/coding-guidelines.md`](../policies/common/coding-guidelines.md#repository-versioning-and-changelog).

`linear-client`-specific release workflow, public API versioning boundary,
plan/archive lifecycle, and next-cycle bootstrap guardrails now live in
[`docs/policies/release-workflow.md`](../policies/release-workflow.md).

### Runtime version metadata

Runtime version metadata policy now lives in
[`docs/policies/release-workflow.md`](../policies/release-workflow.md).

---

## Examples: Temporal Activity Usage

### 1) Instantiate the library inside an Activity

```python
from linear_client import Linear

async def some_activity() -> None:
    async with Linear() as linear:
        me = await linear.me()
        my_user_id = me.peek_id()
        # ...use result...
```

Additional layer-specific examples:
- Domain abstraction layer (domain object workflows): [docs/design/domain-layer.md](domain-layer.md)
- GraphQL services layer (`linear.gql.*`): [docs/design/gql-layer.md](gql-layer.md)

---

## Acceptance Criteria

1. **Async-only**
   - No synchronous HTTP calls in the library.
   - No use of `asyncio.to_thread` for auth or networking.

2. **Dual auth**
   - Works in `client_credentials` mode without any OAuth bootstrap variables.
   - Works in `oauth` mode with initial authorization code and then refresh-only operation.

3. **Env compatibility**
   - All existing env vars listed above are still honored as constructor defaults with `LINEAR_ENV_PREFIX`.

4. **Official domain and fallback APIs**
   - Top-level domain factories (`linear.issue`, `linear.user`, `linear.status`, `linear.team`, `linear.label`, `linear.comment`, `linear.attachment`, `linear.file_upload`) are present and create objects without network I/O.
   - `linear.me()` is always present and returns the authenticated principal as a domain `User`.
   - `Team.list_labels` in domain abstraction layer uses UI-visible semantics (team-owned + global/workspace labels), while strict team-only behavior remains available via `linear.gql.labels.list(..., local_only=True)`.
   - Domain `Label` objects expose hierarchy as object relations (`parent` / `children`) with `get_*`, `peek_*`, and smart-property behavior.
   - `linear.gql.issues` is always present and includes `get`, `search`, `create`, `update`, `next_status`, `assign`, and `link(link_type=...)`.
     - issue-targeted methods support `issue_id` or `issue_key` with mutual-exclusion validation.
   - `linear.gql.users` is always present and includes `list` and `resolve_id`.
   - `linear.gql.statuses` is always present and includes `list` and `resolve_id`.
   - `linear.gql.labels` is always present and includes:
     - `list(..., local_only: bool = True)`
       - `local_only=True` (default): strict team-owned labels only
       - `local_only=False`: UI-visible labels for team issue context (team-owned + global/workspace)
     - `LabelModel` includes hierarchy metadata:
       - `parent_id: str | None`
       - `child_ids: list[str]` derived from list result shape

5. **Operational behavior**
   - Tokens persist to `<PREFIX>LINEAR_OAUTH_TOKEN_PATH` using the specified
     canonical explicit schema.
   - Legacy or inferred token-file shapes are rejected with actionable
     migration guidance rather than compatibility parsing.
   - Mutations are not retried unless explicitly enabled.
   - Logs are useful and do not leak secrets.

6. **Documentation quality**
   - Every file includes clear header documentation.
   - Every public interface is fully documented with complete docstrings.
   - No org-specific behavior is hardcoded; the library remains reusable.

7. **Testing**
   - Unit tests exist under `tests/unit/...` and cover config, token store, auth, transport, and issues helpers.
   - Tests run without external network access and use HTTP mocking.

8. **Integration harness operations**
   - The integration harness supports scenario mode, user-mapping mode (`--list-users`), current-principal mode (`--whoami`), and runtime version mode (`--lib-version`).
   - Scenario mode accepts assignee name input and resolves assignee id internally via `linear.gql.users.resolve_id(...)`.
   - `--whoami` prints the output of `await linear.me()`.
   - `--lib-version` prints runtime library version metadata without network calls.
   - `--list-users` marks with `*` any listed users whose id matches the current principal id from `await linear.me()`.
   - For expected configuration/client failures, the harness prints actionable error messages and exits with stable non-zero codes instead of uncaught tracebacks.

9. **Domain API migration cutoff**
   - No backward-compatibility shim layer exists for legacy domain/service API signatures.
   - Legacy harness/test usage patterns based on pre-domain signatures are removed rather than retained.

10. **Identity-map reconciliation for selector-only construction**
   - Domain factory construction remains no-I/O.
   - Selector-only objects (for example `linear.user(name=...)`) may be provisional until id resolution.
   - Once id resolves, behavior converges to canonical identity-map state for `(type, id)` and avoids divergent duplicate state.

11. **Documentation system readiness**
   - MkDocs-based documentation build is defined and reproducible.
   - MkDocs uses `docs_dir: docs/pub` and `site_dir: site`.
   - Multi-page site remains the canonical documentation output.
   - Internal specification docs are kept outside the published MkDocs source tree by default.
   - GitHub Pages publication remains a deferred future milestone while the repository is private.
   - Public API reference generation from docstrings is part of the documentation build.

---

## Coding Conventions

Repo-local coding, documentation, logging, and defensive-error-handling policy
now lives in [`docs/policies/coding-guidelines.md`](../policies/coding-guidelines.md).

This design set remains the architectural source of truth for cross-layer and
layer-specific behavior, while the policy document defines repository-wide code
quality and documentation-maintenance requirements.
