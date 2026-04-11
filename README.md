# context-sync

Deterministic, offline-friendly snapshots of Linear ticket neighborhoods.

`context-sync` walks the relation graph around one or more root tickets and
materializes a local directory of Markdown files — one per ticket — so that
agent loops, CI pipelines, and human operators can work from a stable,
inspectable context graph without repeated API calls.

The project can be used in two ways:

- **As a CLI tool** — the `context-sync` command provides four operations
  (`sync`, `refresh`, `remove`, `diff`) for managing a local snapshot
  directory.
- **As a Python library** — the async `ContextSync` class exposes the same
  operations programmatically, for embedding in agent frameworks or automation
  scripts.

See [`docs/problem-statement.md`](docs/problem-statement.md) for the full
motivation.

## Installation

`context-sync` requires Python 3.13+ and depends on
[`linear-client`](https://github.com/marcodb226/linear-client), a private
package not published to PyPI. Both packages are installed from their private
GitHub repositories via SSH.

```bash
pip install "linear-client @ git+ssh://git@github.com/marcodb226/linear-client.git@v1.1.0"
pip install "context-sync @ git+ssh://git@github.com/marcodb226/context-sync.git"
```

This makes the `context-sync` command available wherever `pip` installed it.
Use a virtualenv if you prefer isolation.

### Credential setup

All Linear credentials are read from the environment at runtime. The simplest
option is a personal API key (new in `linear-client` v1.1.0):

```bash
export LINEAR_API_KEY="<your-linear-api-key>"
```

Alternatively, use OAuth client-credentials for machine-actor identity:

```bash
export LINEAR_CLIENT_ID="<your-oauth-client-id>"
export LINEAR_CLIENT_SECRET="<your-oauth-client-secret>"
export LINEAR_OAUTH_SCOPE="read,write,app:assignable,app:mentionable"
```

See [Configuration](#configuration) for the complete variable reference and
optional settings.

### Quick start

```bash
# Create a snapshot rooted at a ticket
context-sync sync TEAM-42

# Later, refresh to pick up upstream changes
context-sync refresh

# Check what changed without modifying files
context-sync diff
```

## CLI usage

### Commands

```bash
# Fully rebuild the snapshot from a root ticket
context-sync sync TEAM-42

# Fully rebuild all tracked roots (no root-membership change)
context-sync sync

# Re-fetch the latest data for all tracked tickets
context-sync refresh

# Remove a root (derived-only tickets are pruned)
context-sync remove TEAM-42

# Non-mutating drift inspection (read-only)
context-sync diff
```

### Use cases

| # | Use case | CLI command | Notes |
|---|----------|-------------|-------|
| 1 | Add the first tracked root | `sync TICKET` | Bootstraps the snapshot; TICKET becomes the initial root. |
| 2 | Add a new root to an existing snapshot | `sync TICKET` | Same command; idempotent if TICKET is already tracked. |
| 3 | Lightweight incremental refresh | `refresh` | Re-fetches only tickets identified as new or modified since the last run. |
| 4 | Full rebuild (nuke and rebuild) | `sync` | Rebuilds all tracked roots unconditionally; no root-membership change. |
| 5 | Remove a root and prune orphaned nodes | `remove TICKET` | Stops tracking TICKET and removes tickets not reachable from any remaining root. |
| 6 | Diff without writing to disk | `diff` | Read-only comparison between local snapshot and Linear. |

### Global options

| Flag | Description |
|------|-------------|
| `-v`, `--version` | Print tool name and version, then exit. |
| `-h`, `--help` | Print help text, then exit. |
| `--log-level LEVEL` | Diagnostic log verbosity to stderr. Choices: `DEBUG`, `INFO`, `WARNING` (default), `ERROR`, `OFF`. |

### Per-command options

| Command | Option | Default | Description |
|---------|--------|---------|-------------|
| `sync` | `--context-dir DIR` | `.` | Path to the context directory. |
| `sync` | `--json` | off | Emit machine-readable JSON instead of text. |
| `sync` | `--max-tickets-per-root N` | manifest value | Per-root ticket cap for traversal. Only persisted when explicitly supplied. |
| `sync` | `--depth-blocks N` | manifest value | Traversal depth for `blocks` edges. Only persisted when explicitly supplied. |
| `sync` | `--depth-is-blocked-by N` | manifest value | Traversal depth for `is_blocked_by` edges. Only persisted when explicitly supplied. |
| `sync` | `--depth-parent N` | manifest value | Traversal depth for `parent` edges. Only persisted when explicitly supplied. |
| `sync` | `--depth-child N` | manifest value | Traversal depth for `child` edges. Only persisted when explicitly supplied. |
| `sync` | `--depth-relates-to N` | manifest value | Traversal depth for `relates_to` edges. Only persisted when explicitly supplied. |
| `sync` | `--depth-ticket-ref N` | manifest value | Traversal depth for `ticket_ref` (URL-discovered) edges. Only persisted when explicitly supplied. |
| `refresh` | `--context-dir DIR` | `.` | Path to the context directory. |
| `refresh` | `--json` | off | Emit machine-readable JSON instead of text. |
| `refresh` | `--missing-root-policy` | `quarantine` | How to handle roots no longer visible: `quarantine` or `remove`. |
| `remove` | `--context-dir DIR` | `.` | Path to the context directory. |
| `remove` | `--json` | off | Emit machine-readable JSON instead of text. |
| `diff` | `--context-dir DIR` | `.` | Path to the context directory. |
| `diff` | `--json` | off | Emit machine-readable JSON instead of text. |

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success. |
| `1` | Operational error (lock contention, workspace mismatch, manifest error, root not found, remote failure). |
| `2` | Usage / argument error. |

### Output modes

- **Text** (default): concise human-readable output on stdout, one line per
  category (created, updated, unchanged, removed, errors).
- **JSON** (`--json`): a single JSON object on stdout, parseable with `jq`. For
  `sync`/`refresh`/`remove` the shape is `SyncResult`; for `diff` it is
  `DiffResult`.

## Configuration

### Environment variables

`context-sync` does not define its own environment variables. All credential
and endpoint configuration is provided by the
[`linear-client`](https://github.com/marcodb226/linear-client) library, which
reads the following variables at runtime. They are documented here for
convenience so that tool users do not need to consult the `linear-client`
documentation separately. This table covers the commonly used variables as of
`linear-client` v1.1.0; see the `linear-client`
[configuration docs](https://github.com/marcodb226/linear-client/blob/v1.1.0/docs/pub/configuration.md)
for the full reference including additional variables for OAuth bootstrap and
file handling.

The library supports three auth modes. Only one set of credentials is needed.

| Variable | Auth mode | Required | Description |
|----------|-----------|----------|-------------|
| `LINEAR_API_KEY` | `api_key` | Yes (for this mode) | Personal Linear API key. Simplest option — no token exchange or refresh. |
| `LINEAR_CLIENT_ID` | `oauth`, `client_credentials` | Yes (for these modes) | Linear OAuth application client ID. |
| `LINEAR_CLIENT_SECRET` | `oauth`, `client_credentials` | Yes (for these modes) | Linear OAuth application client secret. |
| `LINEAR_OAUTH_SCOPE` | `oauth`, `client_credentials` | Yes (for these modes) | Comma-separated OAuth scopes (e.g. `read,write,app:assignable,app:mentionable`). |
| `LINEAR_OAUTH_TOKEN_PATH` | `oauth`, `client_credentials` | No | Path to persisted token JSON file. Default: `~/.linear_client_oauth.json`. |
| `LINEAR_OAUTH_URL` | `oauth`, `client_credentials` | No | OAuth token endpoint URL. Default: `https://api.linear.app/oauth/token`. |
| `LINEAR_OAUTH_SKEW_SECONDS` | `oauth`, `client_credentials` | No | Expiry skew in seconds. Default: `30`. |
| `LINEAR_API_URL` | All | No | Linear GraphQL API endpoint. Default: `https://api.linear.app/graphql`. |
| `LINEAR_LOG_LEVEL` | All | No | Log level for the `linear-client` library. Default: `ERROR`. |

No secrets should appear in source files, logs, or error output.

## Operational guidance

### Logging

Diagnostic logs are written to stderr (never stdout). The `--log-level` flag
controls verbosity for the entire process, including both `context-sync` and the
underlying `linear-client` library:

- **WARNING** (default): only warnings and errors.
- **INFO**: run lifecycle events. For mutating modes (`sync`, `refresh`,
  `remove`): active root count, ticket cap, reachable count,
  created/updated/unchanged/removed/error counts, roots-at-cap count, and
  duration. For `diff`: tracked ticket count, current/stale/missing-locally/
  missing-remotely counts, and duration. All modes log an abort reason if the
  run fails.
- **DEBUG**: per-ticket decisions (fresh, stale, pruned, renamed), lock
  acquisition details, alias resolution traces, plus `linear-client` transport
  details.

Typical operator usage:

```bash
# See what the tool is doing at a high level
context-sync refresh --log-level INFO

# Diagnose why a specific ticket was re-fetched (stderr to file)
context-sync refresh --log-level DEBUG 2>debug.log
```

### Lock handling

Mutating operations (`sync`, `refresh`, `remove`) acquire an
exclusive writer lock (`.context-sync.lock`). If another process holds the
lock:

- **Active lock**: the CLI exits with code 1 and a clear message identifying
  the holding writer (ID, host, PID, mode).
- **Stale lock**: if the holding PID no longer exists on the same host, the
  tool preempts the stale lock and proceeds (logged at WARNING level).
- **Indeterminate lock**: if staleness cannot be determined (different host, no
  PID recorded), the CLI refuses and exits with code 1.

`diff` never acquires or modifies the lock. If a non-stale lock exists, `diff`
refuses to run and explains that running it would compete for rate-limited
Linear API capacity with the active writer.

### Missing-root policy

During `refresh`, roots that are no longer visible in the caller's Linear view
are handled by the `--missing-root-policy` flag:

- **`quarantine`** (default): marks the root as quarantined, rewrites its ticket
  file with a warning preamble, and excludes it from traversal. If the root
  becomes visible again, the next refresh automatically recovers it.
- **`remove`**: deletes the root from the manifest and removes its local file
  immediately.

### Common failures

| Symptom | Cause | Resolution |
|---------|-------|------------|
| `linear-client is not installed` | Missing dependency | Install `linear-client` into the active virtualenv (see [Installation](#installation)). |
| `Failed to initialize Linear client` | Missing or invalid env vars | Set the required environment variables (see [Configuration](#configuration)). |
| `Lock held by active process` | Another `context-sync` invocation is running | Wait for it to finish, or if the process is gone, the next run will preempt the stale lock. |
| `Workspace mismatch` | Root ticket belongs to a different Linear workspace | Verify you are targeting the correct context directory or root ticket. |
| `Root ticket not available` | Ticket is archived, deleted, or not visible | Check the ticket in Linear; use `--missing-root-policy remove` to clean up. |

### Smoke validation

Use this recipe to verify that the installed CLI works against a real Linear
workspace.  Replace `TEAM-42` with any issue key visible to your configured
credentials.

**Happy path** — one successful sync, refresh, diff, and remove cycle:

```bash
# 1. Create a fresh context directory.
mkdir -p /tmp/context-sync-smoke && cd /tmp/context-sync-smoke

# 2. Sync a root ticket (creates ticket files).
context-sync sync TEAM-42
# Expected: text output listing the created ticket key(s), exit code 0.

# 3. Refresh (re-fetches all tracked tickets).
context-sync refresh
# Expected: text output with unchanged/updated counts, exit code 0.

# 4. Diff (compare local snapshot to live state, read-only).
context-sync diff
# Expected: text output with diff entries (likely empty if nothing changed), exit code 0.

# 5. Remove the root and clean up.
context-sync remove TEAM-42
# Expected: text output confirming removal, exit code 0.

# 6. Clean up the smoke directory.
rm -rf /tmp/context-sync-smoke
```

**Failure path** — expected error behavior:

```bash
# Missing credentials: neutralize all auth modes to verify the startup failure.
# linear-client defaults to oauth mode when LINEAR_API_KEY is unset, so all
# three auth paths must be cleared. Also remove any persisted token file so
# the library cannot fall back to a cached token.
unset LINEAR_API_KEY LINEAR_CLIENT_ID LINEAR_CLIENT_SECRET LINEAR_OAUTH_SCOPE
rm -f "${LINEAR_OAUTH_TOKEN_PATH:-$HOME/.linear_client_oauth.json}"
context-sync sync TEAM-42
# Expected: "Failed to initialize Linear client" on stderr, exit code 1.

# Restore credentials for the remaining failure checks.
export LINEAR_API_KEY="<your-key>"

# Invalid ticket: use a key that does not exist.
context-sync sync NONEXISTENT-99999
# Expected: "Issue not found" or "Root ticket not available" on stderr, exit code 1.

# JSON error output: verify structured error payload.
context-sync sync NONEXISTENT-99999 --json
# Expected: JSON object with "error" and "message" fields on stdout, exit code 1.
```

---

## Library usage

For programmatic use, import the async `ContextSync` class directly:

```python
from context_sync import ContextSync

ctx = ContextSync(linear=linear_client, context_dir="./context")
result = await ctx.sync(key="TEAM-42")
```

All four CLI operations (`sync`, `refresh`, `remove`, `diff`) are available as
async methods on `ContextSync`. See the class docstring for parameter details.

---

## Contributing

### Prerequisites

- Python 3.13+
- [ripgrep](https://github.com/BurntSushi/ripgrep) (`rg`) — used by agent
  tooling for fast codebase search
- [cloc](https://github.com/AlDanial/cloc) — used to verify source files stay
  within the coding-guidelines 1,000-code-line limit

  Install both via your system package manager:

  ```bash
  # Debian / Ubuntu / WSL
  sudo apt install ripgrep cloc

  # macOS
  brew install ripgrep cloc
  ```

- SSH access to the private
  [`linear-client`](https://github.com/marcodb226/linear-client),
  [`context-sync`](https://github.com/marcodb226/context-sync), and
  [`agent-policies`](https://github.com/marcodb226/agent-policies) repositories

### Developer setup

The project uses a multi-repo workspace with three peer repositories
(`context-sync`, `agent-policies`, `linear-client`). Follow
[`docs/workspace-setup.md`](docs/workspace-setup.md) to clone all three repos,
set up the common-policies symlink, and configure the VSCode multi-root
workspace.

Once the workspace is in place, create a virtualenv and install:

```bash
cd context-sync
python3 -m venv .venv
source .venv/bin/activate
pip install -e ../linear-client          # v1.1.0, from the workspace clone
pip install -e ".[dev]"
pyright --verifytypes linear_client --ignoreexternal  # verify type info
```

The editable install of `linear-client` gives pyright and Pylance full type
information (`py.typed` marker, 100% type completeness). Agent and IDE source
navigation works through the multi-root VS Code workspace.

For running Linear-dependent commands during development, create and source a
local env file from the tracked sample:

```bash
cp scripts/.linear_env.sh.sample scripts/.linear_env.sh
$EDITOR scripts/.linear_env.sh
source scripts/.linear_env.sh
```

[`scripts/.linear_env.sh.sample`](scripts/.linear_env.sh.sample) documents all
available environment variables with comments. The local copy is gitignored.

### Common policies

This project uses a **shared common-policy layer** managed in the
[agent-policies](https://github.com/marcodb226/agent-policies) repository.
The shared policies are expected at `docs/policies/common`, which is a local
symlink (gitignored, never committed) pointing to the sibling policy checkout.

Agent instructions, coding guidelines, execution models, and review checklists
all live in that shared layer. Without it, agents will refuse to proceed and
most tooling will not work correctly.

If the symlink is missing or broken, re-create it:

```bash
ln -s ../../../agent-policies/docs/policies/common docs/policies/common
```

For the full rationale behind the symlink approach, recommended workspace
layout, one-checkout-per-client-repo best practice, and alternatives considered,
see [`docs/policies/common/README.md`](docs/policies/common/README.md).

### Agent sandbox setup

Because `docs/policies/common` is a symlink whose target lives outside this
repository, Claude Code needs explicit write access to the resolved path.
Add the following to `.claude/settings.json`, replacing `<workspace-root>`
with the absolute path to the parent directory that contains all three repos
(for example, `~/src/context-sync-workspace`):

```json
{
  "sandbox": {
    "filesystem": {
      "allowWrite": [
        "<workspace-root>/agent-policies/docs/policies/common"
      ]
    }
  }
}
```

Read access is allowed by default across the filesystem; only write access
needs to be explicitly granted for paths outside the project.

### Developer commands

The repository uses [Ruff](https://docs.astral.sh/ruff/) for linting and
formatting, [Pyright](https://github.com/microsoft/pyright) for static type
checking, [pytest](https://docs.pytest.org/) with
[pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) for testing, and
[coverage.py](https://coverage.readthedocs.io/) with
[pytest-cov](https://pytest-cov.readthedocs.io/) for branch coverage reporting.
Install dev dependencies with `pip install -e ".[dev]"`.

The canonical "validate everything" command is `scripts/validate.sh`. It runs
all quality gates in sequence and exits non-zero on any failure:

```bash
scripts/validate.sh
```

Individual commands are available when working on a specific gate. Make sure the
project virtualenv is active before running these commands:

```bash
# Lint (check only)
ruff check src/ tests/

# Format (check only)
ruff format --check src/ tests/

# Format (apply)
ruff format src/ tests/

# Static type check
pyright

# Run all tests
pytest

# Run tests with verbose output
pytest -v
```

All quality gates (lint, format check, type check, test) must pass before a
ticket can be marked complete.

### Project layout

| Path | Purpose |
|------|---------|
| `src/context_sync/` | Package source |
| `tests/` | Test suite |
| `pyproject.toml` | Package metadata, dependencies, and tool configuration |
| `docs/problem-statement.md` | Motivation and scope |
| `docs/adr.md` | Architecture decision records |
| `docs/future-work.md` | Planned future work |
| `docs/design/` | Design documents |
| `docs/planning/` | Planning artifacts (candidates, draft plans) |
| `docs/execution/` | Per-ticket execution logs |
| `docs/policies/` | Policy documents; `common/` is the shared symlink |
| `scripts/` | Local bootstrap helpers and tracked sample env files for ignored local runtime config |
