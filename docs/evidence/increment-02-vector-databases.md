# Evidence — AI-Tooling Inc 02: Vector databases in practice (posts 22/23)

- **Date:** 2026-07-04 · **Plan:** `docs/plans/ai-tooling-series.md` §1(t2)/§3.1/§3.2/§3.3/§3.4/§3.5(t2)/§3a (APPROVED) · **Base:** `868aad8`
- **Implementer:** Sonnet subagent; **orchestrator independently re-ran the full §4.1 gate.**

## Delivered (2 posts, no other files)
- `content/posts/22-vector-databases-in-practice-for-java.md` — 256 lines
- `content/posts/23-vector-databases-in-practice-for-python.md` — 257 lines
- Scope: pgvector `vector(n)` + distance operators (`<->` L2, `<=>` cosine, `<#>` inner product), HNSW (`m`, `ef_construction`, `hnsw.ef_search`) and IVFFlat (`lists`, `ivfflat.probes`) index creation with real params + build-time semantics (HNSW no-training vs IVFFlat post-load k-means), recall-vs-latency trade-off, and a "when a dedicated store beats pgvector" decision table.

## Gate (orchestrator's own run)
1. **Build:** `hugo --gc --minify` → 117 pages, **no ERROR / no WARN / no REF**.
2. **Render + index:** both posts render; both URLs in `public/index.json`.
3. **Taxonomy:** `/categories/java/` has 22, `/categories/python/` has 23; **`/tags/databases/` aggregates 8, 9, 18, 19, 22, 23** (cross-topic link to the DB-indexing posts, as designed); `/tags/vectors/` aggregates 20, 21, 22, 23.
4. **Cross-links (backward-only):** resolve to 18/19 (indexing, ×2 each) and 20/21 (RAG, ×1 each) — all existing; no forward ref; build's no-REF result confirms resolution.
5. **Read-through:** fences pure (post 22: 2 java / 7 sql / 1 xml; post 23: 4 python / 6 sql / 1 sh; awk cross-idiom scan = 0 hits); all pgvector facts present. Secret-shape grep = **no real keys**; every `password` occurrence is anti-pattern guidance ("never an inline password / `postgresql://user:password@host/db` literal") teaching env-var + bind-parameter usage (§3a). No `budget_tokens`.
6. **Regression:** `node test/search.test.js` → 4/4 pass.

## pgvector grounding (implementer live-verified vs github.com/pgvector READMEs)
- Operators `<->`/`<=>`/`<#>`; HNSW defaults `m=16`, `ef_construction=64`, `hnsw.ef_search=40`; IVFFlat `lists≈rows/1000` (≤1M) / `sqrt(rows)` (>1M), `ivfflat.probes` default 1 / start `sqrt(lists)`; HNSW builds without data, IVFFlat needs data first. Java: `pgvector-java` (`PGvector.registerTypes`, Hibernate 6.4 `hibernate-vector`); Python: `pgvector-python` (psycopg2 `register_vector`, SQLAlchemy `VECTOR.cosine_distance`, Django `VectorField`).

## Deviations (reviewed & accepted → plan-synced)
- **No LLM-generation code** in either post — topic is pgvector mechanics; nothing to ground against `claude-api` (the Voyage-embedding pattern is referenced narratively via the RAG cross-links, not re-shown as code). Scope fact, not an omission.
- **Dedicated-store comparison is a decision table, not vendor code** — writing Pinecone/Weaviate/Qdrant snippets without live-verifying each would violate the grounding invariant; the plan only asks for the trade-off decision. Correct call.
- Both posts trimmed from 262 → 256/257 lines to land inside the ~180–260 band.

Gate status: PASS. AI-Tooling increment 03 may start.
