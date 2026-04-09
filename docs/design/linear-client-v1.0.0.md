# linear-client: API Reference Summary (Retired)

> **Status**: Retired by
> [M5-D2](../implementation-plan.md#m5-d2---design-artifact-refresh-for-v110-workspace-model)
>
> This local API reference summary was written against `linear-client` v1.0.0.
> It is now redundant: the full `linear-client` source lives in the multi-root
> workspace as a sibling clone (see
> [docs/workspace-setup.md](../workspace-setup.md)), and the library's own
> documentation is the authoritative reference.

## Where to find what this document used to provide

| Former content | Current authoritative source |
| --- | --- |
| Installation and workspace layout | [docs/workspace-setup.md](../workspace-setup.md) and [README.md](../../README.md#developer-setup) |
| Architecture (domain layer vs. GraphQL services) | [linear-client `__init__.py` module docstring](../../../linear-client/src/linear_client/__init__.py), [linear-client `docs/design/dependency-map.md`](../../../linear-client/docs/design/dependency-map.md) |
| Authentication and env-var configuration | [linear-client `__init__.py`](../../../linear-client/src/linear_client/__init__.py), [`scripts/.linear_env.sh.sample`](../../scripts/.linear_env.sh.sample) |
| Domain-layer API surface and patterns | [linear-client `examples/`](../../../linear-client/examples/), [linear-client `docs/pub/`](../../../linear-client/docs/pub/) |
| Exception hierarchy | [linear-client `src/linear_client/errors.py`](../../../linear-client/src/linear_client/errors.py) |
| Boundary guidance (domain-layer-first, narrow raw-GQL) | [docs/design/linear-domain-coverage-audit.md](linear-domain-coverage-audit.md) (stable index pointing to the current versioned audit) |
| Type surface and semantic aliases | [linear-client `src/linear_client/types.py`](../../../linear-client/src/linear_client/types.py), [docs/design/linear-domain-coverage-audit.md](linear-domain-coverage-audit.md) §3 |
| Live validation workspace (`ARK` team) | Not migrated to a current design document. Historical guidance in [docs/execution/M1-D1.md](../execution/M1-D1.md), [docs/execution/M3-O1.md](../execution/M3-O1.md), and [docs/design/refresh-freshness-validation.md](refresh-freshness-validation.md). |

Existing references to this file in done-ticket execution artifacts and
historical planning documents are path-correct and do not need updating; they
describe the state of the dependency boundary at the time those tickets were
completed.
