# Evidence — Increment 05: Testing best-practices posts (Java + Python)

- **Date:** 2026-07-03 · **Plan:** §3.4 + §3.2 rows 16–17 (APPROVED) · **Base:** `9f6848c` (uncommitted)
- **Implementer:** Sonnet subagent; **orchestrator independently re-ran build + code checks.**

## Created
- `content/posts/16-testing-best-practices-in-java.md` — test pyramid, behavior-not-implementation, JUnit 5 `@ParameterizedTest`/`assertThrows`, AAA, Mockito + "don't mock what you don't own"/over-mocking anti-pattern, `Clock` injection for determinism, coverage-as-signal, takeaways.
- `content/posts/17-testing-best-practices-in-python.md` — parallel in pytest: fixtures, `@pytest.mark.parametrize`, `pytest.raises`, `monkeypatch`/`Mock(spec=...)`, injected clock/`time.sleep`, coverage-as-signal, takeaways.

## Acceptance (orchestrator's own run)
- Build **clean**, 17 posts.
- Post 16 → `categories/java/`, post 17 → `categories/python/`; both aggregate at `tags/testing/`; both post dirs exist.
- **Code correctness (orchestrator):** Java fences — no cross-language leaks (`def`/`val`/`fun`/`elif` absent); all **9 Python blocks compile** clean.

## Deviations
None. Front-matter/tags/categories/field-order match reference posts. Uncommitted (owner authorization pending).

Gate status: PASS. Increment 06 may start.
