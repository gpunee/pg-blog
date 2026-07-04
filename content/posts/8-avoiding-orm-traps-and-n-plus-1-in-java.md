---
title: "Avoiding ORM Traps and the N+1 Problem in Java"
date: 2026-07-03
description: "The N+1 query problem, lazy vs eager loading, fetch joins and entity graphs, projections, and pagination pitfalls in JPA and Hibernate — with the SQL each one actually generates."
tags:
  - Java
  - Databases
  - ORM
  - JPA
  - Hibernate
  - Performance
categories:
  - Java
draft: false
---

## Introduction

An ORM like JPA/Hibernate makes database access feel like working with plain objects. That is exactly the problem: a single innocent-looking loop can fire hundreds of SQL queries, and you won't see it until production slows to a crawl.

This post covers the ORM traps that bite Java teams most often — starting with the notorious **N+1 query problem** — and the concrete techniques that fix them.

---

## The N+1 Problem

Consider loading authors and printing their books:

```java
List<Author> authors = authorRepository.findAll();   // 1 query
for (Author author : authors) {
    System.out.println(author.getBooks().size());     // 1 query EACH
}
```

With a lazy `@OneToMany`, this runs **1** query to fetch the authors, then **N** more — one per author — to fetch each author's books. One hundred authors means 101 round trips to the database. That is N+1.

The insidious part: it works perfectly in tests with three rows and quietly melts under real data.

---

## Fix It With a Fetch Join

Tell the ORM to load the association in the *same* query using a `JOIN FETCH`:

```java
@Query("SELECT DISTINCT a FROM Author a LEFT JOIN FETCH a.books")
List<Author> findAllWithBooks();
```

This produces a single SQL query with a join. `DISTINCT` collapses the duplicate author rows the join produces. One query instead of 101.

For a more reusable option, an **entity graph** declares what to fetch without hand-writing JPQL:

```java
@EntityGraph(attributePaths = "books")
List<Author> findAll();
```

---

## Understand Lazy vs Eager — and Default to Lazy

JPA associations have a fetch type:

- `LAZY` — the association is loaded only when accessed.
- `EAGER` — it is always loaded, on every query that touches the entity.

Making associations `EAGER` to "avoid N+1" is a classic mistake: now *every* query drags the association along, even when you don't need it, and multiple eager collections can trigger a Cartesian-product explosion. **Default to `LAZY`** and fetch explicitly (join fetch / entity graph) at the specific call sites that need the data.

Note that `@ManyToOne` and `@OneToOne` are `EAGER` by default — usually worth overriding to `LAZY`.

---

## Don't Load Entities You Only Read — Use Projections

Fetching full entities to display three columns wastes memory and forces the persistence context to track objects you'll immediately discard. A **projection** selects only what you need:

```java
public interface AuthorSummary {
    String getName();
    int getBookCount();
}

@Query("""
    SELECT a.name AS name, COUNT(b) AS bookCount
    FROM Author a LEFT JOIN a.books b
    GROUP BY a.id, a.name
    """)
List<AuthorSummary> findSummaries();
```

The generated SQL selects two columns and aggregates in the database — no entity hydration, no lazy associations, far less garbage.

---

## Beware Pagination With Fetch Joins

Combining `JOIN FETCH` on a collection with pagination (`setMaxResults`) is a trap. Because the join multiplies rows, the database can't correctly apply the `LIMIT` — so Hibernate silently **pulls the entire result set into memory and paginates there**, often logging a warning like `firstResult/maxResults specified with collection fetch; applying in memory`.

The fix is a two-step fetch: page the IDs first, then fetch the collections for that page.

```java
// Step 1: page the root IDs only (safe LIMIT)
List<Long> ids = em.createQuery(
        "SELECT a.id FROM Author a ORDER BY a.name", Long.class)
    .setFirstResult(offset).setMaxResults(pageSize).getResultList();

// Step 2: fetch full entities + collections for just those IDs
List<Author> page = em.createQuery(
        "SELECT DISTINCT a FROM Author a LEFT JOIN FETCH a.books WHERE a.id IN :ids", Author.class)
    .setParameter("ids", ids).getResultList();
```

---

## Watch the Transaction Boundary: LazyInitializationException

Access a lazy association *after* the persistence context has closed and you get a `LazyInitializationException`. The right fix is to load what the caller needs **inside** the transaction (via fetch join / entity graph / a DTO), not to keep the session open across the web layer (the "Open Session in View" anti-pattern, which hides N+1 and holds connections too long).

---

## Always Look at the Generated SQL

The ORM's convenience hides its cost. During development, log the actual SQL and watch the query count:

```properties
# application.properties
spring.jpa.show-sql=true
spring.jpa.properties.hibernate.format_sql=true
# Even better: add datasource-proxy or Hibernate statistics to count queries
```

Most ORM performance bugs are invisible in the Java code and obvious the moment you read the SQL log. Make looking at it a habit.

---

## Practical Checklist

| Trap | Fix |
|------|-----|
| N+1 from lazy collections in a loop | `JOIN FETCH` or `@EntityGraph` |
| Everything `EAGER` | Default `LAZY`, fetch explicitly |
| Loading entities to read a few fields | Projections / DTOs |
| Pagination + collection fetch join | Page IDs, then fetch by ID |
| `LazyInitializationException` | Load inside the transaction |
| Hidden query counts | Log and read the SQL |

---

## Final Thoughts

JPA and Hibernate are powerful precisely because they hide the database — and dangerous for the same reason. The discipline that keeps ORM code fast is simple: default to lazy loading, fetch exactly what each use case needs and no more, project when you're only reading, and *always* look at the SQL the ORM actually generates. The abstraction is a convenience, not an excuse to stop thinking about queries.
