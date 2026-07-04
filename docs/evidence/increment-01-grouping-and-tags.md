# Evidence — Increment 01: Java/Python grouping + enriched tags + menu

- **Date:** 2026-07-03
- **Plan:** `docs/plans/sections-tags-search.md` §3.1, §3.2 (Status: APPROVED)
- **Base commit:** `9f6848c` on `main` (changes uncommitted in working tree; batch commit deferred to Phase 5 / owner go-ahead)
- **Implementer:** `implementer` subagent (Sonnet); **independently re-verified by orchestrator** (fresh `rm -rf public resources && hugo --gc --minify`).

## What changed
- `categories` + enriched `tags` set on all 11 posts (front matter only — post **bodies byte-for-byte unchanged**; `title`/`date`/`description`/slug untouched, so all live `/posts/<slug>/` URLs are frozen).
- `hugo.toml` `[menu.main]` replaced: Home(1) · Java(2, `/categories/java/`) · Python(3, `/categories/python/`) · Posts(4) · About(5) · Search(6, `/search/` — page arrives in inc 02).

## Acceptance (orchestrator's own re-run, real output)

**1. Clean build**
```
$ rm -rf public resources && hugo --gc --minify
hugo v0.154.2+extended+withdeploy darwin/arm64
 Pages 81 | Aliases 30 | Total in 215 ms
```
No ERROR / no WARN.

**2. Category split (from front matter) — 7 Java / 4 Python, exactly as planned**
Java: posts 1,2,3,4,6,8,11 · Python: posts 5,7,9,10.

**3. Category pages render the right posts (fixed-string title grep)**
```
              java  python   title
                1     0      Why Java Still Matters
                1     0      Building Reliable LLM Applications in Java
                0     1      Error Handling Best Practices in Python
                0     1      Building Reliable LLM Applications in Python
/posts/ permalinks: java page = 15, python page = 9  (≈2 refs × 7 and × 4 posts)
```
Each title appears only in its own language's category page.

**4. Cross-language tag aggregation**
```
$ grep '…' public/tags/error-handling/index.html
posts/4-error-handling-best-practices-in-java/
posts/5-error-handling-best-practices-in-python/
```
`/tags/error-handling/` aggregates BOTH languages — discoverability goal met.

**5. Menu order** (labels grepped from `public/index.html`): `Home Java Python Posts About Search` ✓

**6. URL freeze regression** — `public/posts/5-error-handling-best-practices-in-python/index.html` present ✓

## Deviations
- None from the plan. `/search/` menu item intentionally 404s until Increment 02 (documented in plan §4, acceptable mid-increment).
- Changes not yet committed to git (kept in working tree); commit/push occurs only on explicit owner authorization per the project's deploy discipline.

Gate status: PASS. Increment 02 may start.
