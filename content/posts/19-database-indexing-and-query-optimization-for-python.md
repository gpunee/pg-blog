---
title: "Database Indexing and Query Optimization for Python Developers"
date: 2026-07-03
description: "How B-tree indexes work, reading Postgres EXPLAIN ANALYZE output, composite index column order, and defining indexes correctly in Django and SQLAlchemy — with real query plans."
tags:
  - Python
  - Databases
  - Indexing
  - Performance
  - SQL
categories:
  - Python
draft: false
---

## Introduction

Fixing N+1 queries with `select_related`/`prefetch_related` or `selectinload` (see the [previous post](/posts/9-avoiding-orm-traps-and-n-plus-1-in-python/)) gets you down to a small, sane number of queries per request. The next bottleneck is what each query costs once the table has millions of rows — and that is almost always about indexing.

An index turns "scan every row" into "look it up directly." Skip it, and a query that's instant in development takes seconds once real data volume shows up in production.

---

## How Indexes Work: The B-Tree Intuition

Without an index, a `WHERE` clause forces a **sequential scan**: the database reads every row and checks the condition — `O(n)`, cost grows linearly with table size.

An index is a separate, sorted structure (almost always a **B-tree**) mapping column values to row locations. Because it's sorted and balanced, finding a value is a tree walk: `O(log n)`. On a 10-million-row table, that's the difference between reading 10 million rows and roughly 23 tree nodes.

This isn't free:

- **Writes get slower** — every `INSERT`/`UPDATE`/`DELETE` on an indexed column also updates the index.
- **Storage grows** — each index is a sorted copy of (part of) the data.

An index trades write cost and storage for read speed. Indexing a column you rarely filter or sort on is pure cost, no benefit.

---

## Reading Query Plans: EXPLAIN ANALYZE

Postgres' `EXPLAIN ANALYZE` shows what the planner actually did, not an estimate.

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

`Seq Scan` means Postgres read all ~1.2 million rows and discarded all but 41. `actual time` is real elapsed time — 118ms for one lookup.

**After** `CREATE INDEX idx_orders_customer_id ON orders (customer_id);`:

```
Index Scan using idx_orders_customer_id on orders  (cost=0.42..8.53 rows=42 width=96) (actual time=0.018..0.041 rows=41 loops=1)
  Index Cond: (customer_id = 48291)
Planning Time: 0.098 ms
Execution Time: 0.061 ms
```

`Index Scan` walks the B-tree straight to the matching rows: 118ms down to 0.06ms, roughly 1,900x — and the gap only widens as the table grows. What to check in any plan:

- **Seq Scan vs Index Scan / Index Only Scan** — the single biggest signal.
- **`rows` (estimate) vs `actual … rows`** — a large gap means stale table statistics (run `ANALYZE`).
- **`cost=startup..total`** — the planner's internal unit, useful for comparing plans, not wall-clock time.
- **`Rows Removed by Filter`** — a high number on a Seq Scan is a strong signal an index would help.

---

## Composite Indexes and Column Order

An index on `(customer_id, status)` is not the same as `(status, customer_id)`. B-tree indexes are searchable by their **leftmost prefix**: sorted first by the first column, then by the second within each value of the first.

```sql
CREATE INDEX idx_orders_customer_status ON orders (customer_id, status);
```

Usable for:

```sql
WHERE customer_id = 48291                          -- uses leftmost column
WHERE customer_id = 48291 AND status = 'SHIPPED'    -- uses both columns
```

**Not** usable (as an index scan on this index) for:

```sql
WHERE status = 'SHIPPED'   -- status alone isn't a leftmost prefix
```

Order columns by how they're actually queried: the column used alone or most selectively goes first.

### Covering Indexes and Index-Only Scans

If an index includes every column a query needs, Postgres can answer straight from the index — an **Index Only Scan**:

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

`Heap Fetches: 0` confirms the table itself was never touched.

### When an Index Is NOT Used

The planner will happily ignore an index that exists. Common reasons:

- **A function wraps the column**: `WHERE UPPER(email) = 'X'` can't use a plain index on `email` (a **functional index**, `CREATE INDEX ON users (UPPER(email))`, fixes this).
- **A leading wildcard**: `WHERE name LIKE '%smith'` can't use a standard B-tree — the sorted prefix is useless without a known prefix. `LIKE 'smith%'` can.
- **Low selectivity**: if 90% of rows match, a Seq Scan genuinely costs less than following an index and fetching almost every row anyway — the planner correctly skips the index.
- **Implicit type casts**: comparing a text column to an integer literal, or a timestamp column to an unparsed string, can force a scan. Match types explicitly.

---

## Selectivity and Cardinality

**Selectivity** is the fraction of rows a condition matches; **cardinality** is the number of distinct values in a column. An index on a boolean `is_active` column has cardinality 2 — following it typically still means fetching close to half the table, which costs more than scanning it outright. Indexes pay off on **high-cardinality, selective** columns (customer IDs, emails, timestamps), not on flags. If you must filter efficiently on a low-cardinality column, pair it in a composite index behind a selective column, or use a **partial index** (`CREATE INDEX ... WHERE is_active = true` for a rare status).

---

## Pagination: Keyset vs OFFSET

The earlier ORM post flagged that slicing a queryset after a `prefetch_related`/join doesn't page cleanly. The same physics show up at the SQL level with `OFFSET`.

```sql
-- Deep page: Postgres must still generate and discard the first 100,000 rows
SELECT * FROM orders ORDER BY id LIMIT 20 OFFSET 100000;
```

`OFFSET` can't skip rows using the index alone — it still walks past them. **Keyset (seek) pagination** remembers the last row seen and uses an indexed condition instead of an offset:

```sql
-- Keyset: uses the index on id directly, same cost on page 1 or page 5,000
SELECT * FROM orders WHERE id > :last_seen_id ORDER BY id LIMIT 20;
```

Django and SQLAlchemy both express this as an ordinary indexed filter:

```python
# Django: keyset pagination instead of Paginator's OFFSET-based pages
Order.objects.filter(id__gt=last_seen_id).order_by("id")[:20]

# SQLAlchemy
session.query(Order).filter(Order.id > last_seen_id).order_by(Order.id).limit(20)
```

This requires (and benefits from) an index on the ordering column — exactly the `idx_orders_customer_id`-style index above.

---

## The Django and SQLAlchemy Angle

Neither ORM invents the right indexes for you — that's still informed by the plans above, not by the model definition alone.

### Django — `Meta.indexes` and `db_index`

```python
class Order(models.Model):
    customer_id = models.IntegerField(db_index=True)
    status = models.CharField(max_length=20)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        indexes = [
            models.Index(fields=["customer_id", "status"], name="idx_orders_customer_status"),
        ]
```

`db_index=True` is fine for a single column; for composite/covering indexes use `Meta.indexes`. Either way, this only takes effect through a **migration** — Django generates one when you run `makemigrations`, and that migration file (not the model) is what actually creates the index:

```python
# orders/migrations/0007_add_customer_status_index.py
operations = [
    migrations.AddIndex(
        model_name="order",
        index=models.Index(fields=["customer_id", "status"], name="idx_orders_customer_status"),
    ),
]
```

Review the generated SQL with `python manage.py sqlmigrate orders 0007` before applying it in production, and consider Postgres' `CREATE INDEX CONCURRENTLY` for large existing tables (Django's `AddIndexConcurrently` on Postgres, run outside an atomic migration).

### SQLAlchemy — `Index(...)` / `index=True` + Alembic

```python
from sqlalchemy import Column, Integer, String, Numeric, Index

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, index=True)
    status = Column(String(20))
    total_amount = Column(Numeric(10, 2))

    __table_args__ = (
        Index("idx_orders_customer_status", "customer_id", "status"),
    )
```

The model declares intent; the actual DDL ships through **Alembic**:

```python
# alembic/versions/xxxx_add_customer_status_index.py
def upgrade():
    op.create_index(
        "idx_orders_customer_status", "orders", ["customer_id", "status"]
    )

def downgrade():
    op.drop_index("idx_orders_customer_status", table_name="orders")
```

### Spotting a plan-hostile query

Log or inspect the generated SQL rather than guessing:

```python
# Django: see queries actually executed (DEBUG=True)
from django.db import connection
print(connection.queries[-1]["sql"])

# SQLAlchemy: echo generated SQL, or inspect a specific query's plan
engine = create_engine(url, echo=True)

result = session.execute(
    text("EXPLAIN ANALYZE SELECT * FROM orders WHERE customer_id = :cid"),
    {"cid": 48291},
)
for row in result:
    print(row)
```

A query that looks fine in Python can compile to a function-wrapped predicate that defeats an index:

```python
Order.objects.filter(status__iexact="shipped")   # Django: often compiles to UPPER(status) = 'SHIPPED'
```

That's the "function on the column" case above. Either add a functional index (`CREATE INDEX ON orders (UPPER(status))`) or normalize `status` on write so the query can compare it directly.

---

## Anti-Patterns

- **Indexing every column "just in case."** Each index slows every write on that table and adds storage; index only what real queries filter, join, or sort on.
- **Redundant indexes.** A single-column index on `customer_id` is redundant once `(customer_id, status)` exists — the composite index already serves lookups on `customer_id` alone.
- **Not indexing foreign keys used in joins.** Postgres does **not** automatically index FK columns; Django adds one for `ForeignKey` fields by default, but a raw SQLAlchemy `ForeignKey` column does not get an index unless you add `index=True` or an explicit `Index`.
- **Trusting the model definition alone in production.** Neither `db_index=True` nor SQLAlchemy's `index=True` does anything until a migration actually runs the DDL.

---

## Practical Checklist

| Situation | Action |
|-----------|--------|
| Query does a Seq Scan on a large table with a selective filter | Add an index on the filtered column(s) |
| Filtering/sorting on two columns together | Composite index, most selective / most-used-alone column first |
| Query reads only indexed columns | Add `INCLUDE` columns for an Index Only Scan |
| `.filter(x__iexact=...)` or leading `%wildcard%` | Functional index or rewrite the predicate |
| Boolean/low-cardinality filter | Partial index, or pair behind a selective column |
| Deep pagination (`OFFSET 100000`) | Keyset pagination on an indexed column |
| FK column used in joins (SQLAlchemy) | Explicitly set `index=True` — it isn't automatic |
| Schema managed by Django/SQLAlchemy models | Ship the DDL via a migration (Django migration / Alembic), not just the model |

---

## Final Thoughts

Indexes are not a checkbox on a model — they're a targeted trade of write cost and storage for read speed, and the only way to know if the trade pays off is to read the actual query plan. Learn to read `EXPLAIN ANALYZE`, order composite indexes by how you really query, watch for the handful of things that silently defeat an index, and keep the DDL in migrations where it belongs. The ORM writes the SQL; the query plan tells you the truth about it.
