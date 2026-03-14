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

The first release stores attachment metadata and URLs in ticket files but does not inline or download attachment contents. That keeps the sync tool read-only, predictable, and simpler to ship, but it leaves useful attachment content outside the local snapshot.

Potential follow-on improvements:

- inline text-based attachment content when it is safe and useful;
- store selected attachment contents as adjacent local files while preserving source URLs in frontmatter;
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
