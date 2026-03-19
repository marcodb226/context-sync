# Future Work

> **Status**: Draft
> **Date**: 2026-03-17

---

## Next release

No items are currently shortlisted for the next planning pass.

## Backlog

All current `FW-*` items remain in `Backlog`. None has been explicitly promoted
to `Next release` yet.

<a id="fw-1-comment-storage-optimizations"></a>
### FW-1 - Comment Storage Optimizations

**Why deferred**
- The first release stores the full Linear comment history for each ticket
  directly in the ticket Markdown file because that is the simplest
  correctness-first and inspectable default.
- Comment-heavy tickets may eventually make refresh cost, file size, or human
  usability worse, but that tradeoff should be revisited only after first-
  release usage data shows it is materially affecting real workflows.

**Scope**
- Refresh comment content incrementally instead of always rewriting the full
  comment section.
- Support a configurable comment cap with an explicit truncation marker.
- Split comments into a separate file when ticket files become too large to
  work with comfortably.
- Add observability around comment volume so the tool can surface when this
  becomes a real operational issue.

**Completion signal**
- The tool has an implemented and documented strategy for bounding or
  restructuring comment-heavy snapshots without losing the intended v1
  correctness guarantees.

<a id="fw-2-attachment-content-handling"></a>
### FW-2 - Attachment Content Handling

**Why deferred**
- The first release stores attachment metadata and URLs in ticket files but
  does not inline or download attachment contents.
- The first release also does not attempt to resolve repo-hosted attachment or
  resource URLs into local filesystem paths, even when the same file may
  already exist in a checked-out project clone. That keeps the sync tool
  read-only, predictable, and simpler to ship.
- The first release narrows incremental refresh correctness so attachment-only
  metadata drift is not guaranteed to be detected during selective refresh.
  That tradeoff is the accepted outcome of
  [M1-D3](implementation-plan.md#m1-d3---refresh-composite-freshness-contract-amendment)
  and keeps the first amendment focused on comment and relation freshness,
  which have higher impact on graph correctness and day-to-day context
  quality.

**Scope**
- Inline text-based attachment content when it is safe and useful.
- Store selected attachment contents as adjacent local files while preserving
  source URLs in frontmatter.
- Expose best-effort local filesystem paths for repo-hosted attachment or
  resource URLs when the corresponding repository is already cloned and
  available locally, while keeping the original URL authoritative.
- Add type-specific handling for images or other rich media.
- Define and implement attachment freshness semantics for incremental refresh
  so attachment-only upstream changes can be detected or intentionally
  reconciled under a documented contract.
- Define size, type, and safety limits so attachment handling does not bloat
  snapshots or introduce surprising network cost.

**Completion signal**
- The snapshot can preserve authoritative source URLs while also exposing the
  selected attachment content or advisory local-path metadata within documented
  size, type, and safety limits, and the incremental-refresh contract explains
  how attachment-only changes are detected or intentionally deferred.

<a id="fw-3-whole-snapshot-atomic-commit"></a>
### FW-3 - Whole-Snapshot Atomic Commit

**Why deferred**
- The first release guarantees atomic file writes but not atomic whole-
  directory snapshot commit, so an interrupted `sync`, `refresh`, `add`, or
  `remove-root` run may leave a mix of files from the previous snapshot and the
  in-progress pass.
- Many expected callers will run the tool over git-managed files, which
  provides a practical recovery path by reverting to the previous committed
  state, but that is not a substitute for stronger tool-level correctness
  because `context-sync` may also be used outside a git repository.

**Scope**
- Write the next snapshot into a staging directory and switch it into place
  only after the full pass succeeds.
- Maintain manifest-level generation or commit markers so readers can
  distinguish a completed snapshot from an interrupted pass.
- Add resumable cleanup logic after interrupted runs.

**Completion signal**
- Mutating runs either publish a complete new snapshot atomically or leave the
  previous snapshot intact, and interrupted runs are distinguishable and
  recoverable from repository artifacts alone.

<a id="fw-4-historical-ticket-alias-import"></a>
### FW-4 - Historical Ticket Alias Import

**Why deferred**
- The first release stores stable ticket UUIDs plus locally observed issue-key
  aliases in the manifest so agents can resolve old and new references
  offline.
- That works well once `context-sync` has seen a rename, but it does not
  reconstruct alias history that predates the tool's tracking of a ticket.

**Scope**
- Backfill historical issue keys for already tracked tickets during `sync` and
  `refresh`.
- Distinguish API-authoritative aliases from locally observed aliases in the
  manifest.
- Expose alias provenance in debug output when a reference resolves through an
  old key.

**Completion signal**
- Tracked tickets can resolve pre-existing historical issue-key aliases
  offline, and the manifest or debug output can explain where a resolved alias
  came from.

<a id="fw-5-ticket-history-and-sectioned-ticket-artifacts"></a>
### FW-5 - Ticket History and Sectioned Ticket Artifacts

**Why deferred**
- The first release stores the ticket description and full comment history in
  the main ticket Markdown file, but it does not yet capture a richer activity
  or history timeline as part of the persisted snapshot.
- If future workflows need ticket history, that data may make ticket files
  materially larger and slower for agents or humans to open, so the persistence
  shape needs deliberate design rather than being folded into the main file by
  default.

**Scope**
- Include a ticket activity or history timeline in the local snapshot.
- Store history in an adjacent file such as `<ticket-key>.history.md` rather
  than in the main ticket file.
- Split other bulky sections such as comments into adjacent files when that
  improves agent ergonomics or open cost.
- Define how refresh and diff treat per-section freshness if different sections
  eventually have different update semantics.

**Completion signal**
- The snapshot can persist richer ticket history with a documented section or
  file layout that keeps the main ticket artifact ergonomic and defines the
  resulting refresh and diff semantics.

<a id="fw-6-transient-ticket-preview-without-persistence"></a>
### FW-6 - Transient Ticket Preview Without Persistence

**Why deferred**
- The first release keeps the persisted interface intentionally small: `sync`,
  `refresh`, `diff`, `add`, and `remove-root` all operate in terms of the
  current context directory and its coherent whole-snapshot semantics.
- There is no separate v1 mode for peeking at a ticket without touching local
  files, even though future human and agent workflows may want a cheap way to
  inspect a ticket, and possibly a small reachable neighborhood, before
  deciding whether to persist anything.

**Scope**
- Expose a transient library helper that fetches a ticket by issue key or URL
  and returns a lightweight preview object.
- Optionally support a bounded non-persisted neighborhood preview for nearby
  linked tickets.
- Define how this preview surface differs clearly from `diff`, which compares
  live Linear state against an existing local snapshot.
- Consider whether a CLI-level preview command would be useful for humans once
  the library behavior is proven.

**Completion signal**
- Callers can inspect a ticket, and optionally a bounded nearby neighborhood,
  without writing to `context_dir`, and that preview behavior is documented as
  distinct from `diff`.

<a id="fw-7-label-based-graph-ticket-filters"></a>
### FW-7 - Label-Based Graph Ticket Filters

**Why deferred**
- The first release persists labels on ticket files, but graph construction is
  driven only by roots, traversal dimensions, and the per-root ticket cap.
- Some workflows will want to keep only tickets with a specific label, or to
  exclude tickets with a specific label, without rebuilding that intent by hand
  after every refresh.
- Because the manifest is the authoritative source for directory-level
  traversal state, label-filter behavior needs deliberate persistence semantics
  rather than an ad hoc one-off refresh flag.

**Scope**
- Support a graph-level label filter that can run in either include
  (whitelist) or exclude (blacklist) mode against the normalized label display
  strings already stored in ticket snapshots.
- Store the active label-filter configuration in `.context-sync.yml` alongside
  the existing traversal configuration so future `refresh` runs continue to
  respect it.
- Apply the filter consistently across `sync`, `refresh`, `add`,
  `remove-root`, and `diff`, including pruning tickets that no longer satisfy
  the configured filter.
- Define how label filters interact with roots and traversal semantics, such as
  whether a filtered-out root is rejected, quarantined, or retained only as a
  traversal anchor.

**Completion signal**
- A context directory can persist an include or exclude label filter in its
  manifest, and subsequent snapshot operations keep only the tickets permitted
  by that stored filter under documented root and pruning rules.

## Historical

No historical items are tracked yet.
