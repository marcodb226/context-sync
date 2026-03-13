# Reference: Design Review Checklist

> Cross-role checklist for reviewing design documents. This is guidance and not a framework-enforced policy.

## Problem and Scope

- What problem is this design solving?
- Is the problem statement clear and specific enough?
- Are the goals and non-goals explicit?
- Is the scope appropriately bounded?

## Requirements Fit

- Does the design actually satisfy the stated functional requirements?
- Does it address the important non-functional requirements (performance, reliability, security, scalability, maintainability, cost)?
- Are there requirements that appear unmet, vague, or contradictory?
- Did the design fabricate any requirement that was not explicitly listed in the ADR?

## Assumptions and Constraints

- What assumptions does the design make?
- Are those assumptions realistic and validated?
- Is the design overfitting to temporary constraints?

## Architecture and Approach

- Is the proposed approach understandable and internally coherent?
- Are the main components, responsibilities, and boundaries clear?
- Are interfaces and contracts well-defined?
- Is the separation of concerns good, or is too much coupled together?

## Alternatives

- Were credible alternatives considered?
- Why was this option chosen over the alternatives?
- Is the rejected-alternatives section honest and complete?
- Does the chosen design optimize the right tradeoffs?

## Complexity

- Is the design simpler than it first appears, or more complex than necessary?
- Where is the complexity concentrated?
- Is any complexity accidental rather than essential?

## Failure Modes and Risk

- What can go wrong?
- How does the system behave under partial failure, bad input, abuse, or dependency outages?
- What are the biggest technical and operational risks?
- Are there mitigations, fallbacks, or rollback plans?

## Data and State

- What data is created, read, updated, deleted, or moved?
- Is ownership of data clear?
- Are consistency, durability, retention, privacy, and audit needs addressed?

## Security and Compliance

- What are the trust boundaries?
- What new attack surface does this introduce?
- Are authentication, authorization, secrets handling, data protection, and logging handled correctly?
- Are there legal, regulatory, or compliance implications?

## Operability

- How will this be monitored, debugged, and supported in production?
- Are metrics, logs, traces, alerts, and dashboards identified?
- Will on-call engineers be able to understand and operate it?
- Are runbooks or operational procedures needed?

## Testing and Validation

- How will we know the design works?
- Is there a clear test strategy across unit, integration, end-to-end, performance, and failure testing?
- Are success criteria measurable?
- Is there a plan to validate assumptions early?

## Maintainability

- Will this be easy to modify six months from now?
- Is the design understandable by engineers beyond the author?
- Does it increase or reduce long-term system health?

## Decision Quality

- Are the key decisions explicitly called out?
- Are the tradeoffs documented, not hidden?
- Is the document clear about what is decided versus still open?
- Are the open questions the right ones?
