# Review: [M1-D3](../implementation-plan.md#m1-d3---refresh-composite-freshness-contract-amendment)

> **Status**: Phase B complete
> **Plan ticket**:
> [M1-D3](../implementation-plan.md#m1-d3---refresh-composite-freshness-contract-amendment)
> **Execution record**:
> [docs/execution/M1-D3.md](M1-D3.md)
> **Reviewer references**:
> [docs/policies/common/execution-model.md](../policies/common/execution-model.md),
> [docs/policies/common/reviews/design-review.md](../policies/common/reviews/design-review.md),
> [docs/implementation-plan.md](../implementation-plan.md),
> [docs/adr.md](../adr.md#52-refresh-incremental-whole-snapshot-update),
> [docs/adr.md](../adr.md#oq-1-refresh-freshness-validation-against-live-linear-behavior),
> [docs/design/0-top-level-design.md](../design/0-top-level-design.md#62-refresh-flow),
> [docs/design/refresh-freshness-validation.md](../design/refresh-freshness-validation.md),
> [docs/future-work.md](../future-work.md#fw-2-attachment-content-handling)

## Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M1-D3-R1 | Low | Todo | Refresh Contract | The amended refresh contract makes `refresh_cursor` mandatory for correctness, but it never states what `refresh` should do when a tracked local file exists with a missing or partial `refresh_cursor`. The governing flow only defines the stale case for "no local file" or for exact component mismatches, leaving malformed or pre-cursor ticket files unspecified. | [docs/adr.md:173](../adr.md), [docs/adr.md:179](../adr.md), [docs/adr.md:373](../adr.md), [docs/design/0-top-level-design.md:385](../design/0-top-level-design.md), [docs/design/0-top-level-design.md:387](../design/0-top-level-design.md), [docs/design/0-top-level-design.md:438](../design/0-top-level-design.md) | Later implementation work for [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery) can legitimately diverge here: one implementation might treat a missing cursor as stale, another might hard-fail, and another might accidentally skip refresh on a file that no longer has enough metadata to prove freshness. That leaves the file-format migration and corrupted-file behavior undefined in the accepted design contract. | Amend the ADR/top-level design so the contract explicitly says that a tracked file with a missing, partial, or otherwise invalid `refresh_cursor` is not fresh. Either require a forced re-fetch in that case or require an explicit format/validation error that triggers re-sync, and tie that rule to the existing `format_version` language. |

## Reviewer Notes

- The main design objective is otherwise met. The ADR and the top-level design
  now agree that first-release `refresh` uses a three-part composite cursor,
  that comment freshness must detect creation/edit activity, that relation
  freshness remains in v1 scope, and that attachment-only drift is explicitly
  deferred to
  [FW-2](../future-work.md#fw-2-attachment-content-handling). Supporting
  evidence:
  [docs/adr.md:376](../adr.md),
  [docs/adr.md:394](../adr.md),
  [docs/design/0-top-level-design.md:417](../design/0-top-level-design.md),
  [docs/design/0-top-level-design.md:445](../design/0-top-level-design.md),
  [docs/execution/M1-D3.md:142](M1-D3.md).
- The ticket handled the previously open ADR-scope question correctly. The
  execution record explicitly says the ADR refresh-strategy prose was rewritten
  rather than leaving the stale single-cursor language in place, and the ADR
  now reflects that accepted decision. Evidence:
  [docs/execution/M1-D3.md:151](M1-D3.md),
  [docs/adr.md:384](../adr.md).
- The relation-freshness choice is appropriately conservative. The ticket makes
  clear that no additional live relation probe was run and therefore does not
  rely on relation changes advancing the parent issue timestamp. Evidence:
  [docs/execution/M1-D3.md:62](M1-D3.md),
  [docs/design/0-top-level-design.md:445](../design/0-top-level-design.md).

## Residual Risks and Testing Gaps

- The accepted `comments_signature` contract still depends on the upstream
  comment/thread metadata behaving as assumed, especially that the chosen
  metadata fields are sufficient to reflect rendered comment changes cheaply.
  [M1-D2](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary)
  now owns auditing the availability/cost side of that path, but later work
  should keep the remaining correctness assumption visible until
  [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery)
  implements it. Supporting context:
  [docs/design/refresh-freshness-validation.md:74](../design/refresh-freshness-validation.md),
  [docs/execution/M1-D3.md:53](M1-D3.md),
  [docs/implementation-plan.md:236](../implementation-plan.md).
- This was a docs-only design ticket, so no repository-wide lint, format, or
  test commands were rerun during review. The review relied on cross-document
  consistency checks against the active plan, ADR, top-level design, and the
  recorded [M1-D1](../implementation-plan.md#m1-d1---refresh-freshness-validation-spike)
  evidence.

---

## Supplementary Independent Review

> **Reviewer session**: independent second-pass Phase B review
> **Date**: 2026-03-19
> **Review scope**: strictest unbiased re-review of all
> [M1-D3](../implementation-plan.md#m1-d3---refresh-composite-freshness-contract-amendment)
> deliverables, covering the ADR amendments, top-level design amendments,
> freshness-validation forward pointer, future-work traceability link,
> implementation-plan
> [M1-D2](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary)
> note, and the execution record itself

### Findings

| ID | Severity | Status | Area | Finding | Evidence | Impact | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M1-D3-R2 | Medium | Todo | Refresh Contract | The `comments_signature` contract relies on each comment's own `updated_at` advancing when the comment body is edited, but the [M1-D1](../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) spike only validated *issue-level* timestamp behavior. The design applies the conservative "don't assume unverified upstream behavior" principle for relations (giving them an independent cursor component) but does not apply the same conservatism to comment-level `updated_at`. [M1-D3](../implementation-plan.md#m1-d3---refresh-composite-freshness-contract-amendment) exists precisely because timestamp assumptions about Linear proved unreliable, yet the replacement contract introduces a new timestamp dependency without empirical validation or an explicit documented assumption. | [docs/design/refresh-freshness-validation.md:46](../design/refresh-freshness-validation.md) (spike tested only issue-level timestamps), [docs/adr.md:398](../adr.md) (`comments_signature` includes comment `updated_at`), [docs/design/0-top-level-design.md:425](../design/0-top-level-design.md) (same), [docs/execution/M1-D3.md:62](M1-D3.md) (relation conservatism applied but no analogous treatment for comments) | If comment-level `updated_at` does not reliably advance on comment body edits in Linear, the `comments_signature` would remain unchanged after an edit and `refresh` would incorrectly treat the ticket as fresh — exactly the failure class that [M1-D1](../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) proved for issue-level timestamps. The risk profile is lower than the issue-level case (same-entity timestamp advancement is standard behavior), but the asymmetry with the relation-freshness conservatism is unacknowledged. | Either: (a) add an explicit validation obligation to [M1-D2](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) requiring it to confirm that comment-level `updated_at` advances on comment edits, analogous to the [M1-D1](../implementation-plan.md#m1-d1---refresh-freshness-validation-spike) probe for issue-level timestamps; or (b) document this as a known unvalidated assumption in the ADR/design and define a fallback (e.g., including comment body digest) if it fails; or (c) include the comment body or a body digest in the canonical input so the signature is self-sufficient regardless of timestamp behavior. |
| M1-D3-R3 | Low | Todo | Refresh Contract | The design mandates "deterministic digest" for `comments_signature` and `relations_signature` but does not specify: (a) the hash algorithm, (b) the output encoding, (c) the canonical ordering of comments in the digest input, or (d) the semantics of the `v1:` prefix visible in the YAML frontmatter example. The `relations_signature` at least specifies ordering by stable target UUID, but `comments_signature` has no equivalent ordering rule for its inputs. | [docs/adr.md:144](../adr.md) (YAML example showing `v1:8f4c...` prefix), [docs/adr.md:398](../adr.md) (comment signature spec without ordering), [docs/adr.md:407](../adr.md) (relation signature with ordering), [docs/design/0-top-level-design.md:422](../design/0-top-level-design.md) (same gap) | Two independent implementations could produce different digest values from identical input, breaking exact-equality comparison across tool versions or reimplementations. The undocumented `v1:` prefix also implies the digest format is versioned, but that versioning contract is never specified, leaving the interaction with `format_version` undefined. | Specify at minimum: a canonical comment ordering rule (e.g., lexicographic by stable comment ID), the digest algorithm, output encoding, and whether the `v1:` prefix is normative or illustrative. These can be brief additions to the existing canonical-input paragraphs. |
| M1-D3-R4 | Low | Todo | Refresh Contract | The sync flow in the top-level design says "Rewrite the ticket file regardless of local freshness" but never explicitly states that `sync` writes the `refresh_cursor` mapping to each ticket file. A subsequent `refresh` depends on those values being present, and the only evidence that `sync` writes them is the shared frontmatter example in the ADR persistence-format section. This is functionally related to existing finding [M1-D3-R1](#m1-d3-r1). | [docs/design/0-top-level-design.md:306](../design/0-top-level-design.md) (sync flow — no mention of `refresh_cursor` writes), [docs/design/0-top-level-design.md:383](../design/0-top-level-design.md) (refresh flow reads `refresh_cursor`), [docs/adr.md:130](../adr.md) (frontmatter example includes `refresh_cursor`) | An implementation that omits `refresh_cursor` from `sync` output would leave every ticket file unpopulated for a subsequent `refresh`, causing unnecessary full re-fetches on the first `refresh` after every `sync`. The contract relies on inference from the shared schema rather than an explicit sync-flow requirement. | Add an explicit note to the sync flow or the persistence format that any mutating flow writing a ticket file must also persist the current `refresh_cursor` so the next `refresh` has a valid baseline. |
| M1-D3-R5 | Low | Todo | Refresh Contract | The `comments_signature` canonical input includes "per-thread `resolved` flag," but `resolved` is a thread-level attribute, not a comment-level one. The design does not specify how this thread-level value maps into the per-comment canonical input sequence: whether every comment in a resolved thread carries the flag, only the root comment does, or the flag is a separate entry in the digest sequence. | [docs/adr.md:401](../adr.md) (canonical input lists resolved alongside per-comment fields), [docs/design/0-top-level-design.md:425](../design/0-top-level-design.md) (same) | Different mappings produce different digests. An implementer must invent a mapping convention that was intended to be part of the design contract. The risk is low because any consistent choice produces correct freshness detection, but the ambiguity adds unnecessary implementation friction for a contract meant to be definitive. | Clarify whether `resolved` is associated with the root comment of each thread in the canonical input, is replicated to every comment in that thread, or is a separate thread-level entry outside the per-comment sequence. |

### Reviewer Notes

- The first review's finding [M1-D3-R1](#m1-d3-r1) remains valid and is
  reinforced by [M1-D3-R4](#m1-d3-r4) above. Together they describe both sides
  of the same gap: the sync flow does not explicitly say it writes cursors, and
  the refresh flow does not explicitly say what to do when cursors are absent.
- The most material new finding is [M1-D3-R2](#m1-d3-r2). The design applies
  an explicit conservatism principle to relations ("no additional live relation
  probes were run... the design makes that explicit and resolves the uncertainty
  by requiring independent relation freshness") but does not apply the same
  principle to comment timestamps. The asymmetry is not arbitrary — same-entity
  timestamp advancement (comment `updated_at` on comment edit) is far more
  standard than cross-entity propagation (issue `updated_at` on comment edit) —
  but the design should acknowledge the assumption and assign its validation
  somewhere, ideally to
  [M1-D2](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary).
- The digest specification gaps ([M1-D3-R3](#m1-d3-r3), [M1-D3-R5](#m1-d3-r5))
  are individually Low but collectively mean the comment signature is less
  implementable from the design artifacts alone than the relation signature.
  This is a solvable gap that does not block the design outcome.
- Aside from these findings, the amendment is well-executed. The ADR and
  top-level design are now consistent, the attachment narrowing is clean and
  properly traced to
  [FW-2](../future-work.md#fw-2-attachment-content-handling), the
  relation-freshness conservatism is the right call given the unvalidated
  upstream behavior, and the
  [M1-D2](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary)
  remote-data requirements are concrete enough for the adapter audit to proceed.

### Residual Risks and Testing Gaps

- The `comments_signature` correctness contract has one unvalidated assumption
  at its core: that comment-level `updated_at` reliably reflects comment edits.
  Until
  [M1-D2](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary)
  or a dedicated follow-up probe confirms this, the edit-detection half of the
  comment freshness promise is provisional. Comment *creation* detection is
  sound because a new comment ID changes the visible set and therefore the
  digest. Supporting context:
  [docs/design/refresh-freshness-validation.md:46](../design/refresh-freshness-validation.md),
  [docs/execution/M1-D3.md:53](M1-D3.md).
- The digest specification is incomplete enough that the first implementation
  will need to make algorithm, encoding, ordering, and prefix-versioning
  choices not recorded in the design. Those choices will become the de facto
  contract once committed, which may or may not match the designer's intent.
  This risk is small but worth noting as a source of potential
  design/implementation drift.
- This was a docs-only design ticket, so no repository-wide lint, format, or
  test commands were rerun during this supplementary review. Validation
  consisted of cross-document consistency checks across the governing plan,
  ADR, top-level design, freshness-validation artifact, execution record, git
  diff of the M1-D3 commits, and the prior Phase B review.

## Ticket Owner Response

| ID | Verdict | Rationale |
| --- | --- | --- |
| M1-D3-R1 | Fix now | This is a real contract gap inside the accepted refresh design itself. Once `refresh_cursor` becomes mandatory for freshness checks, the governing artifacts should say what happens when a tracked file has a missing, partial, or invalid cursor. Clarifying that behavior belongs in the same design/ADR surface changed by [M1-D3](../implementation-plan.md#m1-d3---refresh-composite-freshness-contract-amendment) rather than being left to later implementation choice. |
| M1-D3-R2 | Defer to M1-D2 | The reviewer is right that comment-level `updated_at` is still an unvalidated assumption. The cheapest place to confirm or falsify that assumption is [M1-D2](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary), which already owns auditing the refresh-operation path against the real `linear-client`/Linear surface. If [M1-D2](../implementation-plan.md#m1-d2---linear-domain-coverage-audit-and-adapter-boundary) cannot confirm the assumption, it should record the gap explicitly and route the necessary follow-on adjustment before [M3-1](../implementation-plan.md#m3-1---incremental-refresh-and-quarantined-root-recovery). |
| M1-D3-R3 | Fix now | The digest-format ambiguity is real. Because `refresh_cursor` is persisted in ticket frontmatter, the design should define at least the canonical comment ordering rule, whether the visible `v1:` prefix is normative versioning, and the digest/encoding contract rather than leaving all of that to first implementation. |
| M1-D3-R4 | Fix now | This is the write-side companion to the missing-cursor gap. Once `refresh_cursor` is part of the accepted file contract, the mutating flows that establish the baseline should say that they write it. Clarifying `sync` now is better than leaving later tickets to infer the rule only from the shared example in [docs/adr.md](../adr.md). |
| M1-D3-R5 | Fix now | This is low severity but worth tightening while the comment-signature contract is still docs-only. The design can cheaply clarify how the thread-level `resolved` flag enters the canonical input without changing the broader architecture or ticket sequencing. |
