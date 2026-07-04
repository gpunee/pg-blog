# Evidence — Increment 03: Architecture posts (Java + Python)

- **Date:** 2026-07-03 · **Plan:** §3.4 + §3.2 rows 12–13 (APPROVED) · **Base:** `9f6848c` (uncommitted)
- **Implementer:** Sonnet subagent; **orchestrator independently re-ran build + code checks.**

## Created
- `content/posts/12-designing-for-change-in-java.md` — coupling/cohesion, DIP via `PaymentGateway` interface + adapter (constructor injection), ports-and-adapters `OrderProcessor`/`OrderRepository` with in-memory test adapter, validating `Money` record + sealed `OrderStatus` (pattern-matching switch), "when not to abstract", takeaways.
- `content/posts/13-designing-for-change-in-python.md` — parallel using `typing.Protocol` + `abc.ABC`, framework-free DI, same ports-and-adapters example with `InMemoryOrderRepository`, frozen `__post_init__`-validated `Money` dataclass, `Enum` `OrderStatus` with guarded transition, same "when not to", takeaways.

## Acceptance (orchestrator's own run)
- `rm -rf public resources && hugo --gc --minify` → **build clean**, 13 posts.
- Post 12 in `public/categories/java/`, post 13 in `public/categories/python/` (1 each).
- Both aggregate at `public/tags/architecture/`.
- `public/posts/12-…/` and `public/posts/13-…/` exist; both in sitemap.
- **Code correctness (orchestrator-verified):** Java fences use records/sealed/pattern-switch/`var`/`Optional` — **no Kotlin leaks** (`val`/`fun`/`in 1..` absent); all **12 Python blocks compile** (`compile(...,'exec')` clean).

## Deviations
None. Front-matter/tags/categories match §3.2 exactly. Uncommitted (owner authorization pending).

Gate status: PASS. Increment 04 may start.
