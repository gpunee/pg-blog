# Evidence — Increment 06: DB indexing & query-optimization posts (Java + Python)

- **Date:** 2026-07-03 · **Plan:** §3.4 + §3.2 rows 18–19 (APPROVED) · **Base:** `9f6848c` (uncommitted)
- **Implementer:** Sonnet subagent; **orchestrator independently re-ran build + code checks.**

## Created
- `content/posts/18-database-indexing-and-query-optimization-for-java.md` — B-tree cost, before/after `EXPLAIN ANALYZE` (Seq→Index Scan), composite leftmost-prefix, covering/`INCLUDE` index-only scans, four index-skip cases, selectivity/cardinality, keyset vs `OFFSET`, JPA/Hibernate angle (`@Table(indexes=…)` as hint, Flyway/Liquibase as source of truth, `show-sql`), anti-patterns; cross-links post 8.
- `content/posts/19-database-indexing-and-query-optimization-for-python.md` — same spine with Django (`Meta.indexes`, `db_index`, `sqlmigrate`) + SQLAlchemy (`Index`, `index=True`, Alembic) coverage, `iexact` function-index trap, FK-not-auto-indexed anti-pattern; cross-links post 9.

## Acceptance (orchestrator's own run)
- Build **clean**, **19 posts**.
- Post 18 → `categories/java/`, post 19 → `categories/python/`.
- Both aggregate at `tags/indexing/`; **`tags/databases/` correctly lists all four DB posts (8, 9, 18, 19)** — cross-topic aggregation confirmed.
- Both post dirs exist; both in sitemap.
- **Code correctness (orchestrator):** Java fences clean (no `def`/`self.`/`elif`/py-imports); all **7 Python blocks compile** clean.

## Deviations
None. Uncommitted (owner authorization pending).

Gate status: PASS. All content increments complete — proceed to Phase 5 full verify.
