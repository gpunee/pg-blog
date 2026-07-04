---
title: "Database Indexing and Query Optimization for Java Developers"
date: 2026-07-03
description: "How B-tree indexes actually work, reading Postgres EXPLAIN ANALYZE output, composite index column order, and why JPA/Hibernate entities alone don't create indexes — with real query plans."
tags:
  - Java
  - Databases
  - Indexing
  - Performance
  - SQL
categories:
  - Java
draft: false
---

## Introduction

Fixing N+1 queries (see the [previous post](/posts/8-avoiding-orm-traps-and-n-plus-1-in-java/)) gets your Hibernate app down to a handful of queries per request. The next bottleneck is what each of those queries costs once your tables have millions of rows — and that is almost always a question of indexing.

An index turns "scan every row" into "look it up directly." Get the index wrong — or skip it — and a query that took 2ms in development takes 4 seconds in production once real data volume shows up.

---

## How Indexes Work: The B-Tree Intuition

Without an index, a `WHERE` clause forces a **sequential scan**: the database reads every row and checks the condition. That's `O(n)` — cost grows linearly with table size.

An index is a separate, sorted data structure (almost always a **B-tree**) that maps column values to row locations. Because it's sorted and balanced, finding a value is a tree walk: `O(log n)`. On a 10-million-row table, that's the difference between reading 10 million rows and reading roughly 23 tree nodes.

The cost is not free:

- **Writes get slower.** Every `INSERT`/`UPDATE`/`DELETE` on an indexed column must also update the index structure.
- **Storage grows.** Each index is a copy of (part of) the data, sorted differently.

An index is a trade: you pay on every write so that specific reads become fast. Indexing a column you rarely filter or sort on is pure cost with no benefit.

---

## Reading Query Plans: EXPLAIN ANALYZE

Postgres' `EXPLAIN ANALYZE` shows what the planner actually did — not what you hope it did.

**Before an index**, filtering `orders` by `customer_id`:

```sql
EXPLAIN ANALYZE
SELECT * FROM orders WHERE customer_id = 48291;
```

```
Seq Scan on orders  (cost=0.00..21453.00 rows=42 width=96) (actual time=0.021..118.442 rows=41 loops=1)
  Filter: (customer_id = 48291)
  Rows Removed by Filter: 1199959
Planning Time: 0.112 ms
Execution Time: 118.471 ms
```

`Seq Scan` means Postgres read all ~1.2 million rows and threw away all but 41 of them. `actual time` is the real elapsed time, not an estimate — 118ms for one lookup.

**After** `CREATE INDEX idx_orders_customer_id ON orders (customer_id);`, the same query:

```
Index Scan using idx_orders_customer_id on orders  (cost=0.42..8.53 rows=42 width=96) (actual time=0.018..0.041 rows=41 loops=1)
  Index Cond: (customer_id = 48291)
Planning Time: 0.098 ms
Execution Time: 0.061 ms
```

`Index Scan` walks the B-tree straight to the matching rows. Execution time drops from 118ms to 0.06ms — roughly 1,900x, and the gap only widens as the table grows. What to check in any plan:

- **Seq Scan vs Index Scan / Index Only Scan** — the single biggest signal.
- **`rows` (estimate) vs `actual … rows`** — a big gap means the planner's statistics are stale (`ANALYZE` the table).
- **`cost=startup..total`** — the planner's internal unit, useful for comparing two plans, not wall-clock time.
- **`Rows Removed by Filter`** — a high number on a Seq Scan is a strong sign an index would help.

---

## Composite Indexes and Column Order

An index on `(customer_id, status)` is not the same as one on `(status, customer_id)`. B-tree indexes are searchable by their **leftmost prefix**: the index is sorted first by the first column, then by the second within each value of the first.

```sql
CREATE INDEX idx_orders_customer_status ON orders (customer_id, status);
```

This index is usable for:

```sql
WHERE customer_id = 48291                         -- uses leftmost column
WHERE customer_id = 48291 AND status = 'SHIPPED'   -- uses both columns
```

But **not** usable (as an index scan on this index) for:

```sql
WHERE status = 'SHIPPED'   -- status alone isn't a leftmost prefix
```

Order the columns by how they're actually queried: the column used alone or most selectively goes first.

### Covering Indexes and Index-Only Scans

If an index includes every column a query needs, Postgres can answer the query straight from the index without touching the table at all — an **Index Only Scan**:

```sql
CREATE INDEX idx_orders_customer_status_total
    ON orders (customer_id, status) INCLUDE (total_amount);
```

```sql
EXPLAIN ANALYZE
SELECT status, total_amount FROM orders WHERE customer_id = 48291;
```

```
Index Only Scan using idx_orders_customer_status_total on orders
  (cost=0.42..4.65 rows=41 width=13) (actual time=0.015..0.028 rows=41 loops=1)
  Index Cond: (customer_id = 48291)
  Heap Fetches: 0
```

`Heap Fetches: 0` confirms the table itself was never read.

### When an Index Is NOT Used

The planner will happily ignore an index that exists. Common reasons:

- **A function wraps the column**: `WHERE UPPER(email) = 'X'` cannot use a plain index on `email` (a **functional index**, `CREATE INDEX ON users (UPPER(email))`, fixes this).
- **A leading wildcard**: `WHERE name LIKE '%smith'` can't use a standard B-tree — the sorted prefix is useless when you don't know the prefix. `LIKE 'smith%'` *can*.
- **Low selectivity**: if 90% of rows match, a Seq Scan is genuinely cheaper than following an index and then fetching almost every row anyway — the planner will (correctly) skip the index.
- **Implicit type casts**: comparing a text column to an integer literal, or a timestamp column to a string that requires parsing, can force a scan. Match types explicitly.

---

## Selectivity and Cardinality

**Selectivity** is the fraction of rows a condition matches; **cardinality** is the number of distinct values in a column. An index on a boolean `is_active` column has cardinality 2 — no matter how the tree is shaped, following it typically still means fetching close to half the table, which costs more than just scanning it. Indexes pay off on **high-cardinality, selective** columns (customer IDs, emails, timestamps) — not on flags. If you must filter on a low-cardinality column efficiently, pair it in a composite index behind a selective column, or use a **partial index** (`CREATE INDEX ... WHERE is_active = true` for a rare status).

---

## Pagination: Keyset vs OFFSET

The earlier ORM post flagged that a `LIMIT` on top of a collection fetch join doesn't page cleanly. The same physics show up at the SQL level with `OFFSET`.

```sql
-- Deep page: Postgres must still generate and discard the first 100,000 rows
SELECT * FROM orders ORDER BY id LIMIT 20 OFFSET 100000;
```

`OFFSET` cannot skip rows using the index alone — it still has to walk past them. **Keyset (seek) pagination** avoids this by remembering the last row seen and using an indexed condition instead of an offset:

```sql
-- Keyset: uses the index on id directly, same cost on page 1 or page 5,000
SELECT * FROM orders WHERE id > :last_seen_id ORDER BY id LIMIT 20;
```

This requires (and benefits from) an index on the ordering column — exactly the `idx_orders_customer_id`-style index discussed above.

---

## The JPA/Hibernate Angle

Hibernate generates SQL from JPQL/Criteria queries, but **it does not know your query patterns well enough to invent the right indexes** — that's still your job, informed by the plans above.

### `@Table(indexes = ...)` is a hint, not the source of truth

```java
@Entity
@Table(name = "orders", indexes = {
    @Index(name = "idx_orders_customer_id", columnList = "customer_id"),
    @Index(name = "idx_orders_customer_status", columnList = "customer_id, status")
})
public class Order {
    @Id
    private Long id;

    @Column(name = "customer_id")
    private Long customerId;

    private String status;
    private BigDecimal totalAmount;
}
```

This annotation only takes effect if Hibernate is generating your DDL (`hibernate.hbm2ddl.auto`), which production systems should not rely on. **Indexes belong in versioned migrations** (Flyway or Liquibase), so they're reviewed, ordered, and applied identically across environments:

```sql
-- V12__add_orders_customer_status_index.sql (Flyway)
CREATE INDEX CONCURRENTLY idx_orders_customer_status
    ON orders (customer_id, status);
```

(`CONCURRENTLY` avoids locking the table for writes while the index builds — worth using on any table already in production.) Keep the `@Index` annotation as documentation/for test environments that do use `hbm2ddl.auto=create`, but treat the migration as authoritative.

### Spotting a plan-hostile query from Hibernate

Turn on SQL logging to see what Hibernate actually sends:

```properties
# application.properties
spring.jpa.show-sql=true
spring.jpa.properties.hibernate.format_sql=true
```

A JPQL query that looks innocent can generate a function-wrapped predicate that defeats an index:

```java
@Query("SELECT o FROM Order o WHERE FUNCTION('lower', o.status) = :status")
List<Order> findByStatusCaseInsensitive(@Param("status") String status);
```

This compiles to `WHERE lower(status) = ?` — exactly the "function on the column" case above. Either add a functional index (`CREATE INDEX ON orders (lower(status))`) or normalize `status` on write so the query can compare it directly.

---

## Anti-Patterns

- **Indexing every column "just in case."** Each index slows every write on that table and adds storage; index only columns your real queries filter, join, or sort on.
- **Redundant indexes.** `(customer_id)` is redundant once `(customer_id, status)` exists — the composite index already serves lookups on `customer_id` alone.
- **Not indexing foreign keys used in joins.** Postgres does **not** automatically index FK columns. A `JOIN orders o ON o.customer_id = c.id` without an index on `orders.customer_id` forces a scan on the large side of the join.
- **Trusting `@Table(indexes=...)` alone in production.** If `hbm2ddl.auto` isn't generating your schema, that annotation does nothing — the migration is what ships.

---

## Practical Checklist

| Situation | Action |
|-----------|--------|
| Query does a Seq Scan on a large table with a selective filter | Add an index on the filtered column(s) |
| Filtering/sorting on two columns together | Composite index, most selective / most-used-alone column first |
| Query reads only indexed columns | Add `INCLUDE` columns for an Index Only Scan |
| `WHERE UPPER(col) = ...` or leading `%wildcard%` | Functional index or rewrite the predicate |
| Boolean/low-cardinality filter | Partial index, or pair behind a selective column |
| Deep pagination (`OFFSET 100000`) | Keyset pagination on an indexed column |
| FK column used in joins | Explicitly index it — Postgres won't do it for you |
| Schema managed by JPA entities | Ship the DDL via Flyway/Liquibase, not `hbm2ddl.auto` |

---

## Final Thoughts

Indexes are not a checkbox — they're a targeted trade of write cost and storage for read speed, and the only way to know if the trade is worth it is to read the actual query plan. Learn to read `EXPLAIN ANALYZE`, order composite indexes by how you really query, watch for the handful of things that silently defeat an index, and keep the DDL in migrations where it belongs. The ORM writes the SQL; the query plan tells you the truth about it.
