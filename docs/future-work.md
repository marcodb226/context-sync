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
