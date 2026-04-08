# Multi-Repo Workspace Setup

This guide describes how to set up a local development environment for the
context-sync project using a VSCode multi-root workspace with three peer
repositories.

## Repository layout

All three repositories live as siblings inside a shared parent directory:

```
context-sync-workspace/          # any name you like
├── context-sync/                # main project (writable)
├── agent-policies/              # shared agent policies
└── linear-client/               # integration target (read-only, pinned to tag)
```

The `context-sync` repository is the primary working copy. The other two
provide context that the project depends on:

- **agent-policies** — shared cross-repo policy documents. The context-sync
  repo symlinks to this repo from `docs/policies/common`.
- **linear-client** — the upstream Linear API client at the specific version
  the project integrates against.

## 1. Create the parent directory

```bash
mkdir context-sync-workspace
cd context-sync-workspace
```

## 2. Clone the main project

```bash
git clone git@github.com:marcodb226/context-sync.git
```

This is your normal working copy. No special setup is needed.

## 3. Clone the agent-policies repository

Most contributors need a **read-only** copy of the policies repo, checked out
at the top of `main`. If you are authorized to edit the shared agent policies,
skip ahead to the writable variant below.

### Read-only clone (default)

The order of operations matters: create `.vscode/settings.json` before
removing write permissions, otherwise the locked-down file system will prevent
creating the file later.

```bash
git clone git@github.com:marcodb226/agent-policies.git
cd agent-policies
git remote set-url --push origin DISABLED
mkdir -p .vscode
cat > .vscode/settings.json <<'JSON'
{
  "files.readonlyInclude": {
    "**": true
  },
  "files.readonlyFromPermissions": true
}
JSON
find . \
  -path './.git' -prune -o \
  -path './.vscode' -prune -o \
  -exec chmod a-w {} +
cd ..
```

This gives you three layers of protection:

1. **Git** — pushes are disabled so `git push` cannot send changes upstream.
2. **File system** — write permissions are removed from all repo content
   (`.git/` and `.vscode/` are excluded so Git internals and editor settings
   still work).
3. **VSCode** — the editor UI marks every file as read-only.

### Writable clone (authorized policy editors only)

If you are authorized to edit the shared policies, clone normally instead:

```bash
git clone git@github.com:marcodb226/agent-policies.git
```

No read-only lockdown is needed. You will work on branches and push as usual.

## 4. Clone the linear-client at the integration tag

The project currently integrates against **v1.1.0** of the linear-client.
Clone it as a read-only reference copy pinned to that exact tag:

```bash
git clone git@github.com:marcodb226/linear-client.git
cd linear-client
git checkout --detach v1.1.0
git remote set-url --push origin DISABLED
mkdir -p .vscode
cat > .vscode/settings.json <<'JSON'
{
  "files.readonlyInclude": {
    "**": true
  },
  "files.readonlyFromPermissions": true
}
JSON
# Pre-create .egg-info so pip can build/install from this read-only clone
mkdir -p src/linear_client.egg-info
find . \
  -path './.git' -prune -o \
  -path './.vscode' -prune -o \
  -path './src/linear_client.egg-info' -prune -o \
  -exec chmod a-w {} +
cd ..
```

The detached-HEAD checkout pins the clone to the exact commit tagged `v1.1.0`.
The same three layers of protection (Git, file system, VSCode) apply. The
`src/linear_client.egg-info` directory is kept writable so that `pip install`
(editable or not) can write build metadata there — it is gitignored and does
not affect the pinned source.

## 5. Verify the layout

After all three clones are in place, verify:

```bash
ls -1
# Should show:
#   agent-policies
#   context-sync
#   linear-client
```

Verify the symlink inside context-sync resolves:

```bash
ls context-sync/docs/policies/common/
# Should list the shared policy files
```

If the symlink does not resolve, recreate it:

```bash
cd context-sync/docs/policies
ln -sfn ../../../agent-policies/docs/policies/common common
cd ../../..
```

## 6. Configure the VSCode workspace

The `.vscode/` directory is gitignored, so each contributor creates the
workspace file locally. Create it at
`context-sync/.vscode/context-sync.code-workspace`:

```bash
cd context-sync
mkdir -p .vscode
cat > .vscode/context-sync.code-workspace <<'JSON'
{
  "folders": [
    {
      "name": "context-sync",
      "path": ".."
    },
    {
      "name": "agent-policies",
      "path": "../../agent-policies"
    },
    {
      "name": "linear-client",
      "path": "../../linear-client"
    }
  ],
  "settings": {
    "window.title": "[${profileName}]${separator}${rootName}"
  }
}
JSON
cd ..
```

Then open it:

```bash
code context-sync/.vscode/context-sync.code-workspace
```

Or from inside VSCode: **File > Open Workspace from File**, then navigate to
`context-sync/.vscode/context-sync.code-workspace`.

All paths are relative to the `.vscode/` directory inside the context-sync
repo. Because the three repos are peers in the same parent directory, the
`../../` prefix reaches the parent and then descends into each sibling.

Each read-only repo carries its own `.vscode/settings.json` with the
read-only rules, so VSCode applies those settings per-root automatically
without needing workspace-level overrides.

## Verification checklist

After opening the workspace:

- [ ] The Explorer sidebar shows three workspace roots: **context-sync**,
      **agent-policies**, and **linear-client**.
- [ ] Files in **linear-client** and **agent-policies** (read-only clone)
      show a lock icon or prevent editing.
- [ ] Files in **context-sync** are editable normally.
- [ ] `context-sync/docs/policies/common/` is navigable and contains the
      shared policy files (confirming the symlink works).

## Updating the integration tag

When the project moves to a newer linear-client version, you need to re-clone
or update the pinned copy. To update in place:

```bash
cd linear-client
# restore write permissions temporarily
find . \
  -path './.git' -prune -o \
  -path './.vscode' -prune -o \
  -path './src/linear_client.egg-info' -prune -o \
  -exec chmod u+w {} +
git fetch origin
git checkout --detach v<new-version>
# re-lock (keep .egg-info writable for pip)
find . \
  -path './.git' -prune -o \
  -path './.vscode' -prune -o \
  -path './src/linear_client.egg-info' -prune -o \
  -exec chmod a-w {} +
cd ..
```

Replace `v<new-version>` with the new tag. Update this document to reflect the
new target version when it changes.

## If you need to undo the read-only lockdown

To make a read-only repo writable again (for example, to switch to an
authorized-editor workflow):

```bash
cd <repo>
find . \
  -path './.git' -prune -o \
  -path './.vscode' -prune -o \
  -path './src/*.egg-info' -prune -o \
  -exec chmod u+w {} +
git remote set-url --push origin git@github.com:marcodb226/<repo>.git
git switch main
```

Remove the `files.readonlyInclude` and `files.readonlyFromPermissions` entries
from `.vscode/settings.json` if you no longer want VSCode to enforce read-only
mode.
