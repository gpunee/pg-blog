---
title: "Avoiding ORM Traps and the N+1 Problem in Python"
date: 2026-07-03
description: "The N+1 query problem in SQLAlchemy and the Django ORM — eager loading with selectinload/joinedload and select_related/prefetch_related, projections, and pagination pitfalls."
tags:
  - Python
  - Database
  - SQLAlchemy
  - Django
  - Performance
categories:
  - Database
draft: false
---

## Introduction

Python's ORMs — SQLAlchemy and the Django ORM — are a joy to write and dangerously easy to make slow. A loop over a queryset that reads one related field can silently fire hundreds of queries. It looks fine in development and falls over on real data.

This post covers the ORM traps Python teams hit most, starting with the **N+1 query problem**, in both SQLAlchemy and Django.

---

## The N+1 Problem

You load authors and print each author's book count:

```python
# Django
for author in Author.objects.all():        # 1 query
    print(author.books.count())             # 1 query PER author
```

```python
# SQLAlchemy
for author in session.query(Author).all():  # 1 query
    print(len(author.books))                # 1 lazy-load query PER author
```

One query to fetch the authors, then **N** more — one per author — to fetch each author's books. A hundred authors is 101 round trips. It works on three test rows and collapses in production.

---

## Fix It: Eager Loading

### Django — `select_related` and `prefetch_related`

- `select_related` — for **forward** `ForeignKey`/`OneToOne`. Uses a SQL join, one query.
- `prefetch_related` — for **reverse** FKs and `ManyToMany`. Runs a second query and joins in Python.

```python
# One query for authors + one for all their books, joined in Python
for author in Author.objects.prefetch_related("books"):
    print(len(author.books.all()))

# Forward FK: a single join query
for book in Book.objects.select_related("author"):
    print(book.author.name)
```

### SQLAlchemy — `selectinload` and `joinedload`

```python
from sqlalchemy.orm import selectinload, joinedload

# selectinload: a 2nd query with WHERE author_id IN (...) — best for collections
authors = session.query(Author).options(selectinload(Author.books)).all()

# joinedload: a single LEFT JOIN — best for many-to-one / one-to-one
books = session.query(Book).options(joinedload(Book.author)).all()
```

A good rule of thumb: **`selectinload` for to-many collections** (avoids row multiplication), **`joinedload` for to-one relations**.

---

## Don't Fetch Whole Objects to Read a Few Columns

Hydrating full model instances to display two fields wastes memory and time. Select only what you need.

```python
# Django: .values() / .only() skip full model construction
Author.objects.values("name", "email")            # dicts, no model overhead
Author.objects.only("name")                        # deferred other columns

# SQLAlchemy: select specific columns
session.query(Author.name, Author.email).all()
```

For aggregates, push the work into the database rather than counting in Python:

```python
# Django: annotate a count in SQL — no N+1, no Python-side counting
from django.db.models import Count
Author.objects.annotate(num_books=Count("books"))
```

---

## Pagination Pitfalls

Two things bite here.

**1. Counting for pagination is a full second query.** `LIMIT/OFFSET` pagination runs a `COUNT(*)` to compute total pages, which can be expensive on large tables. For big datasets prefer **keyset (cursor) pagination** — `WHERE id > :last_seen ORDER BY id LIMIT n` — which stays fast regardless of how deep you page.

**2. Slicing after a to-many prefetch/join can multiply or mis-limit rows.** As in Java's JPA, a `LIMIT` applied on top of a collection join doesn't page the way you expect. In Django, `prefetch_related` sidesteps this by issuing a separate query; slice the *base* queryset (`Author.objects.all()[:20]`) and let the prefetch fetch relations for that page.

---

## Beware Implicit Lazy Loads Outside a Session

In SQLAlchemy, accessing a relationship after the `Session` is closed raises `DetachedInstanceError`. In Django, touching a related object in a template after the request's DB work is done can quietly re-query. The fix is the same in both: **load everything the caller needs while the session/request is open**, using eager loading — don't rely on lazy access leaking out of scope.

---

## Always Look at the Queries

The ORM hides the SQL; make it visible in development.

```python
# Django: inspect queries actually run
from django.db import connection
print(len(connection.queries))     # with DEBUG=True
# or use django-debug-toolbar to see counts and duplicates per request

# SQLAlchemy: echo generated SQL
engine = create_engine(url, echo=True)
```

Most ORM performance bugs are invisible in the Python and obvious in the query log. Watching the query *count* is how you catch an N+1 before your users do.

---

## Practical Checklist

| Trap | Django fix | SQLAlchemy fix |
|------|-----------|----------------|
| N+1 on forward FK | `select_related` | `joinedload` |
| N+1 on collection / M2M | `prefetch_related` | `selectinload` |
| Fetching whole objects to read | `.values()` / `.only()` | select columns |
| Counting in Python | `annotate(Count(...))` | `func.count()` |
| Deep `OFFSET` pagination | keyset pagination | keyset pagination |
| Lazy load out of scope | eager-load in request | eager-load in session |

---

## Final Thoughts

SQLAlchemy and the Django ORM are fast enough for almost anything — *if* you tell them how to load related data. Default to eager loading at the call sites that need relations, select only the columns you'll use, keep aggregation in the database, and watch the query count during development. The ORM's job is to hide SQL; your job is to make sure it isn't hiding an N+1.
