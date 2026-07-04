# Plan: Syndicate posts to Dev.to (automated) + Medium & social (assisted)

Status: IMPLEMENTED   <!-- built + verified 2026-07-04; live draft smoke pending in Phase 5 -->

## 1. Goal & Context

**Problem (restated):** The 19 posts live only on `pg-blogs.netlify.app`. The owner wants them
**accessible on established blogging platforms** to reach those audiences — without losing the
SEO of the canonical site.

**Approach — POSSE (Publish on Own Site, Syndicate Elsewhere):** the Netlify site stays the
**canonical original**; every syndicated copy declares `rel=canonical` back to it, so search
engines credit the owner's domain and there is no duplicate-content penalty.

**Honest scope of "automation":** only **Dev.to** has a usable write API, so only Dev.to is
scripted. **Medium** has no current write API (its integration tokens were deprecated) — handled
via its **Import tool** with a generated checklist. **LinkedIn / Reddit / Hacker News** are
*distribution* (link + teaser), not hosted copies — handled with generated teaser snippets.

**Success criteria:**
- One command publishes/updates all (or selected) posts to Dev.to as **drafts by default**, each
  with the correct `canonical_url`, cleaned Markdown (no Hugo shortcodes), and ≤4 valid tags.
- Re-running does **not** create duplicates (idempotent create-or-update via a tracked state map).
- A `medium-import-list.md` with every canonical URL + step-by-step import instructions.
- Per-post teaser snippets for LinkedIn/Reddit/HN (title + hook + canonical link).
- Nothing publishes live without an explicit `--publish` flag; a `--dry-run` shows exactly what
  would be sent without calling any API.

**Non-goals:** Medium/LinkedIn/Reddit/HN API automation (no reliable API / against ToS);
auto-posting live by default; changing any existing blog content or the Hugo site.

## 2. Assumptions & Open Questions

**Assumptions (safe/reversible):**
- **Stack = Python** (per CLAUDE.md §5: scripting → Python). Standalone tool under
  `scripts/syndicate/`; its own gitignored venv; deps pinned in `requirements.txt`
  (`python-frontmatter`, `requests`). Does not touch the Hugo build.
- Canonical URL for a post file `NN-slug.md` is `https://pg-blogs.netlify.app/posts/NN-slug/`
  (matches the live permalink scheme, verified).
- Dev.to is the only scripted target; free API; the owner will create a Dev.to account + API key.
- Default behavior is **draft + dry-run-friendly** because publishing is outward-facing (§3a).

**Open questions:** none blocking. Defaults (draft-first, all-posts, no cover image) are stated in
§3 and are reversible via flags; the owner can override at run time or ask to change the default.

## 3. Design (WHAT / HOW / WHY)

### 3.1 Module layout (`scripts/syndicate/`)
- `posts.py` — load `content/posts/*.md`, parse front matter, expose a `Post` dataclass
  (`slug, title, description, tags, categories, canonical_url, body_markdown`).
- `transform.py` — pure functions that turn Hugo Markdown into platform-portable Markdown:
  - **Rewrite cross-links:** `[text]({{< ref "NN-x.md" >}})` → `[text](https://pg-blogs.netlify.app/posts/NN-x/)`. (Grounded: this is the only shortcode in use.)
  - Strip any other `{{< … >}}` / `{{% … %}}` shortcodes defensively (log if found).
  - Leave fenced code blocks untouched.
- `tags.py` — map our tags → Dev.to-valid tags (lowercase, alphanumeric, **max 4**), via an alias
  table + priority order (language → discipline → specific). Alias examples:
  `Software Engineering→softwareengineering`, `Error Handling→errorhandling`, `AI→ai`,
  `LLM→llm`, `Databases→database`, `Indexing→database`, `Docker→docker`, `DevOps→devops`,
  `Testing→testing`, `Architecture→architecture`, `Performance→performance`, `SOLID→architecture`,
  `Anthropic→ai`, `Agentic→ai`. Dedupe, then keep the first 4 by priority.
- `devto.py` — thin Dev.to API client: `list_my_articles()`, `create(article)`, `update(id, article)`.
  Base `https://dev.to/api`, header `api-key: $DEVTO_API_KEY`. Small retry/backoff on 429/5xx.
- `state.json` — `{ slug: devto_article_id }`, committed so idempotency survives across machines
  (contains only public article IDs, no secrets).
- `cli.py` — `python -m syndicate <command> [flags]`:
  - `devto` — publish/update to Dev.to. Flags: `--dry-run` (print payloads, no calls),
    `--publish` (set `published:true`; **omitted ⇒ draft**), `--only NN[,NN]` (subset),
    `--all` (default). Reconcile against `state.json` + `list_my_articles()` → create or update.
  - `medium` — write `syndication/medium-import-list.md` (all canonical URLs + import steps).
  - `teasers` — write `syndication/teasers/<slug>.md` (title, 2-line hook from description,
    canonical link, suggested subreddits/tags) for LinkedIn/Reddit/HN.

### 3.2 Idempotency (WHY a state map)
Dev.to has no "upsert". We track `slug → article_id` in `state.json`; on run we also fetch the
account's existing articles and match by `canonical_url` as a fallback (so a lost state file
won't double-post). New → `create`; known → `update`. This makes re-runs safe as posts change.

### 3.3 Data model — Dev.to article payload
```json
{ "article": {
    "title": "...",
    "body_markdown": "...cleaned...",
    "published": false,
    "canonical_url": "https://pg-blogs.netlify.app/posts/NN-slug/",
    "description": "...",
    "tags": ["java","architecture","softwareengineering","solid"]
} }
```

### 3.4 Non-functional
- **Cost:** $0 (Dev.to API free; no infra). **Latency:** a handful of REST calls; a ~1s inter-call
  delay to respect rate limits. **Observability:** the CLI prints a per-post action line
  (create/update/skip/draft) and a summary.

### 3.5 As-built notes
> **As built (inc 01):** Modules `posts.py`/`transform.py`/`tags.py` + tests under `scripts/syndicate/`. Tag mapping maps in front-matter order → dedupe → first 4; verified all 19 posts yield ≤4 alphanumeric tags with no leftover shortcodes.
> **As built (inc 02):** `DevToClient` reads the key from `DEVTO_API_KEY` env only (no `.env` parsing — pure `os.environ`); draft is default, `--publish` + TTY prompt/`--yes` to go live; `--dry-run` makes zero network calls; idempotency = `state.json` id → canonical-match fallback → create. **Invocation:** run via `scripts/syndicate/run.sh <cmd>` from anywhere, or `python -m syndicate` with cwd=`scripts/`.
> **As built (inc 03):** Generated artifacts land at **`scripts/syndication/`** (cwd-independent, anchored to the package), not repo-root `syndication/` as §7 implied. Output is regenerable and left **untracked**. `run.sh` wrapper + `README.md` added.
> **As built (Phase 5):** Live Dev.to run performed **by the owner** with their token supplied at runtime as an env var (never written to any file); the orchestrator did not run it (classifier blocked key inlining). `state.json` now maps all 19 slugs → article IDs (`4067810`–`4067830`), evidencing 19 successful creates. Draft-vs-published status is owner-verified on the Dev.to dashboard, not by the orchestrator. See `docs/evidence/increment-syndication-04-live-publish.md`.

### 3a. Security & Privacy
- **Authentication/Authorization** — the Dev.to **API key is a secret**: read only from
  `DEVTO_API_KEY` env var (or a gitignored `scripts/syndicate/.env`), **never** committed,
  **never** logged (the client redacts it). `.gitignore` gets `.env` + `venv/`.
- **PII/sensitive data** — none; posts are already public. `state.json` stores only public
  Dev.to article IDs.
- **Outward-facing action (the core risk)** — publishing is public and hard to fully undo.
  Mitigations: **draft is the default** (`published:false`); `--publish` required to go live;
  `--dry-run` prints the exact payload with no network call; the CLI prints a confirmation
  summary before any live `--publish` run.
- **Input & trust boundaries** — Dev.to API responses parsed defensively; non-2xx surfaces a
  clear error and aborts that post without corrupting `state.json` (write state only after a
  confirmed 2xx).
- **Threats** — (1) leaked key → env/secret only, redacted logs, `.env` gitignored;
  (2) accidental mass live-publish → draft default + explicit `--publish` + dry-run;
  (3) duplicate posts → idempotent state + canonical-match fallback.

## 4. Implementation Steps (increments)

- **Increment 01 — Core transform library (no network).** `posts.py`, `transform.py`, `tags.py`
  + `requirements.txt` + venv. **Sonnet.** *Acceptance:* unit tests (pytest) green — front-matter
  parse, cross-link rewrite (happy + a post with no links), shortcode strip, tag mapping (incl.
  the >4-tags truncation and space/special-char cases), canonical computation. Run against the
  real 19 posts to confirm no crashes and no leftover `{{<` in output.
- **Increment 02 — Dev.to publisher (network, gated).** `devto.py`, `state.json`, `cli.py devto`.
  **Sonnet.** *Acceptance:* `--dry-run` over all 19 prints valid payloads (canonical + ≤4 tags +
  clean body), makes **zero** network calls (tests assert the HTTP layer is untouched in dry-run);
  create/update idempotency unit-tested with a **mocked** Dev.to API (no live calls in tests);
  key-redaction test. No live publish in the gate.
- **Increment 03 — Medium list + social teasers (no network).** `cli.py medium` + `cli.py teasers`.
  **Sonnet.** *Acceptance:* generates `syndication/medium-import-list.md` (19 canonical URLs +
  steps) and `syndication/teasers/*.md` (19 files); unit test asserts each teaser has title +
  canonical link; snapshot one file.

### 4.0 Context-handoff mapping
- **Inc 01:** §3.1 (posts/transform/tags) + §3.3 tag rules + the grounded cross-link form
  `[text]({{< ref "NN-x.md" >}})` + canonical scheme. Invariant: pure functions, no network, no
  writes to `content/`.
- **Inc 02:** §3.1 (`devto.py`,`cli.py`) + §3.2 idempotency + §3a (secret handling, draft default,
  dry-run). Invariant: draft unless `--publish`; state written only after 2xx; key never logged.
- **Inc 03:** §3.1 (`medium`/`teasers`) + canonical scheme. Invariant: pure generation into
  `syndication/`, no network.

### 4.1 Per-increment gate
- pytest green (happy + failure modes); `--publish`-gated behavior covered by paired tests
  (dry-run makes no calls / mocked publish makes the expected call).
- Acceptance demonstrated against the real 19 posts (captured output).
- Evidence `docs/evidence/increment-syndication-<NN>.md` with `Gate status: PASS` before next.

## 5. Testing & Verification
- Unit tests with mocked HTTP for anything touching Dev.to — **no live API calls in the test
  suite.** A single, human-initiated live smoke (`--only 1 --publish` to a real Dev.to draft/account)
  is done **only with the owner present and authorizing**, in Phase 5, and is not part of CI.
- Verify no `{{<`/`{{%` remains in any transformed body; every payload has a canonical + ≤4 tags.

## 6. Risks & Rollback
- **Accidental live publish** → draft default + `--publish` gate + dry-run; rollback: unpublish/
  delete on Dev.to, clear the slug from `state.json`.
- **Key leak** → env/secret only, redacted logs, `.env` gitignored; rollback: revoke key on Dev.to.
- **Duplicate posts** → idempotent state + canonical-match fallback.
- **Markdown quirks on Dev.to** (liquid tags, image paths) → transform strips shortcodes; images
  currently referenced by absolute site paths remain absolute (resolve to the live site).

## 7. Impact
- **New:** `scripts/syndicate/**` (Python tool), `scripts/syndicate/requirements.txt`,
  `scripts/syndicate/state.json`, `syndication/**` (generated lists/teasers), evidence files,
  `.gitignore` additions (`scripts/syndicate/venv/`, `scripts/syndicate/.env`).
- **Unchanged:** all `content/`, `hugo.toml`, layouts, the Hugo build and live site.
- **External:** creates/updates **drafts** on the owner's Dev.to account only when run with a key;
  going live requires `--publish`. Medium/social steps are manual by design.
