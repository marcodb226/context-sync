# context-sync

Deterministic, offline-friendly snapshots of Linear ticket neighborhoods.

`context-sync` walks the relation graph around one or more root tickets and
materializes a local directory of Markdown files — one per ticket — so that
agent loops, CI pipelines, and human operators can work from a stable,
inspectable context graph without repeated API calls.

The project can be used in two ways:

- **As a CLI tool** — the `context-sync` command provides five operations
  (`sync`, `refresh`, `add`, `remove-root`, `diff`) for managing a local
  snapshot directory.
- **As a Python library** — the async `ContextSync` class exposes the same
  operations programmatically, for embedding in agent frameworks or automation
  scripts.

See [`docs/problem-statement.md`](docs/problem-statement.md) for the full
motivation.

> **Pre-release notice:** This project is at version `0.1.0.dev0`. The library
> and CLI interfaces are implemented and tested against a fake gateway, but the
> real `linear-client`-backed gateway adapter is not yet wired. Until that
> adapter lands, the installed CLI and the `ContextSync(linear=...)` constructor
> path will raise an error at runtime. The `_gateway_override` testing hook is
> the only functional entry point today.

## Installation

`context-sync` requires Python 3.13+ and depends on
[`linear-client`](https://github.com/marcodb226/linear-client), a private
package not published to PyPI. Both packages are installed from their private
GitHub repositories via SSH.

```bash
pip install "linear-client @ git+ssh://git@github.com/marcodb226/linear-client.git@v1.0.0"
pip install "context-sync @ git+ssh://git@github.com/marcodb226/context-sync.git"
```

This makes the `context-sync` command available wherever `pip` installed it.
Use a virtualenv if you prefer isolation.

### Credential setup

All Linear credentials are read from the environment at runtime. Set the
required variables before running any command:

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
# Full-snapshot sync from a root ticket
context-sync sync TEAM-42

# Incremental refresh of all tracked roots
context-sync refresh

# Add a second root to an existing snapshot
context-sync add TEAM-99

# Remove a root (derived-only tickets are pruned)
context-sync remove-root TEAM-42

# Non-mutating drift inspection (read-only)
context-sync diff
```

### When to use each command

| Command | Use when you want to... | What it does |
|---------|------------------------|--------------|
| `sync TICKET` | Start tracking a ticket, or add another root to an existing snapshot | Adds the ticket as a root, persists any traversal overrides you supply (`--max-tickets-per-root`, `--depth-*`), then rebuilds the snapshot from **all** active roots. On an empty context directory this bootstraps the snapshot; on an existing one it expands the root set and reconciles. |
| `refresh` | Update the snapshot without changing which tickets are tracked | Re-fetches all tracked roots using the manifest's existing traversal configuration. Only re-fetches tickets whose upstream state has changed (incremental). Does not add or remove roots. |
| `add TICKET` | Add another root without changing traversal configuration | Adds the ticket as a root using the manifest's existing traversal settings (no per-call overrides), then refreshes the snapshot. **Note:** `sync TICKET` achieves the same visible result; `add` exists as a convenience when you want to preserve existing traversal configuration exactly. A future release may unify these commands. |
| `remove-root TICKET` | Stop tracking a root ticket | Removes the ticket from the root set and prunes any derived tickets that are no longer reachable from the remaining roots. This is a destructive operation on the tracked set. |
| `diff` | Inspect drift without modifying files | Compares the local snapshot against live Linear state. Read-only — never acquires a writer lock. If a mutating operation currently holds the lock, `diff` refuses to run rather than competing for rate-limited API capacity. |

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
| `sync` | `--max-tickets-per-root N` | 200 | Per-root ticket cap for traversal. |
| `sync` | `--depth-blocks N` | 3 | Traversal depth for `blocks` edges. |
| `sync` | `--depth-is-blocked-by N` | 2 | Traversal depth for `is_blocked_by` edges. |
| `sync` | `--depth-parent N` | 2 | Traversal depth for `parent` edges. |
| `sync` | `--depth-child N` | 2 | Traversal depth for `child` edges. |
| `sync` | `--depth-relates-to N` | 1 | Traversal depth for `relates_to` edges. |
| `sync` | `--depth-ticket-ref N` | 1 | Traversal depth for `ticket_ref` (URL-discovered) edges. |
| `refresh` | `--context-dir DIR` | `.` | Path to the context directory. |
| `refresh` | `--json` | off | Emit machine-readable JSON instead of text. |
| `refresh` | `--missing-root-policy` | `quarantine` | How to handle roots no longer visible: `quarantine` or `remove`. |
| `add` | `--context-dir DIR` | `.` | Path to the context directory. |
| `add` | `--json` | off | Emit machine-readable JSON instead of text. |
| `remove-root` | `--context-dir DIR` | `.` | Path to the context directory. |
| `remove-root` | `--json` | off | Emit machine-readable JSON instead of text. |
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
  `sync`/`refresh`/`add`/`remove-root` the shape is `SyncResult`; for `diff`
  it is `DiffResult`.

## Configuration

### Environment variables

`context-sync` does not define its own environment variables. All credential
and endpoint configuration is provided by the
[`linear-client`](https://github.com/marcodb226/linear-client) library, which
reads the following variables at runtime. They are documented here for
convenience so that tool users do not need to consult the `linear-client`
documentation separately. This list is complete as of `linear-client` v1.0.0;
newer releases may introduce additional variables.

| Variable | Required | Description |
|----------|----------|-------------|
| `LINEAR_CLIENT_ID` | Yes | Linear OAuth application client ID. |
| `LINEAR_CLIENT_SECRET` | Yes | Linear OAuth application client secret. |
| `LINEAR_OAUTH_SCOPE` | Yes | Comma-separated OAuth scopes (e.g. `read,write,app:assignable,app:mentionable`). |
| `LINEAR_OAUTH_TOKEN_PATH` | No | Path to persisted token JSON file. Default: `~/.linear_client_oauth.json`. |
| `LINEAR_OAUTH_URL` | No | OAuth token endpoint URL. Default: `https://api.linear.app/oauth/token`. |
| `LINEAR_OAUTH_SKEW_SECONDS` | No | Expiry skew in seconds. Default: `30`. |
| `LINEAR_API_URL` | No | Linear GraphQL API endpoint. Default: `https://api.linear.app/graphql`. |
| `LINEAR_LOG_LEVEL` | No | Log level for the `linear-client` library. Default: `ERROR`. |

No secrets should appear in source files, logs, or error output.

## Operational guidance

### Logging

Diagnostic logs are written to stderr (never stdout). The `--log-level` flag
controls verbosity for the entire process, including both `context-sync` and the
underlying `linear-client` library:

- **WARNING** (default): only warnings and errors.
- **INFO**: run lifecycle events. For mutating modes (`sync`, `refresh`, `add`,
  `remove-root`): active root count, ticket cap, reachable count,
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

Mutating operations (`sync`, `refresh`, `add`, `remove-root`) acquire an
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

---

## Library usage

For programmatic use, import the async `ContextSync` class directly:

```python
from context_sync import ContextSync

ctx = ContextSync(linear=linear_client, context_dir="./context")
result = await ctx.sync(key="TEAM-42")
```

All five CLI operations (`sync`, `refresh`, `add`, `remove_root`, `diff`) are
available as async methods on `ContextSync`. See the class docstring for
parameter details.

---

## Contributing

### Prerequisites

- Python 3.13+
- SSH access to the private
  [`linear-client`](https://github.com/marcodb226/linear-client),
  [`context-sync`](https://github.com/marcodb226/context-sync), and
  [`agent-policies`](https://github.com/marcodb226/agent-policies) repositories

### Developer setup

```bash
# 1. Clone this repository
git clone git@github.com:marcodb226/context-sync.git
cd context-sync

# 2. Clone the shared policy repository next to this one,
#    using a checkout dedicated to this client repo
git clone git@github.com:marcodb226/agent-policies.git ../agent-policies-context-sync

# 3. Create the common-policies symlink
ln -s ../../../agent-policies-context-sync/docs/policies/common docs/policies/common

# 4. Create and activate a virtualenv
python3 -m venv .venv
source .venv/bin/activate

# 5. Install the private linear-client dependency
pip install "linear-client @ git+ssh://git@github.com/marcodb226/linear-client.git@v1.0.0"

# 6. Install this project with dev dependencies
pip install -e ".[dev]"
```

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
ln -s ../../../agent-policies-context-sync/docs/policies/common docs/policies/common
```

For the full rationale behind the symlink approach, recommended workspace
layout, one-checkout-per-client-repo best practice, and alternatives considered,
see [`docs/policies/common/README.md`](docs/policies/common/README.md).

### Agent sandbox setup

Because `docs/policies/common` is a symlink whose target lives outside this
repository, Claude Code needs explicit write access to the resolved path.
Add the following to `.claude/settings.json`:

```json
{
  "sandbox": {
    "filesystem": {
      "allowWrite": [
        "~/src/agent-policies-context-sync/docs/policies/common"
      ]
    }
  }
}
```

Read access is allowed by default across the filesystem; only write access
needs to be explicitly granted for paths outside the project.

### Developer commands

The repository uses [Ruff](https://docs.astral.sh/ruff/) for linting and
formatting, [pytest](https://docs.pytest.org/) with
[pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) for testing, and
[cloc](https://github.com/AlDanial/cloc) for measuring source file size against
the coding-guidelines limit (1,000 code lines per file). Install dev
dependencies with `pip install -e ".[dev]"`, and install `cloc` via your system
package manager:

```bash
# Debian / Ubuntu / WSL
sudo apt install cloc

# macOS
brew install cloc
```

Make sure the project virtualenv is active before running these commands:

```bash
# Lint (check only)
ruff check src/ tests/

# Format (check only)
ruff format --check src/ tests/

# Format (apply)
ruff format src/ tests/

# Run all tests
pytest

# Run tests with verbose output
pytest -v
```

All three commands (lint, format check, test) must pass before a ticket can be
marked complete.

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
