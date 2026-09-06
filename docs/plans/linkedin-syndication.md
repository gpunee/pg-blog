# Plan: Automated LinkedIn posting — `syndicate linkedin` (POSSE share to owner's personal profile)

Status: APPROVED   <!-- approved by owner at Phase 3 on 2026-07-26 (personal-profile target, owner-run command, per-post commentary override w/ generated fallback) -->

> Companion to `docs/plans/syndication.md` (the Dev.to / Medium / teasers effort). This plan **extends**
> that tool additively with a new `linkedin` subcommand. Read `syndication.md` §3.1 (module layout),
> §3.2 (idempotency-via-state), and §3a (secret handling, draft/dry-run safety) first — this plan
> mirrors those patterns and only documents what is new or different for LinkedIn.

---

## 1. Goal & Context

**Problem (restated):** The 35 posts on `pg-blogs.netlify.app` are already syndicated to Dev.to (automated)
and Medium (assisted), and the tool generates LinkedIn *teaser text* (`syndicate teasers`) that the owner
pastes by hand. The owner wants that last manual step **automated**: one owner-run command that publishes a
POSSE-style share — a short professional hook plus the canonical link back to the post — to the **owner's
personal LinkedIn profile**, using the same safety model as the existing `devto` subcommand.

**Approach — POSSE, unchanged:** the Netlify site stays the canonical original. A LinkedIn share is
*distribution*, not a hosted copy: it carries the post's commentary (owner-authored or generated) + the
canonical URL as an ARTICLE link-preview card, driving traffic back to the owner's domain. No `rel=canonical` concern (LinkedIn does not host a copy
of the article body).

**What "automation" means here (honest scope):** LinkedIn's **"Share on LinkedIn"** product with the
`w_member_social` OAuth scope exposes a real write endpoint (`POST /v2/ugcPosts`). We script the *publish*.
We do **not** script token minting: LinkedIn issues only a 60-day member access token to a standard app
(programmatic refresh is MDP-partner-only — see §2), so the owner mints/re-mints the token via LinkedIn's
Developer Portal token generator and exports it into their shell, exactly as they do `DEVTO_API_KEY`.

**Success criteria (measurable):**
- One command (`syndicate linkedin`) previews or publishes a share for all (or a `--only NN[,NN,…]` subset)
  of the 35 posts, each containing the post's commentary (an **owner-authored sidecar override** if present,
  else a generated hook) + canonical URL as an ARTICLE share.
- **Nothing posts live without `--publish`.** Because LinkedIn shares have no draft state, the default
  (no `--publish`) is **preview-only with zero network calls**, and `--dry-run` is an explicit preview.
- Re-running never creates a duplicate share: a slug already recorded in `linkedin_state.json` is **skipped**.
- The access token is **env-only, never committed / logged / echoed**; `linkedin_state.json` holds only
  public share URNs (no secrets).
- Existing `devto` / `medium` / `teasers` behavior is **unchanged**; their tests stay green.

**Non-goals / out of scope:**
- Company Page / Community Management API posting (confirmed: personal profile via "Share on LinkedIn" only).
- Image/video shares, scheduling, editing an existing share's text, analytics/read-back of engagement.
- Building an OAuth callback server or a token-refresh daemon (standard app has no programmatic refresh token).
- Changing any blog content, the Hugo build, or the existing `devto`/`medium`/`teasers` commands.

---

## 2. Assumptions & Open Questions

**Assumptions (safe / reversible):**
- **Stack = Python**, same `scripts/syndicate/` package, same conventions (PEP 8, type hints, pytest,
  `requests`). **No new dependency** — `requests` is already pinned in `requirements.txt`.
- The tool consumes an **already-minted member access token** from env (`LINKEDIN_ACCESS_TOKEN`); the OAuth
  client_id/client_secret **never enter the tool** (the owner mints the token outside it). This shrinks the
  tool's secret surface to a single token.
- `linkedin_state.json` (slug → share URN) lives beside `state.json` and is **committed** (public URNs only,
  no secrets) — it is the *sole* duplicate-avoidance guard (LinkedIn offers no cheap "list my shares by URL"
  fallback), so durability across machines matters more here than for Dev.to.
- Endpoint `POST https://api.linkedin.com/v2/ugcPosts` with header `X-Restli-Protocol-Version: 2.0.0` is the
  path documented by the consumer "Share on LinkedIn" guide (verified — §3.4). Author URN format
  `urn:li:person:{id}`.

**Open questions (need the owner before the live smoke — none block the code increments L1–L3, which are
fully mock-tested):**
1. **Author-URN resolution / scope choice (non-blocking; default chosen).** Resolve the author URN one of two
   ways; the design supports both and the owner picks by whether they set `LINKEDIN_AUTHOR_URN`:
   - **(a, default) runtime resolve:** leave `LINKEDIN_AUTHOR_URN` unset; the tool calls `GET /v2/userinfo`
     once per live run to read `sub` and build `urn:li:person:{sub}`. Requires the token to carry
     `openid profile w_member_social` (so the app also adds the "Sign In with LinkedIn using OpenID Connect"
     product). One env var for the owner.
   - **(b, least-privilege) env-supplied URN:** the owner sets `LINKEDIN_AUTHOR_URN=urn:li:person:{id}` once;
     the tool never calls userinfo and the token needs only `w_member_social`. Two env vars.
   **Recommendation:** ship both; default to (a). *Owner: confirm which products you added and whether you
   prefer one env var or strict least-privilege.*
2. **Commentary voice — RESOLVED (owner, 2026-07-26).** Because a live LinkedIn post is high-visibility
   owner-voice content and the generated `_linkedin_hook` is mechanical (project rule §5 forbids mechanical
   filler), the commentary is **owner-overridable with a generated fallback**:
   - **Override source = a committed per-post sidecar file** at `scripts/syndicate/linkedin/<slug>.md`
     (plain text / Markdown, holding *only* the human commentary — never the whole payload).
   - **Precedence:** if the sidecar exists and its stripped content is non-empty, that text is the commentary;
     otherwise the generated hook (`_linkedin_hook(post)`) is the fallback.
   - `build_linkedin_share` **always** appends the canonical URL and sets the ARTICLE preview card, regardless
     of source — so the sidecar author writes only the human hook, not the link or card.
   Design folded into §3.3 (Commentary resolution) and §3.6 (data model). Mechanical-filler risk is removed:
   the owner edits any post's voice by dropping a sidecar; dry-run still prints the full resolved commentary
   verbatim (labelled with its source) for review. A `linkedin --init-sidecars` scaffold that pre-fills
   sidecars with the generated hook is a **noted, out-of-L1-scope follow-up** (§6), not built now (YAGNI).
3. **`/v2/ugcPosts` longevity (non-blocking risk, see §6).** The consumer Share guide documents
   `/v2/ugcPosts`; LinkedIn's newer marketing surface uses `/rest/posts` with a `LinkedIn-Version: YYYYMM`
   header. If LinkedIn migrates consumer shares, the client's single `_request` choke point is where the URL
   + version header change. *No owner action needed now; flagged for awareness.*

---

## 3. Design (WHAT / HOW / WHY)

### 3.1 Module layout (additive to `scripts/syndicate/`)
New / changed files only; everything else in the package is untouched.

| File | Change | Concern |
| --- | --- | --- |
| `linkedin.py` | **new** | `LinkedInClient` + `LinkedInError` — the API client (mirrors `devto.py`). |
| `payload.py` | **add fn** | `build_linkedin_share(post, author_urn, commentary, visibility)` — the ugcPosts body (mirrors `build_devto_article`). |
| `generate.py` | **add fns** | `linkedin_commentary(post)` — the generated fallback hook text (reuses `_linkedin_hook`, no canonical); `resolve_linkedin_commentary(post, sidecar_dir)` — sidecar-override-or-fallback. |
| `cli.py` | **add subcmd** | `linkedin` subparser + `cmd_linkedin` + `_linkedin_sidecar_dir()` anchor (mirrors `cmd_devto` / `_state_path`). |
| `linkedin_state.json` | **new, committed** | `{ slug: share_urn }` idempotency map (public URNs, no secrets). |
| `linkedin/<slug>.md` | **new dir, committed** | Optional per-post owner-authored commentary override (plain text/Markdown; commentary only). |
| `README.md` | **update** | Document the `linkedin` command + token setup (done inside increment L3). |
| `tests/test_linkedin_payload.py`, `tests/test_linkedin.py`, `tests/test_cli_linkedin.py` | **new** | Mirror `test_payload.py` / `test_devto.py` / `test_cli.py`. |

`run.sh` needs **no change** (it forwards `"$@"`). `requirements.txt` needs **no change**. `.gitignore` needs
**no change** (`linkedin_state.json` should be tracked; the token is never written to any file).

### 3.2 `LinkedInClient` (in `linkedin.py`) — modeled on `DevToClient`
Same shape as `devto.py`: a single `_request` choke point that injects auth headers and retries on 429/5xx;
the token read once from env at construction; an error type that carries status + body but **never the token**.

- `__init__(self, access_token: str | None = None, session=None, base_url="https://api.linkedin.com")` —
  `access_token` falls back to `os.environ.get("LINKEDIN_ACCESS_TOKEN")` (read once, like devto).
- `has_token` property → `bool(self._access_token)` (never exposes the token; mirrors `has_key`).
- `_require_token()` → raises `RuntimeError("LINKEDIN_ACCESS_TOKEN not set")` (no value in the message).
- `class LinkedInError(Exception)` — `__init__(status_code, body)`, message `f"LinkedIn API error {status}: {body}"`.
  **Constraint:** the token must never appear in the message (unit-tested).
- `_request(method, path, json=None)` — adds headers
  `Authorization: Bearer {token}`, `X-Restli-Protocol-Version: 2.0.0`, and (for JSON bodies)
  `Content-Type: application/json`. Reuse the devto retry loop verbatim (module-level `SLEEP`,
  `MAX_RETRIES=3`, `RETRYABLE_STATUSES={429,500,502,503,504}`). Returns the `requests.Response` (see next
  bullet — the create path needs the response *header*, not the JSON body).
- `get_person_urn(self) -> str` — `GET /v2/userinfo`; parse `sub` from the JSON; return `urn:li:person:{sub}`.
  Raises `LinkedInError`/clear error if `sub` is absent (e.g. token lacks `openid profile`). Used only in
  open-question path (a): when `LINKEDIN_AUTHOR_URN` is unset.
- `create_ugc_post(self, payload: dict) -> str` — `POST /v2/ugcPosts` with `json=payload`; on `201`, return
  the share URN from the **`X-RestLi-Id` response header** (LinkedIn does not return it in the body). Any
  non-2xx → `LinkedInError` (surfaced status+body, no token).

> **WHY a response-header return (differs from devto):** `create_article` returns `response.json()["id"]`;
> LinkedIn's ugcPosts create returns an (often empty) body and puts the new URN in `X-RestLi-Id`. The
> implementer must read `response.headers["X-RestLi-Id"]`, not the JSON. This is the one place `_request`'s
> "return the Response object" shape is load-bearing.

> **As built (inc L2):** the two malformed-*success* paths raise **`RuntimeError`** (not `LinkedInError`):
> `get_person_urn()` when a 2xx `/v2/userinfo` body lacks `sub`, and `create_ugc_post()` when a 201 lacks the
> `X-RestLi-Id` header. `LinkedInError` is reserved for non-2xx responses (it carries `(status, body)`, which a
> malformed 2xx has no meaningful value for). **L3 consequence:** the per-post live loop must treat *both*
> `LinkedInError` and this `RuntimeError` from `create_ugc_post` as a failed post (count/print/continue) so one
> bad response cannot abort the batch — see §3.5 step 5.

### 3.3 Payload builder (`build_linkedin_share` in `payload.py`) — the ugcPosts ARTICLE share
Pure function, no network. The caller passes the already-resolved `commentary` text (see §3.3.1);
`build_linkedin_share` **always** appends the canonical URL to the commentary and sets the ARTICLE preview
card, so the human-authored part never has to include the link. `visibility` defaults to `"PUBLIC"`.

```python
def build_linkedin_share(
    post: Post, author_urn: str, commentary: str, visibility: str = "PUBLIC"
) -> dict:
    text = f"{commentary.rstrip()}\n\n{post.canonical_url}"   # canonical always appended
    return {
        "author": author_urn,                         # "urn:li:person:{id}"
        "lifecycleState": "PUBLISHED",                 # ugcPosts has no draft state (see §3.5)
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "ARTICLE",
                "media": [
                    {
                        "status": "READY",
                        "originalUrl": post.canonical_url,      # drives the link-preview card
                        "title": {"text": post.title},
                        "description": {"text": post.description},
                    }
                ],
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": visibility},
    }
```

#### 3.3.1 Commentary resolution (override → generated fallback)
Only the **human commentary text** is overridable; the canonical link and ARTICLE card are always machine-
appended by `build_linkedin_share` (above). Resolution is two pure functions in `generate.py`:

- `linkedin_commentary(post) -> str` — the **generated fallback**: `_linkedin_hook(post)` text only (no
  canonical — the builder appends it). Reuses the existing `_linkedin_hook` so the hook has one source of
  truth. `teaser()` is **not** modified (additive-only — its output must not change).
- `resolve_linkedin_commentary(post, sidecar_dir: Path) -> str` — precedence:
  1. If `sidecar_dir / f"{post.slug}.md"` exists **and** its `.strip()`-ed content is non-empty → return that
     content (the owner's override).
  2. Else → return `linkedin_commentary(post)` (generated fallback).

  `sidecar_dir` is injected (not hardcoded) so the function is unit-testable against a `tmp_path`; the CLI
  (L3) supplies the real dir via `_linkedin_sidecar_dir()` = `Path(__file__).resolve().parent / "linkedin"`
  = `scripts/syndicate/linkedin/`, anchored exactly like `_state_path()`.

> **WHY `scripts/syndicate/linkedin/` and not `scripts/syndication/linkedin/`:** the repo's `.gitignore`
> line 25 ignores the whole `scripts/syndication/` tree (it is regenerable teaser *output*). A committed,
> owner-authored source file must live under the tracked package dir `scripts/syndicate/`, beside
> `linkedin_state.json` — separate from the ephemeral `scripts/syndication/teasers/`.

> **Trust boundary:** the sidecar is **owner-authored** (low sensitivity) but is still *external input
> interpolated into an API payload*, so it is treated as untrusted at the boundary: read as UTF-8, `.strip()`
> checked for emptiness (empty/whitespace-only ⇒ fall back, never post a blank commentary), and serialized
> only via `requests`' `json=` (which JSON-escapes) — no manual string-building into JSON. Title/description
> come from our own front matter (first-party). Validate `author_urn` is a non-empty `urn:li:person:` string
> before posting.

### 3.4 Verified LinkedIn API facts (grounded in live docs — §6 of `syndication.md` never covered LinkedIn)
All confirmed 2026-07-26 against `learn.microsoft.com/en-us/linkedin/…`:

| Fact | Value | Source |
| --- | --- | --- |
| Product / scope | "Share on LinkedIn" product grants `w_member_social` ("create a post on behalf of the authenticated member") | [share-on-linkedin](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin) |
| Create endpoint | `POST https://api.linkedin.com/v2/ugcPosts`, required header `X-Restli-Protocol-Version: 2.0.0` | [share-on-linkedin](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin) |
| Success / result id | `201 Created`; new post identified by the **`X-RestLi-Id` response header** | [share-on-linkedin](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin) |
| Author URN | `author: "urn:li:person:{id}"` | [share-on-linkedin](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin) |
| ARTICLE share body | `specificContent."com.linkedin.ugc.ShareContent"` with `shareCommentary.text`, `shareMediaCategory:"ARTICLE"`, `media[].{status:"READY",originalUrl,title.text,description.text}`, `visibility."com.linkedin.ugc.MemberNetworkVisibility":"PUBLIC"` | [share-on-linkedin](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin) |
| Member id / Person URN | From OpenID Connect: `GET https://api.linkedin.com/v2/userinfo` (Bearer) → `sub`; requires `openid profile` scope (legacy `/v2/me` needs deprecated `r_liteprofile`) | [sign-in-with-linkedin-v2](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2), [share-on-linkedin](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin) |
| OAuth authorize | `GET https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=…&redirect_uri=…&state=…&scope=…` (scopes URL-encoded, space-delimited; code TTL 30 min) | [authorization-code-flow](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow) |
| Token exchange | `POST https://www.linkedin.com/oauth/v2/accessToken`, `Content-Type: application/x-www-form-urlencoded`, params `grant_type=authorization_code, code, client_id, client_secret, redirect_uri` → JSON `{access_token, expires_in, scope[, refresh_token, refresh_token_expires_in]}` | [authorization-code-flow](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow) |
| Access-token lifetime | **60 days** (`expires_in` = 5184000 typical) | [authorization-code-flow](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow), [refresh-tokens](https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens) |
| Refresh token | **MDP-partners only:** "LinkedIn supports programmatic refresh tokens for all approved Marketing Developer Platform (MDP) partners." Standard app ⇒ **no** `refresh_token` returned; re-auth every 60 days. Grant (if eligible): `POST /oauth/v2/accessToken`, `grant_type=refresh_token` | [refresh-tokens](https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens) |
| Manual token minting | Developer Portal **Token Generator** creates a member token directly (no callback server needed) | [authorization-code-flow](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow) |
| Rate limits | **150 requests/member/day**; 100,000/app/day | [share-on-linkedin](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin) |

**Consequences for the design:**
- No refresh flow is built (would be dead code for a standard app). Token expiry is handled by a **clear
  401 message** telling the owner to re-mint (§3a threat 5).
- 35 posts × (≤1 userinfo + 1 create) ≤ 71 member calls — well under 150/day.
- `LinkedIn-Version` (YYYYMM) header is **not** sent (that header belongs to the newer `/rest/posts` API; the
  consumer `/v2/ugcPosts` path needs only `X-Restli-Protocol-Version: 2.0.0`).

### 3.5 CLI semantics (`cmd_linkedin`) — mirrors `cmd_devto`, with the draft→preview divergence
Flags identical to `devto`: `--all` (default) / `--only NN[,NN,…]`, `--dry-run`, `--publish`, `--yes`.
Selection reuses the existing `_select_posts`. Live-confirm reuses the existing `_confirm_live_publish`
(generalized to name the platform, or a thin wrapper) — no new confirm logic invented.

**Key divergence from devto — there is no LinkedIn draft state.** Dev.to's default (`--publish` omitted)
creates a *draft article* via a live call. A LinkedIn ugcPost is immediately `PUBLISHED`; there is no draft.
Therefore for `linkedin`:
- **`--publish` is the *only* thing that makes a live `create_ugc_post` call.**
- **Without `--publish` (and with or without `--dry-run`): preview-only, ZERO network calls** — print, per
  selected post, the resolved-or-placeholder author URN, visibility, the commentary **source**
  (`sidecar` vs `generated`, from `resolve_linkedin_commentary`), and the **full resolved commentary text +
  canonical** (exactly what `build_linkedin_share` would send), then a footer: *"LinkedIn has no draft state;
  nothing was posted. Re-run with --publish to post live."* This makes accidental posting structurally
  impossible without the explicit flag, and lets the owner see which posts still use the generated fallback.

Live path (`--publish`), per selected post, in order:
1. If `post.slug` in `linkedin_state.json` → **skip**, print `[slug] already shared (urn=…)`. (No re-post;
   LinkedIn has no dedup and editing a share's text isn't supported here — a share is a point-in-time event.)
2. Resolve `author_urn`: `LINKEDIN_AUTHOR_URN` env if set (no network), else `client.get_person_urn()` once,
   cached in memory for the run.
3. `commentary = resolve_linkedin_commentary(post, _linkedin_sidecar_dir())`;
   `build_linkedin_share(post, author_urn, commentary)` → `client.create_ugc_post(payload)` → returns share URN.
4. Record `linkedin_state[slug] = urn`, `save_state(...)` **only after** the 201 (per-post, atomic — reuse
   `state.load_state`/`save_state`). Print `[slug] shared (urn=…)`.
5. `LinkedInError` on a post → increment `skipped`, print `[slug] FAILED: …`, continue (state uncorrupted).

> **As built (inc L2):** step 5 must **also** catch the malformed-success **`RuntimeError`** that
> `create_ugc_post` raises on a 201 lacking `X-RestLi-Id` (see §3.2 as-built) — treat it identically to a
> `LinkedInError` (print `[slug] FAILED: …`, continue; state stays clean since it is written only after a good
> URN). `get_person_urn()`'s missing-`sub` `RuntimeError` is resolved once in step 2, *before* the per-post
> loop, so it aborts the run pre-post — acceptable (no share is possible without an author URN). The summary
> counter for an errored post is **`failed:`** (the §3.5 summary line's `failed: K` is authoritative; step 5's
> inline word "skipped" predates it — for L3, an error increments `failed`, and `skipped(already)` is only the
> step-1 already-in-state case).

Guards (reuse devto's): `--publish` without a token → print the `LINKEDIN_ACCESS_TOKEN`-not-set message,
exit 1, zero network. `--publish` on a non-TTY without `--yes` → refuse. `--yes` skips the prompt. Summary
line: `Shared: N, skipped(already): M, failed: K.`

> **As built (inc L3):** three clarifications to this section, all pinned by tests:
> - **`--publish --dry-run` resolves to preview** (`if args.dry_run or not args.publish:`). The section enumerated the "no `--publish`" and "`--publish`" branches but not the combination; resolved toward the safer network-free reading (mirrors devto's `--dry-run` precedence). So the create call is reachable **only** when `--publish` is set *and* `--dry-run` is not.
> - **Step 2 author-URN resolution is lazy** — resolved on the first post that actually needs sharing (after the step-1 skip check), not eagerly before the loop, then cached in a local for the run. An all-already-shared batch therefore makes **zero** `get_person_urn` calls. Consistent with "once per run, cached."
> - **`_confirm_live_publish` was generalized in place**, not wrapped: it gained a `platform: str = "Dev.to"` keyword param. `cmd_devto` omits it (wording byte-for-byte unchanged; devto tests green); `cmd_linkedin` passes `platform="LinkedIn"`.
> Evidence `docs/evidence/increment-syndication-08-linkedin-cli.md`.

### 3.6 Data model — every persisted / configured entity
| Entity | Where | Contents | Secret? | Lifecycle |
| --- | --- | --- | --- | --- |
| `linkedin_state.json` | `scripts/syndicate/linkedin_state.json` (committed) | `{ slug: "urn:li:share:…" }` | No — public URNs | Written per-post after a 201; hand-edit a slug out to allow a deliberate re-share |
| Commentary sidecar | `scripts/syndicate/linkedin/<slug>.md` (committed; optional, one per post) | human commentary text only (no link/card) | No — owner-authored, low-sensitivity | **Owner-authored** override; absent ⇒ generated hook fallback. Untrusted at the payload boundary (UTF-8 read, strip-empty check, JSON-escaped via `json=`) |
| `LINKEDIN_ACCESS_TOKEN` | owner's shell env only | member access token (~500 chars) | **Yes** | Owner mints via Portal; exported per session; re-mint ~every 60 days; never persisted by the tool |
| `LINKEDIN_AUTHOR_URN` | owner's shell env only (optional) | `urn:li:person:{id}` | No — public id | Optional; if set, skips userinfo + narrows scope to `w_member_social` |
| Person URN (runtime) | in-memory only | `urn:li:person:{sub}` from `/v2/userinfo` | No | Resolved once per live run, never written to disk |
| OAuth client_id / secret | **never touch the tool** | — | Yes (owner-held) | Used only in the Portal/owner token-minting step, outside the tool |

### 3a. Security & Privacy (mandatory)
- **Authentication.** The tool authenticates to LinkedIn with a **member access token** (OAuth 3-legged,
  minted by the owner). The token is a **secret**: read only from `LINKEDIN_ACCESS_TOKEN` (once, at client
  construction), sent only as an `Authorization: Bearer` header, **never** committed, logged, echoed, or
  placed in an exception. `LinkedInError` carries status+body only (unit-tested to exclude the token). The
  **client secret never enters the tool** — the owner mints the token via the Developer Portal token
  generator — so the tool's secret surface is exactly one env var. MFA on the LinkedIn account is the
  owner's responsibility (N/A to the tool).
- **Authorization.** Least privilege: the token carries `w_member_social` (+ `openid profile` *only* if the
  owner chooses runtime URN resolution, open Q1). `w_member_social` permits posting on the member's behalf
  and nothing else; `openid profile` returns only `sub`/name/picture (no email — `email` scope is not
  requested). Enforcement is at LinkedIn's boundary; the tool cannot exceed the granted scopes. No
  server-side authz of our own (single-owner local CLI).
- **PII / sensitive data.** The share body is the owner's **own** content — an owner-authored sidecar
  commentary or the generated hook over already-public post metadata — plus the canonical URL; no third-party PII. The userinfo `sub`/name are the owner's own identity, used in-memory to build the
  author URN and **never persisted**. `linkedin_state.json` stores only public share URNs. In transit:
  TLS to `api.linkedin.com` / `www.linkedin.com`. At rest: nothing sensitive at rest (token only in
  env/memory). Retention/deletion (rollback): to remove a syndicated share, `DELETE /v2/ugcPosts/{urn}` on
  LinkedIn (owner action) and delete the slug from `linkedin_state.json`. GDPR: owner's own data only —
  N/A for third-party subjects.
- **Secrets.** `LINKEDIN_ACCESS_TOKEN` is env-only, matching the `DEVTO_API_KEY` rule (project §4). Pure
  `os.environ` read (no dotenv parsing), matching devto. Never written to `linkedin_state.json`, logs, or
  code. No secret manager needed for a single-owner local CLI (env var is the appropriate, simplest
  mechanism); a gitignored `scripts/syndicate/.env` is already ignored if the owner ever wants it, but the
  design does not read one.
- **Input & trust boundaries.** All external input is untrusted: LinkedIn API responses are parsed
  defensively — a missing `sub` (userinfo) or missing `X-RestLi-Id` (create) raises a clear error rather
  than crashing; non-2xx surfaces `LinkedInError` and aborts *that* post without corrupting state (state is
  written per-post only after a confirmed 201). The **commentary sidecar** (`scripts/syndicate/linkedin/
  <slug>.md`) is owner-authored and low-sensitivity, but it is still external text interpolated into an API
  payload, so it is boundary-handled: read as UTF-8, `.strip()`-checked for emptiness (empty ⇒ generated
  fallback, never a blank post), and serialized only via `requests`' `json=` (proper JSON escaping) — no
  manual string-into-JSON. `author_urn` is validated as a `urn:li:person:` string before use.
- **Threats & mitigations.**
  1. **Token leak** → env-only; never logged/committed/echoed; `LinkedInError` redacts; client secret never
     touches the tool; rollback: revoke/rotate the token in the Developer Portal.
  2. **Accidental live post** → structurally impossible without `--publish`: the default and `--dry-run` make
     **zero** network calls (no draft state to fall back on, so "no `--publish`" = preview). `--publish`
     additionally requires a TTY confirm or `--yes`.
  3. **Duplicate posts** → `linkedin_state.json` skip-if-present; committed for durability because LinkedIn
     has no canonical-match fallback; re-share requires a deliberate hand-edit of the state file.
  4. **Embarrassing / wrong content** → dry-run prints the **full commentary verbatim** for review; `--only`
     publishes one at a time.
  5. **Token expired mid-run** → 401 → `LinkedInError` with a clear "token expired/invalid — re-mint via the
     Developer Portal and re-export `LINKEDIN_ACCESS_TOKEN`" message; no partial state corruption.

### 3b. Non-functional
- **Cost:** **$0.** LinkedIn "Share on LinkedIn" API is free; no infrastructure, no storage beyond a small
  committed JSON file. *Cost driver:* none (owner-run local CLI). *Cheaper alternative considered:* keep the
  existing manual `teasers` paste workflow ($0, already shipped) — this increment trades a small standing
  cost (re-minting a 60-day token) for removing the manual paste; the owner opted to automate.
- **Latency / rate:** a handful of REST calls per run (≤71 for all 35), far under the 150/member/day limit;
  reuse the devto retry/backoff. **Observability:** per-post action line (shared / already-shared / FAILED)
  + a summary, matching devto.

### 3c. As-built notes
> Phase 5 back-fill appends `> **As built (inc L#):** …` blockquotes here — never a silent rewrite.

> **As built (inc L1):** `payload.build_linkedin_share` + `generate.linkedin_commentary` /
> `generate.resolve_linkedin_commentary` implemented exactly per §3.3/§3.3.1; strictly additive (`teaser()`
> untouched). Evidence `docs/evidence/increment-syndication-06-linkedin-payload.md`.

> **As built (inc L2):** `linkedin.LinkedInClient` + `LinkedInError` per §3.2; `_request` returns the raw
> `Response` on 2xx (header-based URN). Malformed-success cases (missing `sub` / missing `X-RestLi-Id`) raise
> `RuntimeError`, not `LinkedInError` — see the §3.2 and §3.5 as-built notes for the L3 error-handling
> consequence. Evidence `docs/evidence/increment-syndication-07-linkedin-client.md`.

> **As built (inc L3):** `cli.cmd_linkedin` + the `linkedin` subparser per §3.5, strictly additive
> (`cmd_devto`/`cmd_medium`/`cmd_teasers` unchanged; the 94 prior tests stay green). Preview path never
> constructs a `LinkedInClient` (zero-network is structural); the per-post live loop catches **both**
> `LinkedInError` and the malformed-success `RuntimeError`. New committed fixtures: `linkedin_state.json`
> (`{}`) and `scripts/syndicate/linkedin/.gitkeep`. README documents usage + sidecar override + token/URN env
> setup. See the §3.5 L3 note for the three behavioral clarifications. Full suite **111 passed**; acceptance
> `run.sh linkedin --all --dry-run` previews all 35 posts with zero network. Evidence
> `docs/evidence/increment-syndication-08-linkedin-cli.md`. **L1–L3 are code-complete; only L0 (owner
> preflight) + the Phase-5 live smoke remain, both owner actions.**

---

## 4. Implementation Steps (iterative increments)

Ordered; each is small, independently shippable, leaves the tool working, and ships its own mock-network
tests. **L0 is an owner preflight (no code).** L1–L3 are code and do **not** depend on L0 (all network is
mocked in their gates); only the Phase-5 live smoke depends on L0. That is the cross-increment bridge: the
live-publish code path is built and unit-tested against a mocked LinkedIn in L2/L3, exactly as devto's live
path was mock-tested in its increment 02 and only exercised for real by the owner in Phase 5.

### Increment L0 — LinkedIn app + token preflight (OWNER action, no code) — §0 prerequisite
Owner, in the LinkedIn Developer Portal: create an app; add the **"Share on LinkedIn"** product (grants
`w_member_social`); if choosing runtime URN resolution (open Q1a), also add **"Sign In with LinkedIn using
OpenID Connect"** (grants `openid profile`); note client_id/secret (kept by the owner, **not** given to the
tool); mint a member access token via the **Token Generator** with the chosen scopes; `export
LINKEDIN_ACCESS_TOKEN=…` (and optionally `LINKEDIN_AUTHOR_URN=…`) in their shell.
*Acceptance:* owner confirms the env vars are set (the tool's `has_token` is True; a preview run works). No
production code. *Evidence:* recorded by the orchestrator when the owner completes it, immediately before the
live smoke (like devto's Phase-5 live run). *Provisioning note (core §4 preflight):* verify the
`scripts/syndicate/venv` toolchain exists before L1; no new packages are needed.

### Increment L1 — Payload + commentary resolution (pure, no network). **Sonnet.**
Add `build_linkedin_share(post, author_urn, commentary, visibility="PUBLIC")` to `payload.py`; add
`linkedin_commentary(post)` (generated fallback, hook only — canonical is appended by the builder, not here)
and `resolve_linkedin_commentary(post, sidecar_dir)` (§3.3.1 precedence) to `generate.py` (reusing
`_linkedin_hook`; do **not** alter `teaser()`).
*Files:* `payload.py`, `generate.py`, `tests/test_linkedin_payload.py`. *Acceptance:* unit tests —
(1) the built dict has the exact ARTICLE shape of §3.3 (author, `lifecycleState:"PUBLISHED"`, ShareContent,
`ARTICLE` media with canonical `originalUrl`/title/description, `PUBLIC` visibility) and its
`shareCommentary.text` ends with the canonical URL for any commentary input;
(2) **override present** — a non-empty `<slug>.md` in a `tmp_path` sidecar dir → `resolve_linkedin_commentary`
returns that text (not the hook);
(3) **override absent / empty / whitespace-only** → falls back to `linkedin_commentary(post)` (the
`_linkedin_hook` text);
(4) building over all 35 real posts raises nothing and always yields `shareMediaCategory=="ARTICLE"`.
*Size:* small.

### Increment L2 — `LinkedInClient` (network, gated; tests mocked). **Sonnet.**
Add `linkedin.py` per §3.2. *Files:* `linkedin.py`, `tests/test_linkedin.py`. *Acceptance:* unit tests with a
`FakeSession`/`ExplodingSession` (mirror `test_devto.py`): token-not-set → `RuntimeError` mentioning
`LINKEDIN_ACCESS_TOKEN` and **no** value; `has_token` reflects config; `LinkedInError` never contains the
token; `_request` sends `Authorization: Bearer …` and `X-Restli-Protocol-Version: 2.0.0`; retry on
429-then-200 and exhausted-503; non-retryable (422) no retry; `create_ugc_post` returns the URN from the
`X-RestLi-Id` **header** and POSTs to `/v2/ugcPosts`; `get_person_urn` builds `urn:li:person:{sub}` from a
mocked userinfo and errors cleanly when `sub` is absent. **Zero live calls in the suite.** *Size:* small–med.

### Increment L3 — `linkedin` CLI subcommand + idempotency + sidecar wiring + README (tests mocked). **Sonnet.**
Add the `linkedin` subparser and `cmd_linkedin` per §3.5; add the `_linkedin_sidecar_dir()` anchor (§3.3.1)
and thread `resolve_linkedin_commentary(post, _linkedin_sidecar_dir())` into both preview and live paths;
introduce `linkedin_state.json` (via the existing `state.load_state`/`save_state`, anchored like
`_state_path`) and the committed `scripts/syndicate/linkedin/` sidecar dir (ship a `.gitkeep` so the empty
dir is tracked); update `README.md` (command usage, token setup, **and how to author a sidecar override**).
*Files:* `cli.py`, `README.md`, `linkedin_state.json` (initially `{}`), `scripts/syndicate/linkedin/.gitkeep`,
`tests/test_cli_linkedin.py`. *Acceptance:* paired / failure-mode tests mirroring `test_cli.py` — default &
`--dry-run` make **zero** network calls (use an exploding client) and print full resolved commentary + its
source label + the "no draft state / nothing posted" footer; a monkeypatched sidecar dir with a `<slug>.md`
override → preview/publish uses the sidecar text (labelled `sidecar`) and a slug without one uses the
generated fallback (labelled `generated`); `--only` filters by prefix; a slug already in `linkedin_state.json`
is **skipped** (no create call); `--publish` without a token → exit 1, no network; `--publish` on non-TTY
without `--yes` → refuse; `--publish --yes` calls `create_ugc_post` once and records the returned URN in
state; `LinkedInError` on one post → counted failed, state uncorrupted; env `LINKEDIN_AUTHOR_URN` path makes
no userinfo call while the unset path resolves once. Acceptance run: `run.sh linkedin --all --dry-run`
previews all 35, zero network. Whole suite (existing + new) green. *Size:* medium.

### Phase 5 — Live smoke (OWNER-run, after L0). 
Owner runs `run.sh linkedin --only NN --publish` for a single post with the interactive confirm; orchestrator
records the created share URN, the new `linkedin_state.json` entry, and owner-verified appearance on the
profile (owner-run, not orchestrator-run — matching the devto Phase-5 precedent). Not part of CI.

### 4.0 Context-handoff mapping (minimal brief per increment — never the whole doc)
- **L1:** §3.3 + §3.3.1 (payload shape + commentary override→fallback precedence, sidecar path/format) +
  §3.4 (ARTICLE-share fact row). *Invariants:* pure functions, no network, injectable `sidecar_dir`
  (no hardcoded path); do not change `teaser()` output; canonical appended by the builder (not
  `linkedin_commentary`); canonical scheme from `posts.py`. *Pointers:* existing
  `payload.build_devto_article`, `generate._linkedin_hook`.
- **L2:** §3.2 (client spec) + §3.4 rows (endpoint, `X-Restli-Protocol-Version`, `X-RestLi-Id`, userinfo/`sub`).
  *Invariants:* token env-only + never logged/in-errors; state written only after 2xx (applies at L3);
  mirror `devto.py` retry. *Pointers:* `devto.py`, `tests/test_devto.py`.
- **L3:** §3.5 (CLI semantics + draft→preview divergence) + §3.3.1 (sidecar wiring via
  `_linkedin_sidecar_dir()`, source labelling) + §3.6 (state + sidecar entities) + §3a (safety defaults).
  *Invariants:* no `--publish` ⇒ zero network; skip-if-in-state; token never logged; sidecar dir committed
  under `scripts/syndicate/linkedin/`; reuse `_select_posts`, `_confirm_live_publish`,
  `state.load_state/save_state`. *Pointers:* `cli.py` `cmd_devto` + `_state_path`, `tests/test_cli.py`.

### 4.1 Per-increment gate
- Unit tests green (happy path + failure modes); the `--publish` toggle gets **paired** tests (no-`--publish`
  makes zero network calls / mocked `--publish` makes exactly the expected `create_ugc_post` call).
- No live LinkedIn calls anywhere in the suite; token-redaction test present (L2+).
- Acceptance demonstrated against the real 35 posts where applicable (captured output, not an assertion).
- Existing `devto`/`medium`/`teasers` tests remain green (additive-only proof).
- Evidence `docs/evidence/increment-syndication-<NN>.md` (continuing the series: 06 = L1, 07 = L2, 08 = L3,
  09 = live smoke) with `Gate status: PASS` before the next increment starts.

---

## 5. Testing & Verification
- **Unit tests, network fully mocked** — reuse the `FakeResponse` / `FakeSession` / `ExplodingSession`
  pattern from `tests/test_devto.py` and the `Exploding…Client` / monkeypatch pattern from `tests/test_cli.py`.
  A `FakeResponse` must expose a `headers` dict so `X-RestLi-Id` can be asserted.
- **"Done" per increment** = §4.1 gate passes and evidence is recorded.
- **Edge/failure cases to cover:** token unset; 401 (expired token) surfaces the re-mint message; missing
  `sub` in userinfo; missing `X-RestLi-Id` on create; a slug already in state (skip); `--only` with an
  unknown prefix (empty selection → "No posts selected."); `LinkedInError` mid-batch leaves state consistent;
  `LINKEDIN_AUTHOR_URN` set vs unset (userinfo call vs none).
- **Live smoke** is a single owner-authorized `--only NN --publish` in Phase 5 (not in CI), then owner
  verifies the post on their profile.

## 6. Risks & Rollback
- **Accidental live publish** → no-draft-state means default = zero-network preview; `--publish` + confirm/
  `--yes` required. *Rollback:* `DELETE /v2/ugcPosts/{urn}` + remove slug from `linkedin_state.json`.
- **Token leak** → env-only, redacted errors, never committed; client secret never in the tool. *Rollback:*
  revoke/rotate the token in the Developer Portal.
- **Duplicate share** → committed `linkedin_state.json` skip-guard (sole guard; no canonical fallback).
  *Rollback:* delete the duplicate ugcPost + fix the state entry.
- **60-day token expiry** → clear 401 message → owner re-mints. No refresh flow built (MDP-only). Documented
  in README as a standing chore.
- **`/v2/ugcPosts` deprecation / migration to `/rest/posts`** → the single `_request` choke point isolates
  the URL + a possible `LinkedIn-Version: YYYYMM` header; migration is a localized change, not a redesign.
  Flagged (open Q3) — verify against live docs before any future bump.
- **Mechanical hook voice** (project §5) → resolved (open Q2): the owner overrides any post's commentary via a
  committed `scripts/syndicate/linkedin/<slug>.md` sidecar (§3.3.1); absent ⇒ generated hook fallback. Dry-run
  prints the full resolved commentary + its source (`sidecar`/`generated`) so the owner sees which posts still
  ride the fallback; `--only` publishes one at a time.
- **Follow-up (not in scope now, YAGNI):** a `linkedin --init-sidecars` flag that scaffolds
  `scripts/syndicate/linkedin/<slug>.md` files pre-filled with the generated hook (owner edits rather than
  writes from scratch). Cleanly isolated — it would only add a write-if-absent branch in `cmd_linkedin` and
  reuse `linkedin_commentary`. Deferred until the owner asks; the manual "create a `<slug>.md`" path works today.

## 7. Impact
- **New:** `scripts/syndicate/linkedin.py`, `scripts/syndicate/linkedin_state.json` (committed, `{}` initially),
  `scripts/syndicate/linkedin/.gitkeep` (committed sidecar-override dir), `tests/test_linkedin_payload.py`,
  `tests/test_linkedin.py`, `tests/test_cli_linkedin.py`, evidence files
  `docs/evidence/increment-syndication-06..09-linkedin-*.md`.
- **Changed (additive):** `scripts/syndicate/payload.py` (+`build_linkedin_share`), `generate.py`
  (+`linkedin_commentary`, +`resolve_linkedin_commentary`), `cli.py` (+`linkedin` subcommand,
  +`_linkedin_sidecar_dir`), `README.md` (+ LinkedIn section, token setup & sidecar-override how-to).
- **Unchanged:** all `content/`, the Hugo site, `devto`/`medium`/`teasers` behavior and their tests,
  `run.sh`, `requirements.txt`, `.gitignore`, `state.json`.
- **External:** creates public shares on the **owner's** LinkedIn profile **only** when run with a valid token
  and `--publish`. No infra. No migrations. No breaking changes.
- **Docs to update:** `scripts/syndicate/README.md` (in L3); this plan's §3c as-built notes (per gate).
