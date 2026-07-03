# Plan: Production-Readiness Upgrades for PG Blog

Status: IMPLEMENTED   <!-- approved & built 2026-07-03; evidence in docs/evidence/increment-01-08-production-readiness.md -->

<!-- AS-BUILT NOTES (2026-07-03):
  - Increments 6 (GA4 ID) and 7 (giscus IDs) config was folded into the single Increment-2
    `hugo.toml` edit (one file); their layout work (comments partial + single.html) stayed in
    Increment 7. GA/giscus proven via paired production/development ON-OFF builds.
  - Increment 2 needed no custom `robots.txt` template: ananke's template already emits the
    sitemap in production and disallows non-production — enableRobotsTXT=true was sufficient.
  - Increment 3: no immutable long-cache on theme CSS (ananke does not fingerprint main.min.css);
    no CSP yet (needs giscus/GitHub/GA allowlist) — deferred as report-only follow-up.
  - Evidence consolidated into one file with per-increment sections (disclosed deviation).
  - Assets generated with Pillow (installed into a scratchpad venv; not a project dependency).
  - Owner bio in content/about.md left as an intentional placeholder (not fabricated). -->


## 1. Goal & Context

**Problem:** The blog (Hugo + `ananke` theme, deployed on Netlify) has good bones but is not production-ready. An architecture review found one showstopper (`baseURL = https://example.org/` poisons every canonical/sitemap/OG/RSS URL), committed build artifacts with no `.gitignore`, and a set of SEO / credibility / hardening gaps.

**Serves:** Public readers of `https://pg-blogs.netlify.app/` and the site owner (discoverability, analytics, engagement).

**Success criteria (measurable):**
- All generated URLs (canonical, `og:url`, sitemap `<loc>`, RSS) resolve to `https://pg-blogs.netlify.app/`.
- `robots.txt` served, referencing the sitemap.
- Homepage `<meta name="description">` non-empty; every share has an `og:image`.
- `git status` clean of build output; `.gitignore` present.
- Favicon served; About page reachable from nav.
- GA4 loads; giscus comments render on posts.
- `hugo --gc --minify` builds with **zero warnings**.

**Non-goals:** Custom domain/DNS (staying on `*.netlify.app` for now); redesign/re-theming; new blog content; migration off Hugo/Netlify.

## 2. Assumptions & Open Questions

**Assumptions (safe/reversible):**
- Netlify site name is `pg-blogs`; production URL is `https://pg-blogs.netlify.app/`.
- Netlify auto-initializes the `themes/ananke` git submodule on build (default behavior).
- Python 3 + Pillow can generate favicon/OG raster assets; if unavailable, fall back to an SVG favicon + document the OG-image limitation.

**Open questions (BLOCKING for two increments only):**
- **GA4 Measurement ID** (`G-XXXXXXXXXX`) — required for Increment 6. Cannot be invented.
- **giscus setup** (Increment 7) — requires the owner to, on `github.com/gpunee/pg-blog`: (1) make the repo public, (2) enable **Discussions**, (3) install the **giscus GitHub App**, then (4) provide from giscus.app: `data-repo-id`, `data-category`, `data-category-id`. Cannot be generated on our side.

Non-blocking: Increments 1–5, 8 can proceed immediately on approval; 6 and 7 are wired with config placeholders and completed once the values arrive.

## 3. Design (WHAT / HOW / WHY)

**Approach:** Small, isolated, config-first changes. No content is touched. Theme is left untouched (git submodule); all customization lives in the project via `hugo.toml`, `static/`, `content/`, and minimal `layouts/` overrides — the Hugo-idiomatic way to customize a themed site without forking it.

**Key decisions & rationale:**
- **Config stays in a single `hugo.toml`** (not split into `config/_default/`). Rationale: the config is still small; a split adds structure without payoff yet. Rejected the split as premature.
- **giscus via a `layouts/` override**, because ananke ships native Disqus/Commento but not giscus. We add `layouts/_partials/comments.html` (the giscus embed) and override `layouts/single.html` (copied from the theme) to include it after the article. Trade-off: the copied `single.html` won't auto-track future theme changes to that one file — documented, and acceptable for a stable theme. Rejected Disqus (ads/privacy) per owner choice; giscus stores comments in GitHub Discussions (no ads, owner-controlled).
- **GA4 via Hugo's built-in `google_analytics` internal template** (ananke already includes it in `baseof.html`) — just set the `googleAnalytics` config key. No custom code. Simplest correct option.
- **Favicon via a `head-additions.html` override** referencing an SVG (+ PNG fallback), rather than ananke's `.ico`-only `site-favicon.html`, since we can't generate `.ico` without image tooling. SVG favicons are broadly supported by current browsers.
- **Security + cache headers in `netlify.toml`** (`[[headers]]`), not in-page. Static site, but headers still harden against clickjacking/MIME-sniffing and enable long-cache of fingerprinted assets.

**Interfaces / contracts:** None external. Config keys added to `hugo.toml`; files added under `static/`, `content/`, `layouts/`.

**Non-functional:** Performance improves (minify + long-cache headers). Cost unchanged (Netlify free tier; GA4 free; giscus free). Observability added (GA4). Reversible: every change is a file add/edit under version control.

### 3a. Security & Privacy (mandatory)

- **Authentication / Authorization** — N/A: static public blog, no accounts, no server, no protected resources. giscus auth is delegated entirely to GitHub (readers sign in with GitHub to comment; we store no credentials).
- **PII / sensitive data** — GA4 collects visitor analytics (IP-derived geo, device, behavior) = personal data under GDPR/UK-GDPR. Mitigations: rely on GA4's IP-anonymization-by-default; add a short privacy note to the About/footer describing GA4 + giscus; keep a cookie/consent notice as a documented follow-up (GA4 sets cookies). giscus stores commenter GitHub identity in the repo's Discussions (public, owner-moderated). No other PII is collected.
- **Secrets** — GA4 Measurement ID and giscus IDs are **public identifiers by design** (they ship in client-side HTML), not secrets — safe to commit. No API keys or tokens are introduced. Nothing sensitive enters the repo.
- **Input & trust boundaries** — giscus renders a third-party iframe from `giscus.app`; comment content is user-generated and sandboxed in that iframe (not injected into our DOM). Security headers (below) constrain framing/MIME behavior. If a strict CSP is added, it must allowlist `giscus.app`, GitHub avatar hosts, and `googletagmanager.com`/`google-analytics.com`, or the embeds break — so CSP starts permissive/report-only to avoid breaking the third-party embeds, tightened later.
- **Top threats & mitigations** — (a) *Clickjacking* → `X-Frame-Options: DENY` / frame-ancestors. (b) *MIME sniffing* → `X-Content-Type-Options: nosniff`. (c) *Referrer leakage* → `Referrer-Policy: strict-origin-when-cross-origin`. (d) *Comment spam/abuse* → giscus inherits GitHub Discussions moderation; owner can lock/delete. (e) *Stale/incorrect indexing* → fixed by the baseURL correction (Increment 2).

## 4. Implementation Steps (iterative increments)

Each increment is independently shippable and leaves the site building. Ordered by dependency and value.

| # | Increment | Files | Acceptance check | Type |
|---|-----------|-------|------------------|------|
| 1 | **Repo hygiene** | `.gitignore` (add `public/`, `resources/`, `.hugo_build.lock`); `git rm -r --cached` those | `git status` shows them ignored; site still builds | Scaffold (mechanical) |
| 2 | **Fix baseURL + core config** | `hugo.toml` | baseURL, `[params]` description/author, `[params.ananke]` opts, `enableRobotsTXT=true`, `[minify]`, `[markup.highlight]`, `[menus]` (Home/Posts/About), `mainSections` | Rebuild: sitemap/canonical/RSS all `pg-blogs.netlify.app`; `public/robots.txt` exists and references sitemap; homepage `<meta description>` non-empty | Logic |
| 3 | **Netlify build + headers** | `netlify.toml` | build → `hugo --gc --minify`; add `[[headers]]` (security + long-cache for `/ananke/*` fingerprinted assets) | `hugo --gc --minify` clean; netlify.toml parses; headers present for `/*` and asset paths | Logic |
| 4 | **Favicon + default OG image** | `static/favicon.svg` (+PNG), `static/images/og-default.png`, `layouts/_partials/head-additions.html`, `hugo.toml` param | Generate assets (Pillow) or SVG fallback; wire favicon link + default `og:image` | Favicon 200s; every page head has an `og:image` | Logic + scaffold |
| 5 | **About page + author + nav** | `content/about.md`, `hugo.toml` (author, menu) | About page with owner bio + brief privacy note; menu entry | `/about/` renders; appears in nav | Scaffold + logic |
| 6 | **GA4** *(needs ID)* | `hugo.toml` (`googleAnalytics`) | Set Measurement ID | gtag/GA script present in built pages when ID set | Scaffold |
| 7 | **giscus comments** *(needs GitHub setup + IDs)* | `layouts/_partials/comments.html`, `layouts/single.html`, `hugo.toml` (`[params.giscus]`) | giscus embed gated on config + `hugo.IsProduction`; included after article | giscus container renders on a post page in a prod build | Logic |
| 8 | **Verify & hand off** | `docs/evidence/` | Full `hugo --gc --minify`; spot-check outputs; record evidence | Zero-warning build; acceptance transcript captured | Verify |

**Dependencies:** 2 precedes 3–8 (correct config first). 6 and 7 depend on the two open questions; everything else is unblocked. **Right-sizing note:** these are small, low-risk config/asset edits — implemented directly (with per-increment verification) rather than fanned out to subagents, per "match rigor to stakes."

## 5. Testing & Verification

- **Per increment:** rebuild with `hugo --gc --minify`; assert the acceptance check against the *generated* `public/` output (grep the real HTML/XML), not against intent.
- **Edge cases:** GA4 and giscus must **not** load in `hugo server` dev mode (gate on `hugo.IsProduction`); robots.txt must allow crawl + list sitemap; security headers must not break the giscus iframe or GA script (verify embeds still function).
- **Config toggles (ON/OFF):** giscus and GA are config-gated — verify a build with them disabled (or unset) still succeeds and omits the scripts, and an enabled build includes them.
- **"Done" =** zero-warning production build + all §1 success criteria demonstrably met in `public/`, recorded under `docs/evidence/`.

## 6. Risks & Rollback

- **Wrong giscus IDs** → embed silently shows an error box. Mitigation: verify against a live post after the owner provides IDs. Rollback: unset `[params.giscus]`.
- **Copied `single.html` drifts from theme** → future ananke changes to that file won't apply. Mitigation: documented; the override is minimal (adds one partial include). Rollback: delete the override.
- **CSP too strict breaks embeds** → start without a strict CSP (or report-only); add security headers that don't require an allowlist first.
- **Netlify submodule not fetched** → blank theme. Mitigation: already relied upon and working; unchanged by this plan.
- General rollback: every change is an additive file or a config edit under git — revert the commit.

## 7. Impact

- **Files added:** `.gitignore`, `netlify.toml` (edited), `hugo.toml` (edited), `content/about.md`, `static/favicon.svg` (+ PNG, `static/images/og-default.png`), `layouts/_partials/head-additions.html`, `layouts/_partials/comments.html`, `layouts/single.html`, `docs/evidence/*`.
- **Removed from git tracking:** `public/`, `resources/`, `.hugo_build.lock` (files remain on disk, now ignored).
- **Migrations/breaking changes:** none. **Docs to update:** this plan's status on approval.
