# Evidence — Production-Readiness Upgrades (Increments 1–8)

**Date:** 2026-07-03
**Plan:** `PLAN.md` (Status: APPROVED, owner-confirmed 2026-07-03)
**Git state:** working tree, **not committed** (per "commit only when asked" policy) — no commit hash; changes verified against the working tree and the generated `public/`.
**Verification model:** This is a Hugo static site — there is no application test suite / migrations / coverage to run. Per "test at the right level," the acceptance gate is: **production build completes with zero warnings** + **assertions grepped against the generated `public/` output** (not against intent). All transcripts below are real command output captured during implementation.

> **Disclosed deviation from §4 (evidence file convention):** the eight increments were small, related config/asset changes executed in one session, so they are recorded here as one file with per-increment sections rather than eight separate `increment-NN.md` files. Flagged for faithfulness.

---

## Increment 1 — Repo hygiene
**Changed:** added `.gitignore`; `git rm -r --cached public resources .hugo_build.lock`.
**Acceptance:**
```
tracked build files remaining: 0
gitignore honored? public resources/_gen .hugo_build.lock
```
Files remain on disk; only untracked from git. ✅

## Increment 2 — baseURL + core config
**Changed:** `hugo.toml` — baseURL → `https://pg-blogs.netlify.app/`, site `description`, `author`, `mainSections`, `show_reading_time`, `[params.ananke]`, `[menu.main]` (Home/Posts/About), `[markup.highlight]`, `enableRobotsTXT=true`.
**Acceptance:**
```
example.org occurrences in public/: 0
canonical: https://pg-blogs.netlify.app/posts/1-why-java-still-matters-today/
robots.txt: User-agent: *  Allow: /  Sitemap: https://pg-blogs.netlify.app/sitemap.xml
homepage <meta description>: "Practical, no-hype best practices for Java and Python developers…"
nav: >Home< >Posts< >About<
reading time on post: "minutes" + "859 words"
```
✅ (baseURL blocker resolved; the theme's robots.txt already emits the sitemap in production, so no custom template was needed.)

## Increment 3 — Netlify build + security headers
**Changed:** `netlify.toml` — build `hugo --gc --minify`, `HUGO_ENV=production`, `[[headers]]` security block for `/*` (X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy) + 1-week cache for `/images/*`.
**Decision:** no immutable long-cache on theme CSS — ananke does not fingerprint `main.min.css`, so immutable caching would serve stale styles after a theme update. No CSP yet (would need to allowlist giscus/GitHub/GA; deferred to report-only follow-up).
**Acceptance:**
```
netlify.toml valid TOML — build.command = 'hugo --gc --minify'; header blocks: 2
production minified build: clean, no warnings
```
Header *delivery* is a Netlify-edge behavior, verifiable only on the deployed site (see Follow-ups). ✅ (config validated)

## Increment 4 — Favicon + default OG image
**Changed:** generated `static/images/og-default.png` (1200×630, Pillow), `static/favicon.svg`, `static/favicon-32x32.png`, `static/apple-touch-icon.png`; added `layouts/_partials/head-additions.html` (icon links) + `images` param.
**Acceptance:**
```
<link rel=icon href=/favicon.svg type=image/svg+xml>
<link rel=icon href=/favicon-32x32.png type=image/png sizes=32x32>
<link rel=apple-touch-icon href=/apple-touch-icon.png>
og:image: https://pg-blogs.netlify.app/images/og-default.png (absolute)
assets in public/: favicon.svg, favicon-32x32.png, apple-touch-icon.png, images/og-default.png
```
✅ (Pillow was installed into a scratchpad venv after confirming it was absent system-wide; OG image visually reviewed.)

## Increment 5 — About page + author + nav
**Changed:** `content/about.md` (what the blog is, topics, stack, privacy note, **placeholder for owner bio** left intentionally un-fabricated); `author`/menu already in `hugo.toml`.
**Acceptance:**
```
/about/ renders: <title>About | PG Blog</title>
About in nav → href=/about/
byline on posts: <strong>PG Blog</strong>
```
✅

## Increment 6 — GA4
**Changed:** `[services.googleAnalytics] ID = "G-Q3T0426WLM"` in `hugo.toml`.
**Acceptance (paired ON/OFF):**
```
production build: G-Q3T0426WLM present + googletagmanager
development build: GA count 0 (gated by baseof.html hugo.IsProduction)
```
✅

## Increment 7 — giscus comments
**Changed:** `layouts/_partials/comments.html` (gated on `hugo.IsProduction` AND `params.giscus.repoId`); `layouts/single.html` override (theme copy + one `partials.Include "comments.html"`); `[params.giscus]` in `hugo.toml`.
**Decision/risk:** the copied `single.html` won't auto-track future theme changes to that one file (documented; override is one added line).
**Acceptance (paired ON/OFF):**
```
production: giscus.app/client.js present; data-repo-id=R_kgDOQ0ZlPw
development: giscus count 0; robots.txt Disallow: /
```
✅

## Increment 8 — Final verification
**Full production build:** clean, no warnings, 87 pages, 244 ms.
```
S1 no example.org ............ 0        (want 0)  ✅
S2 robots.txt + sitemap ...... YES                ✅
S3 homepage description ...... YES                ✅
S3 og:image on every post .... 0 missing (want 0) ✅
S4 build output untracked .... 0 tracked (want 0) ✅
S5 favicon served ............ YES                ✅
S5 /about/ + in nav .......... YES                ✅
S6 GA4 in production ......... YES                ✅
S7 giscus on posts ........... YES                ✅
```

## Follow-ups requiring the live deployed site or the owner
1. **Deploy to Netlify**, then confirm: security headers present (`curl -I https://pg-blogs.netlify.app/`), GA4 Realtime shows the visit, giscus renders and a test comment creates a GitHub Discussion.
2. **Personalize** the "Who's behind it" section of `content/about.md` (name/bio/contact) — left as a placeholder.
3. **Optional:** custom domain; a report-only CSP; a cookie-consent banner for GA4 depending on audience region.
