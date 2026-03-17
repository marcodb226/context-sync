# context-sync

Linear Context Sync Tool — a deterministic, offline-friendly utility for
snapshotting Linear ticket neighborhoods so that agent loops and human operators
can work from a stable, inspectable context graph without repeated API calls.

See `docs/problem-statement.md` for the full motivation.

## Prerequisites

- Python 3.13+
- A local clone of the shared policy repository
  ([agent-policies](https://github.com/marcodb226/agent-policies))
- SSH access to the private `linear-client` GitHub repository, or a human
  operator who can install it into the project virtualenv

## Getting started

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

# 5. Human-only step: install the private linear-client dependency
python -m pip install "linear-client @ git+ssh://git@github.com/marcodb226/linear-client.git@v1.0.0"

# 6. Install this project
python -m pip install -e .
```

Before running Linear-dependent commands, create and source a local env file
from the tracked sample:

```bash
cp scripts/.linear_env.sh.sample scripts/.linear_env.sh
$EDITOR scripts/.linear_env.sh
source scripts/.linear_env.sh
```

`scripts/.linear_env.sh` is gitignored on purpose. Create it from
[`scripts/.linear_env.sh.sample`](scripts/.linear_env.sh.sample), then source
it into the same shell session you will use for Linear-dependent commands.
That satisfies the credential/bootstrap side of
[`M1-O1`](docs/planning/implementation-plan.md#m1-o1---live-linear-validation-environment-available);
the remaining prerequisite is having `linear-client` installed in the repo-local
`.venv`.

`linear-client` lives in a private GitHub repo and is not published to PyPI.
Agents should not try to bootstrap that dependency themselves. If the active
project virtualenv does not already contain `linear-client`, ask a human to
install it before running imports, the CLI, or validations that depend on
Linear access. See
[`docs/design/linear-client.md`](docs/design/linear-client.md) for the
repository's dependency-boundary and domain-layer guidance.

## Common policies

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

## Agent sandbox setup

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

## Project layout

| Path | Purpose |
|------|---------|
| `docs/problem-statement.md` | Motivation and scope |
| `docs/adr.md` | Architecture decision records |
| `docs/future-work.md` | Planned future work |
| `docs/design/` | Design documents |
| `docs/planning/` | Planning artifacts (candidates, draft plans) |
| `docs/execution/` | Per-ticket execution logs |
| `docs/policies/` | Policy documents; `common/` is the shared symlink |
| `scripts/` | Local bootstrap helpers and tracked sample env files for ignored local runtime config |
