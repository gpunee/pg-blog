# Plan: Java/Python grouping, richer tags, client-side search, and 8 new posts

Status: IMPLEMENTED   <!-- approved by owner 2026-07-03; all 6 increments built + verified. Deploy pending separate owner go-ahead. -->

## 1. Goal & Context

**Problem (restated):** The blog is live and production-ready, but (a) its 11 posts are an
undifferentiated pile under one `/posts/` section with no easy way to browse "just Java" or
"just Python"; (b) tags exist but are thin (most posts carry a single `Java`/`Python` tag), so
topic discovery is weak; (c) there is no search; and (d) the planned discipline matrix is
incomplete — Software Architecture, Agentic workflows, Testing, and Database indexing have no
posts yet.

**Serves:** readers browsing the live site (`https://pg-blogs.netlify.app/`) who want to filter
by language or topic and search across posts; and the owner, who wants the content library
rounded out.

**Success criteria (measurable):**
- `/categories/java/` and `/categories/python/` list exactly the right posts; "Java" and
  "Python" appear in the site menu and link there.
- Every post carries language + discipline + specific-topic tags; `/tags/<topic>/` pages
  aggregate across languages (e.g. `/tags/error-handling/` shows both the Java and Python posts).
- A `/search/` page returns correct results client-side for a known query (e.g. "docker",
  "n+1") with **zero backend and zero recurring cost**.
- 8 new posts (4 Java+Python pairs) published: Architecture, Agentic workflows, Testing, DB
  indexing — matching the existing posts' depth, tone, and front-matter shape.
- `hugo --gc --minify` builds with no errors; existing post URLs are **unchanged** (no SEO loss).

**Non-goals / out of scope:**
- No physical move of posts into `/java/` `/python/` directories (user chose navigational
  grouping to preserve live URLs — so no `_redirects` needed).
- No header-embedded search box in this pass (dedicated `/search/` page keeps the theme
  override minimal); can be added later.
- No CSP change (deferred item from the prior plan stays deferred); but new JS is vendored
  locally so it does not add a third-party origin, keeping a future CSP simpler.
- No personalization of the About page (still owner's TODO).

## 2. Assumptions & Open Questions

**Assumptions (safe/reversible):**
- `categories` (a Hugo built-in taxonomy) is the right axis for language grouping; `tags` carry
  topic/tech. This keeps the two axes orthogonal and is theme-supported (ananke renders both and
  auto-generates `/categories/*` and `/tags/*` term pages). Reversible: taxonomy is front-matter.
- The 3 original posts (Why Java Matters, Cloud/Microservices, JVM Ecosystem) are Java-category.
- Post 1's current `categories: ["Technology"]` is replaced by `["Java"]` (Technology added no
  value as a browse axis). Reversible.
- Fuse.js is pinned and **vendored** into the repo (not loaded from a CDN) for supply-chain
  safety, offline builds, and CSP-friendliness.
- New posts are original prose written in this repo; the two Agentic posts describe the Anthropic
  SDKs and therefore follow the `claude-api` skill defaults (`claude-opus-4-8`, adaptive
  thinking, structured outputs) in their code samples — **no live API calls are made**.

**Open questions:** none blocking. (Search UX — page vs header box — was resolved to "page"
via the non-goals above; raise later if the owner wants the box.)

## 3. Design (WHAT / HOW / WHY)

### 3.1 Language grouping via the `categories` taxonomy (WHY not sections)
- **WHAT:** set `categories: ["Java"]` or `["Python"]` on every post; add menu entries
  `Java → /categories/java/` and `Python → /categories/python/`.
- **WHY:** the user explicitly chose to preserve existing `/posts/<slug>/` URLs (already indexed
  and in the live sitemap). Real Hugo sections would relocate every URL and force 301s. A
  taxonomy gives the same "browse by language" navigation with **zero URL churn**. Rejected
  alternative: `content/java/` + `content/python/` sections + `_redirects` — more moving parts,
  real SEO risk, no offsetting benefit for a small site (§3e: simplest thing that works).
- **Menu order (weights):** Home(1) · Java(2) · Python(3) · Posts(4) · About(5) · Search(6).

### 3.2 Tag enrichment (discoverability)
- **WHAT:** give each post a consistent tag set = `[language, discipline, …specific topics]`.
  ananke already includes `tags.html` in `single.html`, and Hugo auto-builds `/tags/<t>/`
  aggregation pages, so **no template work is needed** — this is pure front-matter.
- **Tag vocabulary (exact, per post):**

  | # | Post | categories | tags |
  |---|------|-----------|------|
  | 1 | Why Java Still Matters | Java | Java, JVM, Programming Languages, Backend, Software Engineering |
  | 2 | Java Cloud & Microservices | Java | Java, Cloud, Microservices, Kubernetes, Architecture |
  | 3 | JVM Ecosystem | Java | Java, JVM, Kotlin, Scala |
  | 4 | Error Handling (Java) | Java | Java, Error Handling, Exceptions, Software Engineering |
  | 5 | Error Handling (Python) | Python | Python, Error Handling, Exceptions, Software Engineering |
  | 6 | Docker (Java) | Java | Java, Docker, DevOps, Containers |
  | 7 | Docker (Python) | Python | Python, Docker, DevOps, Containers |
  | 8 | ORM/N+1 (Java) | Java | Java, Databases, ORM, JPA, Hibernate, Performance |
  | 9 | ORM/N+1 (Python) | Python | Python, Databases, ORM, SQLAlchemy, Django, Performance |
  | 10 | LLM Apps (Python) | Python | Python, AI, LLM, Anthropic |
  | 11 | LLM Apps (Java) | Java | Java, AI, LLM, Anthropic |
  | 12 | Architecture (Java) | Java | Java, Architecture, Software Design, SOLID, Software Engineering |
  | 13 | Architecture (Python) | Python | Python, Architecture, Software Design, SOLID, Software Engineering |
  | 14 | Agentic Workflows (Java) | Java | Java, AI, Agentic, LLM, Anthropic |
  | 15 | Agentic Workflows (Python) | Python | Python, AI, Agentic, LLM, Anthropic |
  | 16 | Testing (Java) | Java | Java, Testing, JUnit, Software Engineering |
  | 17 | Testing (Python) | Python | Python, Testing, pytest, Software Engineering |
  | 18 | DB Indexing (Java) | Java | Java, Databases, Indexing, Performance, SQL |
  | 19 | DB Indexing (Python) | Python | Python, Databases, Indexing, Performance, SQL |

  (Hugo normalizes tags to lowercase, hyphenated slugs for URLs, e.g. `Error Handling` →
  `/tags/error-handling/`; display text keeps the case above.)

### 3.3 Client-side search (Fuse.js + Hugo JSON index)
- **WHAT / HOW:**
  1. **Index:** add `JSON` to the home output formats and a `layouts/index.json` template that
     emits an array of `{title, url, date, summary, tags, categories, content}` for every
     regular post in `mainSections`. `content` is plain-text (`.Plain`) so the index isn't HTML.
  2. **Library:** vendor `fuse.js` (pinned, min build) into `assets/js/fuse.min.js` (or
     `static/js/`); committed to the repo — no CDN.
  3. **Search page:** `content/search.md` (a normal page at `/search/`) + a `layouts/search.html`
     template rendering a search `<input>` and an empty `<ul id="search-results">`.
  4. **Behavior:** `assets/js/search.js` fetches `/index.json` once, builds a Fuse index over
     `title/summary/tags/categories/content` (weighted: title > tags > content), reads the query
     from `?q=` and the input, and renders results. **Results are injected with `textContent`
     (never `innerHTML`) so post content cannot inject markup** (see §3a).
  5. **Menu:** add `Search → /search/`.
- **WHY Fuse.js over Pagefind/Algolia:** 19 posts is tiny; a JSON index + client fuzzy match is
  the simplest zero-cost, zero-new-build-tooling option (build command stays `hugo --gc
  --minify`). Pagefind would add a post-build dependency; Algolia adds cost + API keys +
  a third-party origin. (§3e: cheapest option that meets the real requirement.)
- **Data model — `index.json` element:**
  ```json
  { "title": "…", "url": "/posts/…/", "date": "2026-07-03",
    "summary": "…", "tags": ["Java","Docker"], "categories": ["Java"], "content": "plain text …" }
  ```

### 3.4 New posts (content)
- 8 posts, numbered 12–19, one Markdown file each in `content/posts/`, front matter per the
  table in §3.2, body matching the existing posts' structure (intro → problem → concrete
  Java/Python code with real output/SQL where relevant → pitfalls → takeaways).
- The two Agentic posts' code follows `claude-api` skill defaults (model `claude-opus-4-8`,
  `thinking: {type:"adaptive"}`, structured outputs / tool-use loop) and are **illustrative
  snippets only** — nothing executes, no keys, no network.

### 3.5 Non-functional
- **Performance:** `index.json` for 19 posts is a few hundred KB of text, fetched once on the
  `/search/` page only (not site-wide); Fuse min ~24 KB. Negligible.
- **Observability/cost:** no new infra, no new build step, $0 recurring. Search failures are
  client-side and degrade gracefully (empty results, console error).

### 3.6 As-built notes
> **As built (inc 01):** Final category split is **11 Java / 8 Python = 19** posts. Menu shipped exactly as planned (Home·Java·Python·Posts·About·Search). Post bodies untouched; all `/posts/<slug>/` URLs frozen and verified present after build.
> **As built (inc 02):** Fuse.js pinned to **v7.1.0** (Apache-2.0, 26 415 bytes), vendored at `assets/js/fuse.min.js`. The `/search/` page renders via top-level **`layouts/search.html`** (flattened lookup picked it up directly — no `_default/search.html` fallback needed). Home outputs = `["HTML","RSS","JSON"]`; sitemap + home RSS unaffected. `index.json` field: `plainify`'d `summary` + `.Plain` `content`. Search results rendered exclusively via `textContent`/`createElement` (XSS-safe, verified). An automated Node test (`test/search.test.js`, no npm install — `require`s the UMD Fuse build) guards the index.
> **As built (inc 04):** Agentic-post code was written from SDK patterns the orchestrator grounded out of the bundled `claude-api` skill docs (not model memory): Python `thinking={"type":"adaptive"}` + `messages.parse(output_format=…)` + `@beta_tool`/`tool_runner`; Java `ThinkingConfigAdaptive` + `BetaToolRunner` + `StructuredMessageCreateParams` + `Model.CLAUDE_OPUS_4_8`. No `budget_tokens`, no hardcoded keys (verified).
> **As built (inc 04, convention):** Cross-post links use Hugo's `{{< ref "…" >}}` shortcode (posts 14/15/18/19) — a **new** convention for this repo; resolves with no build warnings. First adopted here; reuse it for future cross-links.
> **As built (Phase 5, process):** The `require-increment-evidence.py` guard requires the literal marker **`Gate status: PASS`** in each evidence file — evidence files use that exact line. Evidence is one file per increment under `docs/evidence/increment-0N-<slug>.md`.
> **Known cosmetic gap (inc 02):** `/search/` shows the theme's default hero header (it overrides only `main`), unlike the minimal-header content pages. Cosmetic only; deferred.

### 3a. Security & Privacy
- **Authentication / Authorization** — N/A: static site, no accounts, no server. Search runs
  entirely in the browser against a public JSON file.
- **PII / sensitive data** — N/A: `index.json` contains only already-public post content; no user
  data is collected, stored, or transmitted by search (queries never leave the browser).
- **Secrets** — none. The Agentic posts show SDK usage but contain **no API keys** (illustrative;
  keys would come from env vars in real use, per the samples).
- **Input & trust boundaries** — the search query is untrusted *post content* rendered into the
  DOM. **Mitigation: results (titles/snippets) are inserted via `textContent`/DOM node creation,
  never `innerHTML`**, eliminating stored-XSS-via-post-content and query-reflection XSS. The `?q=`
  param is read as a string and used only as a Fuse query, never `eval`'d or written as HTML.
- **Supply chain** — Fuse.js is pinned to a specific version and vendored into the repo (a
  reviewable committed file), not pulled from a CDN at runtime; this also avoids adding a
  third-party script origin, keeping a future CSP tractable.
- **Threats & mitigations** — (1) XSS via malicious post content → textContent rendering;
  (2) supply-chain via CDN → vendored pinned lib; (3) index bloat/DoS → tiny static file, N/A at
  this scale.

## 4. Implementation Steps (iterative increments)

Each increment leaves the site building and deployable. Content increments (3–6) are lighter-gated
(build clean + acceptance grep + review) since a blog has no unit-test surface for prose; the
search increment (2) carries a real automated test.

- **Increment 01 — Grouping + tags (config + front matter).** Edit `hugo.toml` menu (add
  Java/Python/Search, reweight); set `categories` + enriched `tags` on all 11 existing posts per
  §3.2. Scaffolding-ish but touches config semantics → **Sonnet** (front-matter correctness
  matters). *Acceptance:* build clean; generated `public/categories/java/index.html` and
  `.../python/index.html` list the correct post sets; `public/tags/error-handling/` aggregates
  both language posts; menu shows Java/Python.
- **Increment 02 — Search feature.** Add `[outputs]` home JSON + `layouts/index.json`; vendor
  `fuse.min.js`; add `content/search.md`, `layouts/search.html`, `assets/js/search.js`; add
  Search menu item. **Sonnet** (logic). *Acceptance:* `public/index.json` is valid JSON with one
  entry per post and plain-text `content`; an automated Node test loads `index.json`+Fuse and
  asserts queries ("docker", "n+1", "sqlalchemy") return the expected posts; `/search/` renders
  the box locally; results render via `textContent`.
- **Increment 03 — Architecture pair (posts 12–13).** Two Markdown posts. **Sonnet.**
  *Acceptance:* build clean; both appear under `/categories/{java,python}/` and `/tags/architecture/`;
  code blocks compile-sane on read-through.
- **Increment 04 — Agentic pair (posts 14–15).** Two posts; code follows `claude-api` defaults.
  **Sonnet.** *Acceptance:* as inc 03, plus samples use `claude-opus-4-8` + adaptive thinking.
- **Increment 05 — Testing pair (posts 16–17).** **Sonnet.** *Acceptance:* as inc 03.
- **Increment 06 — DB indexing pair (posts 18–19).** **Sonnet.** *Acceptance:* as inc 03; SQL/EXPLAIN
  snippets are accurate.

Increments 03–06 are independent and could be reordered or parallelized; 01 and 02 are
independent of each other but both should precede the final verify.

### 4.0 Context-handoff mapping
- **Inc 01:** §3.1 + §3.2 (menu table + tag table) + current `hugo.toml` + list of 11 post files.
  Invariant: do not change post `title`/`date`/`slug` (URLs are frozen); front-matter edits only.
- **Inc 02:** §3.3 + §3a (textContent rule, vendored lib) + `netlify.toml` (build command must
  stay `hugo --gc --minify`). Invariant: no CDN; no new build step; textContent not innerHTML.
- **Inc 03–06:** §3.4 + the relevant row(s) of §3.2's table + one existing same-topic post as a
  style exemplar (implementer reads it). Invariant: front-matter shape matches existing posts;
  Agentic code uses `claude-api` defaults; no secrets.

### 4.1 Per-increment gate
- Build passes: `hugo --gc --minify` with no ERROR/WARN regressions.
- Acceptance demonstrated against generated `public/` (captured grep/HTTP output, not asserted).
- Inc 02 additionally: the Node search test is green (happy path + a no-match query).
- Evidence file `docs/evidence/increment-<NN>-<slug>.md` written before the next increment starts.

## 5. Testing & Verification
- **Grouping/tags:** grep generated `public/categories/*/index.html` and `public/tags/*/index.html`
  for expected post titles; confirm counts (Java vs Python) match the table.
- **Search:** automated Node test (`fuse` over `public/index.json`) asserting known queries →
  expected URLs, plus a query with no matches → empty. Manual: `hugo server`, load `/search/?q=docker`.
- **Content:** clean build; each new post reachable, categorized, tagged; read-through review of
  code samples for correctness (the §5 bar the prior posts were held to — e.g. no cross-language
  syntax leaks like the earlier Kotlin-in-Java bug).
- **Regression:** existing 11 URLs still resolve unchanged; sitemap still lists all posts (now 19).
- **Full verify (Phase 5):** clean build, paired check that search works in a served build, and a
  live re-verify after deploy **only if the user authorizes a push** (this plan stops at merge —
  deploy is a separate go-ahead).

## 6. Risks & Rollback
- **Risk:** changing `categories` reshapes `/categories/*` term pages. *Mitigation:* additive;
  old `/posts/` URLs untouched. *Rollback:* revert front-matter.
- **Risk:** `index.json` output format misconfig could alter other outputs. *Mitigation:* scope
  the `[outputs]` change to `home` only; verify RSS/sitemap still emit. *Rollback:* remove JSON
  from outputs + delete search files.
- **Risk:** vendored Fuse.js version drift/vuln. *Mitigation:* pin + record version in evidence;
  it's a leaf dep, easy to bump. *Rollback:* delete `search.js` include.
- **Risk:** a new post ships a code error (as the earlier Kotlin/Java slip). *Mitigation:*
  read-through review gate per §5; keep samples minimal and idiomatic.

## 7. Impact
- **Edited:** `hugo.toml` (menu + `[outputs]`), all 11 existing post front matters (categories +
  tags; **bodies untouched**).
- **New:** `layouts/index.json`, `layouts/search.html`, `content/search.md`,
  `assets/js/fuse.min.js`, `assets/js/search.js`, 8 post Markdown files (`content/posts/12…19`),
  evidence files under `docs/evidence/`.
- **Migrations:** none. **Breaking changes:** none (URLs frozen). **Docs:** this plan; evidence.
- **Deploy:** merge to `main` triggers Netlify auto-deploy — **only on explicit user go-ahead**,
  same as before.
