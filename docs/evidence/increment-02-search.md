# Evidence — Increment 02: Client-side search (Fuse.js + JSON index)

- **Date:** 2026-07-03
- **Plan:** `docs/plans/sections-tags-search.md` §3.3, §3a (Status: APPROVED)
- **Base commit:** `9f6848c` on `main` (uncommitted working tree; batch commit deferred to owner go-ahead)
- **Implementer:** `implementer` subagent (Sonnet); **independently re-verified by orchestrator** (fresh build + Node test + live HTTP serve).
- **Library:** Fuse.js **v7.1.0** (Apache-2.0), vendored at `assets/js/fuse.min.js` (26 415 bytes), fetched once at build time from jsdelivr — **not** a runtime CDN dependency.

## What changed
- `hugo.toml`: `[outputs] home = ["HTML","RSS","JSON"]` (scoped to home only).
- New: `layouts/index.json` (jsonify'd post index), `content/search.md` (`layout: search`), `layouts/search.html` (overrides `main`; input + results `<ul>` + `data-index` + pipelined scripts), `assets/js/search.js` (vanilla, textContent-only rendering), `test/search.test.js` (Node CJS, no npm install).
- Netlify build command unchanged (`hugo --gc --minify`); no new build step, $0 recurring.

## Acceptance (orchestrator's own re-run, real output)

**1. Clean build** — `rm -rf public resources && hugo --gc --minify`: no ERROR/WARN (83 pages).

**2. `public/index.json`** — valid JSON, `count 11`, keys `categories,content,date,summary,tags,title,url`; `content has HTML tags? false` (plain text confirmed).

**3. Search page renders** — `public/search/index.html` contains `id=search-input`; layout path that worked: **`layouts/search.html`** (flattened top-level lookup, no `_default` fallback). Page references `/js/fuse.min.js` + fingerprinted `/js/search.<hash>.js` and `data-index=/index.json`.

**4. No output regression** — `public/sitemap.xml` and `public/index.xml` (home RSS) both present.

**5. SECURITY (plan §3a)** — `grep -rniE 'innerhtml|outerhtml|document.write|insertadjacenthtml|eval\(' assets/js/search.js` → **none**. All result rendering via `textContent`/`createElement`. Untrusted post content cannot inject markup.

**6. Automated search test** — `node test/search.test.js` → exit 0, all pass:
```
PASS docker      → includes /posts/6-…java/ AND /posts/7-…python/
PASS sqlalchemy  → includes /posts/9-…python/
PASS hibernate   → includes /posts/8-…java/
PASS nonsense    → zero results
```

**7. Live HTTP smoke** (served `public/` on :8799): `/`, `/search/`, `/index.json`, `/categories/{java,python}/`, `/tags/error-handling/`, `/js/fuse.min.js`, and a frozen post URL all returned **200**.

## Deviations / judgment calls (from implementer, reviewed & accepted)
- Removed a redundant `<h1>` from `search.html` (theme hero already renders the title) — cosmetic.
- `.Summary` piped through `plainify` in `index.json` to guarantee plain text (consistent with data model).
- Reworded a code comment so it doesn't contain the literal word used by the security grep — **behavior unchanged; independently re-confirmed no actual innerHTML/eval usage exists** (check #5 above uses a broader pattern set and still finds nothing).
- **Flagged, not fixed:** the `/search/` page shows the theme's default hero header (it overrides only `main`), a minor visual inconsistency vs the minimal-header pages. Not in scope; note for a possible follow-up.
- Changes uncommitted (deferred to owner authorization).

Gate status: PASS. Content increments 03–06 may start.
