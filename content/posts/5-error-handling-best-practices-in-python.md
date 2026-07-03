---
title: "Error Handling Best Practices in Python"
date: 2026-07-03
description: "EAFP over LGBYL, catching narrow exceptions, exception chaining, custom exception hierarchies, context managers, and when to return a result instead of raising in Python."
tags:
  - Python
  - Software Engineering
  - Error Handling
  - Best Practices
  - Exceptions
categories:
  - Software Engineering
draft: false
---

## Introduction

Python's error handling reads deceptively simply — `try`, `except`, done. But the difference between code that fails clearly and code that fails mysteriously comes down to a handful of habits: catching the *right* exception, preserving the original cause, and knowing when *not* to raise at all.

This post covers the practices that keep Python failures debuggable in production.

---

## Prefer EAFP over Look-Before-You-Leap

Python idiom favors **EAFP** — "Easier to Ask Forgiveness than Permission." Rather than checking whether an operation will succeed, attempt it and handle the failure:

```python
# LBYL — racy, verbose, and easy to get subtly wrong
if "user" in data and data["user"] is not None:
    name = data["user"].name

# EAFP — Pythonic, and free of the time-of-check/time-of-use gap
try:
    name = data["user"].name
except (KeyError, AttributeError):
    name = "unknown"
```

Beyond being idiomatic, EAFP avoids the race window between the check and the use — the check can pass and then the state change before you act on it.

---

## Catch Narrow Exceptions, Never Bare `except`

The most damaging habit in Python error handling is the bare `except:` (or `except Exception:` used as a catch-all). It swallows everything — including `KeyboardInterrupt`, `SystemExit`, and the `NameError` from your own typo.

```python
# DON'T: hides bugs and can't be interrupted with Ctrl-C
try:
    result = process(payload)
except:
    result = None

# DO: name exactly what you expect and can handle
try:
    result = process(payload)
except ValueError as exc:
    logger.warning("invalid payload, skipping: %s", exc)
    result = None
```

Catch the *specific* exceptions a block can actually recover from. Anything else should propagate — an unexpected exception is information, and hiding it turns a clear crash into a silent wrong answer.

---

## Preserve the Cause with `raise ... from`

When you catch a low-level exception and raise a domain-specific one, chain them explicitly. Python then prints both tracebacks with a clear "The above exception was the direct cause of the following":

```python
class OrderError(Exception):
    """Domain-level failure while processing an order."""

def place_order(order_id: int) -> Order:
    try:
        return repository.load(order_id)
    except DatabaseError as exc:
        raise OrderError(f"could not load order {order_id}") from exc
```

The `from exc` is what keeps the root cause visible. Dropping it (a bare `raise OrderError(...)`) throws away the original traceback — the exact thing you need at 3 a.m.

---

## Build a Small Exception Hierarchy

Define your own exception types, rooted at a single base, so callers can catch at whatever granularity they need:

```python
class AppError(Exception):
    """Base for all application errors."""

class ValidationError(AppError):
    """Input failed validation."""

class ExternalServiceError(AppError):
    """A downstream dependency failed."""
```

Now a caller can `except ValidationError` for precise handling, or `except AppError` to catch anything the application deliberately raises — while still letting truly unexpected exceptions (a `KeyError` from a bug) surface loudly.

---

## Don't Raise for Expected Outcomes — Return Instead

Exceptions are for the *exceptional*. When a "failure" is a routine, expected result — a lookup that finds nothing, validation of user input — returning a value is often clearer and faster than raising:

```python
from dataclasses import dataclass

@dataclass
class ParseResult:
    value: int | None
    error: str | None

def parse_port(raw: str) -> ParseResult:
    try:
        port = int(raw)
    except ValueError:
        return ParseResult(None, f"not a number: {raw!r}")
    if not 1 <= port <= 65535:
        return ParseResult(None, f"port out of range: {port}")
    return ParseResult(port, None)
```

Returning `None` for a not-found lookup, or a small result object for parsing, keeps the happy path free of `try/except` noise and makes the failure a normal branch instead of hidden control flow.

---

## Clean Up with Context Managers

Any resource — files, connections, locks — should be managed with a `with` block so cleanup happens even when an exception is raised mid-operation:

```python
with open(path) as f, db.connection() as conn:
    conn.execute(f.read())
# file and connection both closed, even on exception
```

For your own resources, implement `__enter__`/`__exit__` or use `contextlib.contextmanager`. This replaces fragile `try/finally` and guarantees the cleanup runs.

---

## Log with Context, Not Just the Message

When you do log an exception, use `logger.exception` (inside an `except`) or pass `exc_info=True` so the full traceback is captured, and include the *entity* you were working on:

```python
except ExternalServiceError:
    logger.exception("payment failed for order_id=%s", order_id)
    raise
```

`logger.exception` records the stack trace automatically — far more useful than `logger.error(str(exc))`, which throws the traceback away.

---

## Practical Checklist

| Practice | Why it matters |
|----------|----------------|
| Prefer EAFP over LBYL | Idiomatic, avoids check/use races |
| Catch narrow, specific exceptions | Bugs surface instead of hiding |
| Never use bare `except:` | Ctrl-C and real bugs stay visible |
| Chain with `raise ... from exc` | Preserves the root traceback |
| Define an app exception hierarchy | Callers catch at the right level |
| Return a result for expected failures | Exceptions stay exceptional |
| Use `with` / context managers | Cleanup runs even on exception |
| Log with `logger.exception` | Full traceback, real context |

---

## Final Thoughts

Python makes it easy to write error handling that *looks* fine and silently loses information. The fix is discipline: catch only what you can handle, chain what you re-raise, return instead of raise for expected outcomes, and let context managers own cleanup.

The goal is not to prevent every failure — it is to make sure that when something fails, the traceback tells you exactly what, where, and why.
