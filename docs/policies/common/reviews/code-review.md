# Reference: Code Review Checklist

> Cross-role checklist for reviewing implementation changes. This is guidance and not a framework-enforced policy.

## Requirement Fit

- What problem is this solving? Is the implementation aligned with that problem?
- Does it match requirements, design, and ticket?
- Is the scope appropriate? Is it doing the right amount: not too much unrelated work, not hiding refactors, and not missing necessary pieces?

## Correctness

- What happens in normal flow, edge cases, empty input, invalid input, retries, and partial failure?

## Security and Privacy

- Are permissions, auth checks, input validation, secret handling, and data exposure handled correctly?

## Data Integrity

- Could this create inconsistent state, migration issues, duplicate writes, or broken backward compatibility?

## Concurrency and Distributed Behavior

- What happens under parallel requests, retries, idempotency, async execution, or eventual consistency?

## API and Contract Impact

- Does this change public behavior, schema, payloads, or assumptions for callers?
- In repositories that have already shipped a stable release (`>=1.0.0`), does this change externally observable behavior relative to the previous release?
- If released behavior changed, is `CHANGELOG.md` updated for the upcoming release?
- If no changelog entry was added, is the omission explicitly justified and correct?

## Readability

- Are naming, control flow, function boundaries, and file placement good?
- Are all public interfaces documented?
- Is the code readable? Are there enough comments where logic is non-obvious?

## Design Quality

- Is this the simplest good design?
- Is there a cleaner decomposition?
- Is the code defensive?
- Are we sure none of the defensive checks fail silently?

## Testing

- What important scenario is not tested yet?
- Are there enough unit tests?
- Is each unit test clearly testing one capability?
- Would tests fail under realistic broken conditions, or are any tests effectively trivial pass-through checks?
- Are the unit tests passing cleanly?
- Are all linter checks passing cleanly?

## Operational Readiness

- How will we detect problems after release?
- Are there enough error logs?
- Are there enough info logs?
- Are there enough debug logs?

## Blast Radius

- What can go wrong if this ships today?

## Future Cost

- Are we making the next change easier or harder?

## Reuse

- Is there any duplication in the code?
- Would an extra helper function reduce duplication?

## Conformance Checks

- Does the code conform to all coding guidelines?
