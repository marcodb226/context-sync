# Future Work

> **Status**: Draft
> **Date**: 2026-03-13

---

## FW-1: Comment Storage Optimizations

The first release stores the full Linear comment history for each ticket directly in the ticket Markdown file. That is the right default for correctness, inspectability, and implementation simplicity, but it may become too expensive for very large threads.

Potential follow-on improvements:

- refresh comment content incrementally instead of always rewriting the full comment section;
- support a configurable comment cap with an explicit truncation marker;
- split comments into a separate file when ticket files become too large to work with comfortably;
- add observability around comment volume so the tool can surface when this becomes a real operational issue.

This item should be revisited after first-release usage data shows whether comment-heavy tickets materially affect refresh cost, file size, or human usability.

## FW-2: Attachment Content Handling

The first release stores attachment metadata and URLs in ticket files but does not inline or download attachment contents. It also does not attempt to resolve repo-hosted attachment or resource URLs into local filesystem paths, even when the same file may already exist in a checked-out project clone. That keeps the sync tool read-only, predictable, and simpler to ship, but it leaves useful attachment content and local path affordances outside the local snapshot.

Potential follow-on improvements:

- inline text-based attachment content when it is safe and useful;
- store selected attachment contents as adjacent local files while preserving source URLs in frontmatter;
- expose best-effort local filesystem paths for repo-hosted attachment or resource URLs when the corresponding repository is already cloned and available locally, while keeping the original URL authoritative;
- add type-specific handling for images or other rich media;
- define size, type, and safety limits so attachment handling does not bloat snapshots or introduce surprising network cost.

This item should be revisited after first-release usage clarifies whether attachment content is a meaningful gap for agent workflows or human debugging.

## FW-3: Whole-Snapshot Atomic Commit

The first release guarantees atomic file writes but not atomic whole-directory snapshot commit. If a `sync`, `refresh`, `add`, or `remove-root` run is interrupted partway through, the directory may contain a mix of files from the previous snapshot and the in-progress pass.

Many expected callers will run the tool over git-managed files, which provides a practical recovery path by reverting to the previous committed state. That mitigation helps, but it is not a substitute for stronger tool-level correctness because `context-sync` may also be used outside a git repository.

Potential follow-on improvements:

- write the next snapshot into a staging directory and switch it into place only after the full pass succeeds;
- maintain manifest-level generation or commit markers so readers can distinguish a completed snapshot from an interrupted pass;
- add resumable cleanup logic after interrupted runs.

This item should be revisited if interrupted runs become a real operational problem or if non-git callers become a meaningful share of tool usage.

## FW-4: Historical Ticket Alias Import

The first release stores stable ticket UUIDs plus locally observed issue-key aliases in the manifest so agents can resolve old and new references offline. That works well once `context-sync` has seen a rename, but it does not reconstruct alias history that predates the tool's tracking of a ticket.

If the Linear API exposes authoritative historical aliases or rename history for tickets, the tool should ingest that data and merge it into the local manifest alias table.

Potential follow-on improvements:

- backfill historical issue keys for already tracked tickets during `sync` and `refresh`;
- distinguish API-authoritative aliases from locally observed aliases in the manifest;
- expose alias provenance in debug output when a reference resolves through an old key.

This item should be revisited if offline resolution of pre-existing ticket references becomes important for agent workflows or for migration from older documentation sets.

## FW-5: Ticket History and Sectioned Ticket Artifacts

The first release stores the ticket description and full comment history in the main ticket Markdown file, but it does not yet capture a richer activity or history timeline as part of the persisted snapshot.

If future workflows need ticket history, that data may make ticket files materially larger and slower for agents or humans to open. A likely follow-on design is to keep one canonical core ticket file and store bulky secondary sections in adjacent files.

Potential follow-on improvements:

- include a ticket activity or history timeline in the local snapshot;
- store history in an adjacent file such as `<ticket-key>.history.md` rather than in the main ticket file;
- split other bulky sections such as comments into adjacent files when that improves agent ergonomics or open cost;
- define how refresh and diff treat per-section freshness if different sections eventually have different update semantics.

This item should be revisited if richer history becomes important for agent workflows or if ticket files become large enough that section-level chunking materially improves usability.

## FW-6: Transient Ticket Preview Without Persistence

The first release keeps the persisted interface intentionally small: `sync`, `refresh`, `diff`, `add`, and `remove-root` all operate in terms of the current context directory and its coherent whole-snapshot semantics. There is no separate v1 mode for peeking at a ticket without touching local files.

Future human and agent workflows may still want a cheap way to inspect a ticket, and possibly a small reachable neighborhood, without persisting anything to `context_dir`.

Potential follow-on improvements:

- expose a transient library helper that fetches a ticket by issue key or URL and returns a lightweight preview object;
- optionally support a bounded non-persisted neighborhood preview for nearby linked tickets;
- define how this preview surface differs clearly from `diff`, which compares live Linear state against an existing local snapshot;
- consider whether a CLI-level preview command would be useful for humans once the library behavior is proven.

This item should be revisited if callers repeatedly need ad hoc ticket inspection before deciding whether to add a root or refresh a snapshot.
