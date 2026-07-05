---
title: "Vector Databases in Practice for Python"
date: 2026-07-04
description: "pgvector vs. dedicated vector stores: the vector column type, L2/cosine/inner-product distance operators, HNSW and IVFFlat index parameters, and the recall-vs-latency trade-off, with psycopg and SQLAlchemy examples."
tags:
  - Python
  - AI
  - Databases
  - Vectors
  - RAG
  - Performance
categories:
  - Python
draft: false
---

## Introduction

[RAG From Scratch in Python]({{< ref "21-rag-from-scratch-in-python.md" >}}) built retrieval with nothing but a list of floats and `sorted()`: cosine similarity computed in a loop, top-k picked with a slice. That post said outright that this is a brute-force `O(n)` scan — fine for a few thousand chunks, the wrong tool once a corpus reaches millions. This post picks up exactly there: how do you store and search vectors at that scale, using Postgres, and when do you need something else entirely?

The mental model is the same one [Database Indexing and Query Optimization for Python Developers]({{< ref "19-database-indexing-and-query-optimization-for-python.md" >}}) built for B-trees: an index is a trade, not a free lunch. A B-tree trades write cost and storage for `O(log n)` lookups instead of a sequential scan. A vector index trades **recall** — how often it finds the true nearest neighbors — for query speed, because at scale finding the *exact* nearest neighbor over millions of high-dimensional vectors is too expensive to do on every query. Everything below is illustrative SQL and Python, verified against the live [pgvector](https://github.com/pgvector/pgvector) documentation — no companion repo, no live network calls.

---

## pgvector: Postgres as a Vector Store

[pgvector](https://github.com/pgvector/pgvector) is a Postgres extension that adds a `vector` column type and a handful of distance operators, so embeddings live in the same table — and the same transaction — as the rest of your data. Enable it once per database, then declare a column with a fixed dimension count matching your embedding model (`voyage-4` from the RAG post produces 1024-dimensional vectors):

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document_chunks (
    id           bigserial PRIMARY KEY,
    document_id  text NOT NULL,
    chunk_index  int NOT NULL,
    content      text NOT NULL,
    embedding    vector(1024) NOT NULL
);
```

pgvector supports three distance operators relevant here (plus L1 and two binary-vector operators not used in this post):

| Operator | Distance | Notes |
|---|---|---|
| `<->` | L2 (Euclidean) | Straight-line distance between vectors |
| `<=>` | Cosine distance | `1 - cosine_similarity`; use `1 - (a <=> b)` to recover similarity |
| `<#>` | Negative inner product | Returns the *negative* dot product — Postgres only supports ascending-order index scans, so pgvector negates it; multiply by `-1` to get the real inner product |

Since Voyage embeddings are normalized to unit length (the same fact the RAG post used to justify a plain dot product), cosine distance and inner product rank identically here — cosine is the natural default because it reads intuitively (0 = identical direction) without depending on that normalization assumption holding forever:

```sql
SELECT id, document_id, content, embedding <=> '[0.01,0.02,...]' AS distance
FROM document_chunks
ORDER BY embedding <=> '[0.01,0.02,...]'
LIMIT 5;
```

Without any index, this is **exact** nearest-neighbor search — a sequential scan comparing the query vector against every row, exactly the brute-force scan the RAG post wrote in Python, just run inside Postgres instead of the interpreter.

---

## Storing and Querying Vectors from Python

Install the `pgvector` package, which teaches psycopg (and SQLAlchemy) how to adapt a Python list to a `vector` column:

```sh
pip install pgvector psycopg2-binary
```

```python
import os
import psycopg2
from pgvector.psycopg2 import register_vector

conn = psycopg2.connect(os.environ["DATABASE_URL"])  # env only, never hardcoded
register_vector(conn)  # teaches psycopg2 about the vector type

with conn.cursor() as cur:
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

with conn.cursor() as cur:
    cur.execute(
        "INSERT INTO document_chunks (document_id, chunk_index, content, embedding) "
        "VALUES (%s, %s, %s, %s)",
        (chunk.document_id, chunk.index, chunk.text, embedding),  # embedding: list[float]
    )

with conn.cursor() as cur:
    cur.execute(
        "SELECT document_id, content, embedding <=> %s AS distance "
        "FROM document_chunks ORDER BY embedding <=> %s LIMIT %s",
        (query_embedding, query_embedding, 20),
    )
    rows = cur.fetchall()

conn.commit()
```

Two things worth calling out: the connection string comes from `DATABASE_URL` (or a `PG_CONN`-style env var) — **never** an inline `postgresql://user:password@host/db` literal in code, config, or a log line — and the query vector is a **bind parameter** (`%s`), not an f-string dropped into the query. Building `f"... ORDER BY embedding <=> '{query_embedding}'"` reopens the exact SQL-injection surface the ORM posts warn about, just with a vector literal instead of a `WHERE` clause value.

If your team already runs SQLAlchemy or Django for the rest of the schema (as [post 19]({{< ref "19-database-indexing-and-query-optimization-for-python.md" >}}) assumed), `pgvector` ships first-class column types and index classes for both:

```python
# SQLAlchemy
from pgvector.sqlalchemy import VECTOR

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id = Column(BigInteger, primary_key=True)
    document_id = Column(String)
    content = Column(String)
    embedding = mapped_column(VECTOR(1024))

# nearest neighbors, cosine distance
session.scalars(
    select(DocumentChunk).order_by(DocumentChunk.embedding.cosine_distance(query_embedding)).limit(20)
)
```

```python
# Django: VectorField + CosineDistance, same idea
from pgvector.django import VectorField, CosineDistance
# embedding = VectorField(dimensions=1024)  # on the model
DocumentChunk.objects.order_by(CosineDistance("embedding", query_embedding))[:20]
```

Either way, the index that makes this fast at scale is defined in a migration — Alembic or a Django migration — the same discipline post 19 argued for B-tree indexes: reviewed DDL, not a model field alone.

---

## Exact vs. Approximate Nearest Neighbor

By default pgvector does **exact** search: every query is a full comparison against every row, guaranteeing perfect recall (it always finds the true nearest neighbors) at the cost of scanning the whole table — the same trade-off as a Seq Scan in post 19, just over vector distance instead of an equality filter. Adding an **approximate** index (HNSW or IVFFlat) changes the answer: you'll see slightly different, occasionally imperfect results in exchange for sub-linear query time. This is worth stating plainly because it's a real behavior change, not just a performance knob — once an approximate index exists, a query that used to return the mathematically closest 5 rows may return 4 of them plus a close 6th.

---

## HNSW: A Graph Index with Real Parameters

HNSW (Hierarchical Navigable Small World) builds a multilayer graph over the vectors and walks it at query time instead of scanning linearly. It gives the best speed-recall trade-off of pgvector's two index types, at the cost of slower builds and more memory — and unlike IVFFlat, it can be created before any data is loaded, since there's no training step:

```sql
CREATE INDEX ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

- **`m`** — the max number of graph connections per node per layer (default **16**). Higher `m` means a denser graph: better recall, larger index, slower builds and inserts.
- **`ef_construction`** — the size of the candidate list explored while *building* the graph (default **64**). Higher values examine more candidates per insertion, improving recall at the cost of build time — this is a one-time (or per-insert) cost, not a per-query one.

Query-time recall is controlled separately, without rebuilding anything:

```sql
SET hnsw.ef_search = 100;   -- default 40; higher = better recall, slower queries
```

`ef_search` is the size of the candidate list explored *at search time* — raise it for a query where recall matters more than latency (a one-off analytics query), lower it for a hot path where p99 latency is the binding constraint. Use `SET LOCAL` inside a transaction to scope the change to one query rather than the whole session.

---

## IVFFlat: Lists and Probes

IVFFlat (Inverted File with Flat compression) partitions the vector space into `lists` clusters via k-means, then at query time searches only the `probes` clusters nearest the query vector — faster to build and lighter on memory than HNSW, but with a worse speed-recall curve:

```sql
CREATE INDEX ON document_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

- **`lists`** — the number of clusters. pgvector's own guidance: start at `rows / 1000` for up to ~1M rows, `sqrt(rows)` beyond that. For a 200k-row chunk table, `lists = 200` is a reasonable starting point.
- **IVFFlat needs data before it's built** — unlike HNSW, the k-means training step needs representative vectors present, so build this index *after* the initial bulk load, not on an empty table.

```sql
SET ivfflat.probes = 10;   -- default 1; pgvector suggests sqrt(lists) as a starting point
```

Probing more clusters raises recall at the cost of scanning more of the index — the direct analogue of `ef_search` for HNSW.

| | HNSW | IVFFlat |
|---|---|---|
| Build time | Slower | Faster |
| Memory | More | Less |
| Query speed-recall | Better | Worse |
| Needs data before building? | No | Yes (k-means training) |
| Key build param | `m`, `ef_construction` | `lists` |
| Key query param | `ef_search` | `probes` |

**Default choice:** reach for HNSW unless build time or memory on a very large table rules it out — its speed-recall curve is better at query time, which is usually the cost that matters more since queries vastly outnumber builds.

---

## Recall vs. Latency: Measuring the Trade-off, Not Guessing It

Every knob above — `m`, `ef_construction`, `ef_search`, `lists`, `probes` — moves the same dial in the same direction: more work per query or build buys more recall. The only way to pick real values is to measure, not assume a default is right for your data:

1. Build a small **ground-truth set**: for a sample of queries, compute the true top-k with exact search (no index, or `enable_indexscan` forced off) — this is what post 21's brute-force scan already gives you for free at small scale.
2. Run the same queries with the approximate index at a few `ef_search` (or `probes`) values, and compute **recall@k**: what fraction of the true top-k did the approximate search actually return?
3. Record query latency (p50/p95) at each setting alongside recall.

```python
import time

def recall_at_k(cur, query_embedding, k, ef_search):
    cur.execute(f"SET LOCAL hnsw.ef_search = {ef_search}")
    start = time.perf_counter()
    cur.execute(
        "SELECT id FROM document_chunks ORDER BY embedding <=> %s LIMIT %s",
        (query_embedding, k),
    )
    approx_ids = {row[0] for row in cur.fetchall()}
    latency_ms = (time.perf_counter() - start) * 1000
    return approx_ids, latency_ms

# ground_truth_ids computed once with the index disabled (exact scan)
approx_ids, latency_ms = recall_at_k(cur, query_embedding, k=10, ef_search=100)
recall = len(approx_ids & ground_truth_ids) / len(ground_truth_ids)
```

Comparing recall and latency across `ef_search` values (40, 100, 200, ...) traces out a curve specific to your data's dimensionality and cluster structure — a generic "use `ef_search = 100`" recommendation from a blog post (including this one) is a starting point, not a target. Pick the lowest setting that clears your recall bar at your query volume, and re-measure whenever the corpus grows meaningfully — recall characteristics shift as the graph or clustering grows.

---

## When a Dedicated Vector Store Beats pgvector

pgvector's biggest advantage is that it isn't a new system: vectors live in the same database, transaction, and backup as the data they describe, joined with ordinary SQL against `document_id`, tenant, or permission columns. That advantage erodes as scale or specialization needs grow:

| Situation | Lean toward |
|---|---|
| Millions of vectors, moderate QPS, data already in Postgres | **pgvector** — one system, ACID joins, existing ops muscle |
| Billions of vectors, very high QPS, dedicated ANN tuning (product quantization, disk-based indexes) | **Dedicated store** (e.g. a managed vector database) — built for that scale as the primary workload |
| Need transactional consistency between vectors and relational data (e.g. permission checks in the same query) | **pgvector** — a join, not a fan-out across two systems |
| Need built-in multi-tenant sharding/replication tuned specifically for vector workloads at large scale | **Dedicated store** — that's the product's core engineering investment |
| Team already operates Postgres; no dedicated platform team for a new datastore | **pgvector** — avoids a new operational surface (see the DevOps hat: justify new infrastructure, don't default to it) |
| Need hybrid search (dense + sparse/BM25) as a first-class, managed feature | Either — pgvector supports combining a vector index with ordinary Postgres full-text search, but a dedicated store may ship it more turnkey |

The honest rule of thumb: **start with pgvector if you already run Postgres**, and revisit only when you hit a wall pgvector genuinely can't clear at your scale — most teams retrieving against thousands to low millions of chunks never do. Reaching for a dedicated store before that point is optimizing for a scale you don't have yet, at the cost of a second system to secure, back up, and operate.

---

## Practical Checklist

| Situation | Action |
|-----------|--------|
| Fewer than a few hundred thousand vectors, exploring | Skip the index — exact search is fast enough and gives perfect recall |
| Corpus growing past that, latency-sensitive | Add an HNSW index; start `m=16, ef_construction=64` (the defaults) |
| Very large table, memory-constrained build | Consider IVFFlat; build it *after* the bulk load, not before |
| Query recall too low | Raise `hnsw.ef_search` or `ivfflat.probes` and re-measure — don't guess a value |
| Query latency too high, recall acceptable | Lower `ef_search`/`probes` — you're paying for recall you don't need |
| Filtering by tenant/category alongside vector search | Bind-parameterize the filter value; never f-string it into the query |
| Connection details | `DATABASE_URL`/`PG_CONN` from the environment — never an inline password |
| Considering a dedicated vector store | Confirm you've actually hit a wall pgvector can't clear — not just anticipating one |

---

## Final Thoughts

The vector index conversation is the same conversation post 19 already had about B-trees, just with a different currency: instead of trading write cost for read speed, you're trading recall for query speed. HNSW's `m`/`ef_construction` and IVFFlat's `lists`/`probes` are not settings to copy from a tutorial — they're levers on a curve you should plot against your own data before choosing a point on it. And the biggest decision isn't HNSW vs. IVFFlat at all: it's whether you need a dedicated vector store rather than the Postgres table you're probably already running.
