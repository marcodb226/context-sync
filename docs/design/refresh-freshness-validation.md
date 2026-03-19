# Refresh Freshness Validation

> **Status**: Resolved on 2026-03-17 with a negative outcome
> **Governing question**:
> [OQ-1](../adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior)
> **Plan ticket**:
> [M1-D1](../implementation-plan.md#m1-d1---refresh-freshness-validation-spike)
> **Execution record**:
> [docs/execution/M1-D1.md](../execution/M1-D1.md)

## Scope

This spike validates whether issue-level `updated_at` alone is sufficient for
the v1 persisted main-ticket snapshot defined in
[docs/adr.md](../adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior)
and
[docs/design/0-top-level-design.md](0-top-level-design.md#62-refresh-flow).

The v1 snapshot includes persisted ticket metadata, description, comments,
attachments, and relations in the main ticket file. Because comments were the
highest-risk child-backed field called out in
[docs/adr.md](../adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior),
the spike used them as the release-gate discriminator and used direct
issue-field updates as positive controls.

## Probe Method

- Ran the probe in the same credentialed execution session established by
  [M1-O1](../execution/M1-O1.md).
- Used disposable `[Linear-client test harness]` issues in the `ARK` team to
  avoid mutating normal work items.
- First probe sequence:
  direct issue title update, direct issue description update, then comment
  creation on the same disposable issue.
- Follow-up probe sequence:
  new disposable issue, comment creation, wait `2.5s`, comment edit, wait
  `2.5s`.
- Archived the disposable probe issues after the validation run.

## Evidence

| Probe | Previous issue `updated_at` | Current issue `updated_at` | Result |
| --- | --- | --- | --- |
| Direct title update (positive control) | `2026-03-17T22:34:11.671Z` | `2026-03-17T22:34:13.339Z` | Advanced |
| Direct description update (positive control) | `2026-03-17T22:34:13.339Z` | `2026-03-17T22:34:14.772Z` | Advanced |
| Comment create on same issue | `2026-03-17T22:34:14.772Z` | `2026-03-17T22:34:14.772Z` | Did not advance |
| Follow-up comment create after `2.5s` wait | `2026-03-17T23:02:50.371Z` | `2026-03-17T23:02:50.371Z` | Did not advance |
| Follow-up comment edit after additional `2.5s` wait | `2026-03-17T23:02:50.371Z` | `2026-03-17T23:02:50.371Z` | Did not advance |

The follow-up probe rules out a simple stale-read explanation for comments:
even after a longer wait, the parent issue `updatedAt` stayed unchanged across
both comment creation and comment edit.

## Outcome

Issue-level `updated_at` is **not** sufficient for the v1 refresh contract.

The current one-cursor design fails for persisted comments: comment creation
and comment edit change rendered ticket content without changing the parent
issue `updatedAt`. A `refresh` implementation that checks only issue-level
`updated_at` would miss stale ticket files and silently retain outdated
comments.

Direct issue-field updates still advanced `updated_at`, so native issue fields
can remain part of the eventual freshness cursor. The failure is specifically
in the child-backed portions of the v1 ticket snapshot.

## Required Amendment Before Refresh Work

- Do **not** implement `refresh` with issue-level `updated_at` as the only
  per-ticket freshness cursor.
- Amend the batched freshness design so each ticket carries a composite
  freshness signal rather than a single issue timestamp.
- Minimum required addition for v1:
  include a per-ticket comment freshness signal that detects both comment
  creation and comment edits before deciding a ticket is fresh.
- Because attachments and relations are also persisted in the v1 ticket file,
  either validate that their changes advance the parent issue `updatedAt` or
  include freshness signals for them in the same composite cursor before
  [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery)
  begins.
- Until that amendment is captured in the governing design/plan, treat
  [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery)
  as blocked.
- The follow-on governing amendment was later accepted in
  [M1-D3](../implementation-plan.md#m1-d3---refresh-composite-freshness-contract-amendment)
  and is now recorded in
  [docs/design/0-top-level-design.md](0-top-level-design.md#62-refresh-flow)
  and
  [docs/adr.md](../adr.md#52-refresh-incremental-whole-snapshot-update).
