# Problem Statement: Linear Context Sync Tool

> **Status**: Draft
> **Date**: 2026-03-13
> **Context**: Forked from the agent-control-plane repo

---

## Context

The agent control plane needs more than a single claimed ticket to work safely. Useful context often lives in the ticket's surrounding Linear graph: blockers, blocked work, parent and child tickets, related tickets, and ticket references embedded in descriptions or comment threads. Human operators and other automation often need the same picture when they are validating, debugging, or extending agent behavior.

Today that context is assembled live inside the agent loop through repeated Linear API calls. The work is deterministic data retrieval, but it happens inside the same execution surface that consumes model tokens and carries the model's working context.

## What Breaks Today

The current runtime-only approach creates several linked operational problems.

- It is expensive. Every Linear fetch is a tool invocation that consumes tokens for request and response scaffolding even though the task does not benefit from model reasoning.
- It is inconsistent. Related tickets are fetched sequentially, so the assembled neighborhood is not a stable snapshot of one moment in time.
- It is shallow by default. Because deeper exploration means more calls, the system naturally stops close to the root ticket even when second- and third-order relationships matter.
- It is disposable. Restarts, resumes, and ticket handoffs rebuild the same context from scratch and pay the same cost again.
- It is opaque. There is no durable artifact showing what the agent knew when it acted, which makes debugging and human validation harder than they should be.
- It is hard to reuse. Other callers that need the same ticket neighborhood must either invoke the agent loop or recreate the traversal logic themselves.

These issues compound. The system spends tokens on deterministic fetches, still ends up with a partial and time-skewed view, and leaves behind no inspectable record.

## Affected Workflows

- The agent loop needs ticket context at claim time, on restart or resume, before sensitive write operations, and whenever it discovers a new ticket identifier mid-run.
- The agent loop needs to start from an initial root ticket, then expand that pool of root tickets as it discovers additional tickets that should remain in long-lived context.
- Human operators need to inspect what an agent would see, compare local context to current Linear state, and debug incorrect decisions without adding special instrumentation.
- CI and other automation need ticket-neighborhood data for reporting, validation, and offline workflows that should not depend on an interactive agent session.

## What a Good Outcome Must Change

A satisfactory solution should:

- move ticket-context materialization out of the model loop and into a bounded, repeatable process;
- preserve that context as a local artifact that both agents and humans can inspect directly;
- support bounded traversal beyond a single hop so nearby dependency structure is available when the work depends on it;
- allow callers to expand the pool of root tickets over time instead of treating the first requested ticket as the only durable anchor;
- make refresh incremental so restart, resume, and targeted validation do not begin from zero every time;
- provide a lightweight refresh path that updates local context by fetching only what changed since the previous snapshot;
- be reusable outside the control plane rather than being hardwired into one caller;
- remain read-only with respect to Linear.

The exact traversal model, persistence format, interface shape, and refresh semantics are design decisions documented in [adr.md](<adr.md>) and [design.md](<design.md>).

## Boundaries

This work is about reading and materializing Linear context. It is not about modifying Linear tickets, fetching attachment contents, mirroring GitHub state, or designing the agent control plane's git and pull-request workflow. Real-time webhook-driven sync is also outside the initial scope.
