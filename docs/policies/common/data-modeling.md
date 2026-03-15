# Data Modeling — Pydantic vs dataclass

> **Status**: Active
> **Scope**: All Python source in this project

---

## Decision Rule

Use **Pydantic** (`BaseModel` / `BaseSettings`) when data crosses a trust or serialization boundary. Use **`dataclass`** when data is internal and already trusted.

### When to use Pydantic

1. **Configuration from environment** — `BaseSettings` subclasses that read and validate env vars (e.g. `ACPLinearConfig`).
2. **API request/response shapes** — data entering or leaving the system (Linear webhook payloads, GitHub webhook payloads, CLI output schemas).
3. **Inter-component messages** — data that flows between independently-developed components where the contract must be enforced (e.g. agent-to-agent messages, metrics file schemas).
4. **Persisted/serialized data** — anything written to disk or sent over the wire where `.model_dump()` / `.model_validate()` round-tripping is needed.

### When to use dataclass

1. **Internal state containers** — objects that hold live or opaque references that cannot be serialized (e.g. `LinearContext` holds the `Linear` client instance and domain objects).
2. **Private implementation structs** — module-internal data that never leaves its enclosing module or package (e.g. `_BlockerCacheEntry`, `TodoPage`).
3. **Mutable state** — caches, accumulators, or state machines where values are constructed from already-validated data and mutation is the primary use case (e.g. `BlockerCache`).
4. **Performance-sensitive paths** — hot-loop structures where Pydantic's construction and validation overhead is unnecessary (e.g. cache entries evaluated many times per cycle).

### Deciding heuristic

> Does this data come from, or go to, somewhere I don't control?
>
> **Yes** -> Pydantic. &nbsp;&nbsp; **No** (constructed internally from trusted values) -> dataclass is appropriate.

### What is NOT allowed

- Plain `dict` as a structured data model at any boundary (trust, serialization, or module).
- Untyped `dataclass` (all fields must have type annotations regardless of which mechanism is used).

---

## Examples from this codebase

| Class | Mechanism | Why |
|---|---|---|
| `ACPLinearConfig` | `BaseSettings` | Env var input; needs validation and `ACP_` prefix mapping |
| `LinearContext` | `dataclass` | Internal state; holds live client objects that cannot be serialized |
| `BlockerCache` | `dataclass` | Mutable internal cache; constructed from trusted resolved data |
| `_BlockerCacheEntry` | `dataclass` | Private struct; never leaves the readiness module |
| `TodoPage` | `dataclass` | Adapter-internal DTO; holds live domain objects from the bridge |
