# linear-client: API Reference Summary

> This document summarizes the public API surface of the `linear-client` async Python library, which is the framework's exclusive mechanism for all Linear API calls. It is a framework-internal reference, not user-facing documentation. The canonical source is the library's own MkDocs site; this file exists so agents can resolve API questions without leaving the repository.
>
> Wheel releases: https://github.com/marcodb226/linear-client/releases/tag/v1.0.0

---

## Installation

`linear-client` is a private package hosted on GitHub. It is not published to PyPI.

```bash
# Requires SSH access to the repo
pip install "linear-client @ git+ssh://git@github.com/marcodb226/linear-client.git@v1.0.0"
```

Once installed, install the control plane project itself (which declares `linear-client>=1.0.0` as a dependency):

```bash
pip install -e ".[dev]"
```

---

## Architecture: Two Layers

The library exposes two distinct layers. **Use the domain abstraction layer by default.** Drop to the GraphQL services layer only when a needed operation is not yet exposed by the domain layer.

| Layer | Access path | When to use |
|---|---|---|
| Domain abstraction | `linear.issue(...)`, `team.search_issues(...)`, etc. | All routine workflow operations |
| GraphQL services | `linear.gql.*` | Advanced filtering, schema-level control, or operations not yet in the domain layer |

---

## Authentication

The library supports two auth modes. The framework always uses `client_credentials`.

```python
Linear(auth_mode="client_credentials")
```

With client credentials mode, the library exchanges `client_id` + `client_secret` for a 30-day access token and caches it to `oauth_token_path`. Minimum required env vars (with prefix `PM_` as example):

```
PM_LINEAR_CLIENT_ID
PM_LINEAR_CLIENT_SECRET
PM_LINEAR_OAUTH_SCOPE
```

### Env var prefix

The library resolves a prefix from:
1. Constructor `env_prefix` argument
2. `LINEAR_ENV_PREFIX` env var
3. Empty prefix (fallback)

Setting `LINEAR_ENV_PREFIX=PM_` makes `PM_LINEAR_CLIENT_ID` resolve as the client ID. This is how per-agent namespacing works in the framework (see Section 4.5 of the architecture spec).

### Full configuration keys (with `<PREFIX>`)

| Key | Purpose |
|---|---|
| `<PREFIX>LINEAR_CLIENT_ID` | OAuth app client ID |
| `<PREFIX>LINEAR_CLIENT_SECRET` | OAuth app client secret |
| `<PREFIX>LINEAR_OAUTH_SCOPE` | OAuth scopes to request |
| `<PREFIX>LINEAR_OAUTH_TOKEN_PATH` | Path to cached token file (default: `/work/.acp-cache/linear.tokens.json`) |
| `<PREFIX>LINEAR_OAUTH_URL` | OAuth endpoint (default: Linear's standard URL) |
| `<PREFIX>LINEAR_OAUTH_SKEW_SECONDS` | Clock skew tolerance for token expiry |
| `<PREFIX>LINEAR_API_URL` | GraphQL API endpoint |
| `<PREFIX>LINEAR_LOG_LEVEL` | Library log level |

---

## Entrypoint

```python
from linear_client import Linear

async with Linear() as linear:
    me = await linear.me()
```

`linear.me()` returns the authenticated user object. Use on startup to verify credentials.

---

## Domain Abstraction Layer

### Factories (object constructors)

Factories create local domain objects. No network I/O is performed until an explicit async operation is called.

```python
linear.team(key="ACP")
linear.issue(title="...", team=team, description="...")
linear.issue(key="ACP-42")
linear.user(name="architect-agent")
linear.status(name="In Progress", team=team)
linear.label(name="Bug", team=team)
linear.comment(body="...")
linear.attachment(url="...", title="...")
```

### Read contract

| Method type | Behavior |
|---|---|
| `peek_*()` | Sync, no network I/O. Returns currently-held value or `None`. |
| `get_*()` | Async, fetches if not yet resolved. |
| `await issue.id`, `await issue.status`, etc. | Smart async properties — fetch on demand. |
| `await obj.fetch()` | Explicit refresh from Linear. |

### Mutations

All mutations execute immediately against the Linear API.

```python
issue = await issue.create()
issue = await issue.update(title="New title", description="...")
issue = await issue.assign(user)
issue = await issue.transition(status)
comment = await issue.add_comment("Comment text")
attachment = await issue.add_attachment(url, title)
issue = await issue.set_labels([label_a, label_b])
```

### Team collections

```python
issues = await team.search_issues(status="Todo", limit=20)
statuses = await team.list_statuses()
users = await team.list_users(limit=50)
labels = await team.list_labels(limit=100)
```

`search_issues` returns a list of domain `Issue` objects. Additional filter parameters are documented in the full API reference.

---

## GraphQL Services Layer

Accessed via `linear.gql`. Use as a fallback only.

### Raw helpers

```python
await linear.gql.gql(document, variables=None, operation_name=None)
await linear.gql.query(document, variables=None, operation_name=None)
await linear.gql.mutate(document, variables=None, allow_retry=False)
await linear.gql.paginate_connection(...)
```

### Service namespaces

```python
linear.gql.issues      # IssuesService
linear.gql.users       # UsersService
linear.gql.statuses    # StatusesService
linear.gql.labels      # LabelsService
```

Services return typed models (`IssueModel`, `UserModel`, `StatusModel`, `LabelModel`, `IssueLinkModel`). Use `issues_from_gql()` from `linear_client.domain.bridges` to convert GQL results to domain objects.

---

## Exception Hierarchy

```
LinearError
├── LinearConfigurationError       # invalid inputs, selectors, or config
│   └── LinearUnsupportedGrantTypeError
└── LinearTransportError           # payload shape / protocol errors
    ├── LinearHTTPError            # non-2xx HTTP responses
    ├── LinearGraphQLError         # GraphQL-level errors in response payload
    └── LinearNonRetryableError    # explicitly non-retryable failures
```

### Import path

```python
from linear_client.errors import (
    LinearConfigurationError,
    LinearGraphQLError,
    LinearHTTPError,
    LinearNonRetryableError,
    LinearTransportError,
)
```

### Retry guidance

| Exception | Retry? | Agent loop action |
|---|---|---|
| `LinearConfigurationError` | No | Programming error — alert, halt |
| `LinearHTTPError` | Yes (with backoff) | Retry up to configured ceiling |
| `LinearGraphQLError` | No | Query bug or schema drift — alert |
| `LinearTransportError` | No | Payload shape bug — alert |
| `LinearNonRetryableError` | No | Alert immediately |

---

## Bridging GQL to Domain Objects

```python
from linear_client.domain.bridges import issues_from_gql

gql_results = await linear.gql.issues.search(team_key="ACP", limit=10)
domain_issues = issues_from_gql(gql_results, linear=linear)
```

---

## Quick Reference: Framework-Critical Patterns

### Startup identity check

```python
async with Linear() as linear:
    me = await linear.me()
    # verify me.peek_name() matches expected bot identity
```

### Poll for pickup-eligible tickets

```python
team = linear.team(key=TEAM_KEY)
bot = linear.user(name=BOT_NAME)
issues = await team.search_issues(status="Todo", assignee=bot, limit=10)
```

### Pick up a ticket

```python
in_progress = linear.status(name="In Progress", team=team)
issue = await issue.transition(in_progress)
await issue.add_comment("Picked up. Beginning context reconstruction.")
```

### File a clarification and return ticket to queue

```python
# Create clarification ticket (enters at Triage), link as blocker, return original to Todo
clarification = linear.issue(title="Clarification: ...", team=team, description="...")
clarification = await clarification.create()
# link clarification as blocking dependency of issue (via GQL layer — TBD)
todo = linear.status(name="Todo", team=team)
await issue.transition(todo)
await issue.add_comment("Filed clarification ticket. Returning to queue until resolved.")
```

### Mark ticket under review

```python
in_review = linear.status(name="In Review", team=team)
await issue.transition(in_review)
await issue.add_comment("PR submitted: <link>. Waiting for review.")
```

### Close a ticket

```python
done = linear.status(name="Done", team=team)
await issue.add_comment("Completion summary:\n...")
await issue.transition(done)
```
