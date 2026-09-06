# Handoff — pg-blog LinkedIn syndication

**Last updated:** 2026-09-06
**Repo:** https://github.com/gpunee/pg-blog · **Live site:** https://pg-blogs.netlify.app/
**Plan:** `docs/plans/linkedin-syndication.md` (Status: **APPROVED**, 2026-07-26)

This document is the pick-up point for continuing the LinkedIn syndication work on a
**different machine**. It is deliberately self-contained: the project's local operating
manual (`/CLAUDE.md`) is **gitignored by owner decision** and will **not** be present after
a fresh clone, so everything needed to resume is written out here.

**To get the full instruction set on the new machine**, also clone the private workspace repo
`gpunee/claude-workspace-settings`, which carries:
- `CLAUDE.md` — the workspace **core** lifecycle manual (PLAN → ASK → CONFIRM → IMPLEMENT →
  VERIFY, the non-negotiables, the model-per-phase rules)
- `docs/project-manuals/pg-blog-CLAUDE.md` — a mirror of **this project's** manual, kept
  private on purpose; copy it back to `pg-blog/CLAUDE.md` after cloning (it stays untracked
  there)
- `.claude/agents/`, `.claude/skills/`, `.claude/hooks/` — the planner/implementer/scaffolder
  agents, the `/brief` `/gate` `/evidence` `/retro` `/plan-sync` skills, and the lifecycle
  guard hooks

---

## 1. TL;DR — where things stand

The `linkedin` subcommand is **code-complete and green**. Nothing has been posted to
LinkedIn yet: no LinkedIn app exists, no access token has been minted, and
`scripts/syndicate/linkedin_state.json` is still `{}`.

| Increment | What | Status |
|-----------|------|--------|
| **L0** | LinkedIn app + access token preflight (**owner action, no code**) | **NOT DONE — do this first** |
| **L1** | Payload builder + commentary resolution (pure, no network) | DONE · gate PASS |
| **L2** | `LinkedInClient` (network layer, mocked in tests) | DONE · gate PASS |
| **L3** | `linkedin` CLI subcommand + idempotency + sidecar + README | DONE · gate PASS |
| **Phase 5** | Live smoke — post one real share (**owner action**) | NOT DONE — blocked on L0 |

Evidence: `docs/evidence/increment-syndication-06-linkedin-payload.md` (L1),
`-07-linkedin-client.md` (L2), `-08-linkedin-cli.md` (L3). All three end `Gate status: PASS`.

---

## 2. What the tool does

POSSE-style syndication: the blog stays canonical, LinkedIn gets a share that links back.
For each of the 35 posts it publishes **one ARTICLE share to the owner's personal LinkedIn
profile** — a short professional hook followed by the canonical blog URL, which LinkedIn
renders as a link-preview card.

Design decisions already settled (do not re-litigate without the owner):

- **Target:** the owner's *personal profile*, not a Company Page.
- **Trigger:** one owner-run command. No automation, no scheduler, no CI hook.
- **Post text:** per-post override via a committed sidecar file, with a generated fallback.
- **Safety model:** mirrors the existing `devto` tool — preview is the default, live posting
  requires an explicit `--publish`.

### The critical LinkedIn difference from Dev.to

**LinkedIn has no draft state.** Dev.to can create an unpublished draft; LinkedIn cannot —
a `ugcPosts` call publishes immediately and visibly. The CLI is built around this:

- Default run (no flags) → **preview only, zero network calls**
- `--dry-run` → preview, zero network
- `--publish --dry-run` → **still preview** (`--dry-run` always wins, so the combination can
  never post)
- `--publish` → the only path that makes a live call, and it still requires an interactive
  confirmation (or `--yes`)

The preview path never even *constructs* a `LinkedInClient`; that is structural, not a
conditional, and is pinned by tests that inject a client whose constructor raises.

---

## 3. Resuming on a new machine

```sh
git clone https://github.com/gpunee/pg-blog.git
cd pg-blog

# Python tool setup (the venv is gitignored — recreate it)
cd scripts/syndicate
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# Verify the checkout is healthy — expect: 111 passed
./venv/bin/pytest -q

# Verify against running code — expect: 35 previews, zero network, exit 0
cd ../.. && ./scripts/syndicate/run.sh linkedin --all --dry-run
```

Requirements are just `python-frontmatter`, `pytest`, `requests`. No Docker, no database,
no services. Hugo is only needed to build the site itself, not for syndication.

**Not in the clone:** `/CLAUDE.md` (gitignored per owner — restore it from
`claude-workspace-settings/docs/project-manuals/pg-blog-CLAUDE.md`),
`scripts/syndicate/venv/`, `scripts/syndication/` (regenerable output), `/public/`,
`/resources/`.

---

## 4. Next action — Increment L0 (owner, no code)

In the **LinkedIn Developer Portal** (https://www.linkedin.com/developers/apps):

1. **Create an app.** LinkedIn requires it to be associated with a Company Page — that page
   is only an administrative owner of the app; shares still go to the personal profile.
2. **Add the "Share on LinkedIn" product** → grants the `w_member_social` scope. This is the
   scope that actually posts.
3. *(Optional but recommended)* **Add "Sign In with LinkedIn using OpenID Connect"** →
   grants `openid profile`, which lets the tool resolve the author URN itself via
   `GET /v2/userinfo`. Skip it only if you intend to supply `LINKEDIN_AUTHOR_URN` by hand.
4. **Mint a member access token** using the portal's **Token Generator** with those scopes.
5. **Export it into your shell** (never into a file — see §7):

```sh
export LINKEDIN_ACCESS_TOKEN="<the token>"
# Optional: skips the userinfo lookup entirely
export LINKEDIN_AUTHOR_URN="urn:li:person:<your-member-id>"
```

**Token lifetime:** LinkedIn member access tokens last roughly **60 days**, and standard
apps get **no refresh token** — when it expires, mint a new one through the Token Generator
and re-export. The `client_id`/`client_secret` stay with the owner; the tool never sees them.

**L0 acceptance:** a preview run works and the tool reports the token as present. Record
this in evidence when done (it is the immediate predecessor of the live smoke).

---

## 5. Then — Phase 5 live smoke

Do **one post first**, verify it on the profile, then decide about the rest.

```sh
# 1. Preview the single post you're about to publish
./scripts/syndicate/run.sh linkedin --only 1 --dry-run

# 2. Publish it for real (interactive confirmation prompt)
./scripts/syndicate/run.sh linkedin --only 1 --publish

# 3. Verify: the share is on your profile, and the URN was recorded
cat scripts/syndicate/linkedin_state.json
```

Expected after step 2: `[1-why-java-still-matters-today] shared (urn=urn:li:share:…)` and a
matching `slug → urn` entry in `linkedin_state.json`.

Only after that looks right:

```sh
./scripts/syndicate/run.sh linkedin --only 2,3,4 --publish   # subsets, or
./scripts/syndicate/run.sh linkedin --all --publish          # all remaining
```

**Idempotency:** any slug already in `linkedin_state.json` is skipped with no API call, so
re-running `--all` will not double-post. Commit `linkedin_state.json` after a publish run —
that file *is* the record of what has been shared.

Write the result up as `docs/evidence/increment-syndication-09-linkedin-live-smoke.md`.

**Posting 35 shares at once is a judgment call, not a technical limit** — consider spacing
them out so the profile feed does not read as a bulk dump.

---

## 6. Customising the post text

Each share's commentary comes from one of two sources, and the CLI labels which one it used
(`source=sidecar` or `source=generated`) in every preview line.

- **Generated fallback** — derived from the post's own description. Fine, but generic.
- **Sidecar override** — create `scripts/syndicate/linkedin/<slug>.md` containing exactly
  the text you want. Non-empty file wins; the canonical URL is appended automatically, so
  **do not** include the link yourself.

```sh
echo "Java's not dead — here's what 20 years of it taught me about picking a stack." \
  > scripts/syndicate/linkedin/1-why-java-still-matters-today.md
./scripts/syndicate/run.sh linkedin --only 1 --dry-run   # confirm: source=sidecar
```

Sidecars are committed on purpose — they are owner-authored content, and they live under the
tracked `scripts/syndicate/linkedin/` directory, **not** the gitignored `scripts/syndication/`
output tree. (Those two similar names are a real foot-gun; the tracked one ends in `-ate`.)

---

## 7. Security constraints (carry these forward)

1. **Never write a token into any file, log, echo, or inline command** — not even a rotated
   or expired one. `LINKEDIN_ACCESS_TOKEN` is read from the environment only.
2. The OAuth `client_id`/`client_secret` never enter the tool.
3. `linkedin_state.json` holds **only public share URNs**. No secrets belong there.
4. `LinkedInError` is constructed so it can never carry the token into a message or log —
   there is a test asserting exactly this (`tests/test_linkedin.py`).
5. The `AQV-super-secret-linkedin-token-do-not-leak` string in the test suite is a
   **deliberately fake fixture** used to prove #4. It is not a credential.
6. Live publishing happens only on an explicit owner go-ahead. A non-TTY run without `--yes`
   refuses rather than silently auto-publishing.

---

## 8. File map

**New (LinkedIn feature):**

| Path | What |
|------|------|
| `scripts/syndicate/linkedin.py` | `LinkedInClient` — env-only token, retry loop, `create_ugc_post`, `get_person_urn`; `LinkedInError` |
| `scripts/syndicate/linkedin_state.json` | Idempotency map `slug → urn`. Currently `{}` |
| `scripts/syndicate/linkedin/.gitkeep` | Tracks the committed sidecar-override directory |
| `scripts/syndicate/tests/test_linkedin_payload.py` | L1 tests |
| `scripts/syndicate/tests/test_linkedin.py` | L2 tests (mocked HTTP) |
| `scripts/syndicate/tests/test_cli_linkedin.py` | L3 tests (17, mocked network) |
| `docs/plans/linkedin-syndication.md` | The approved plan, with as-built notes |
| `docs/evidence/increment-syndication-0{6,7,8}-*.md` | Per-increment evidence |

**Modified (all additive — no existing behaviour changed):**

| Path | Change |
|------|--------|
| `scripts/syndicate/cli.py` | `linkedin` subparser + `cmd_linkedin` + helpers. `cmd_devto`/`cmd_medium`/`cmd_teasers` bodies untouched |
| `scripts/syndicate/payload.py` | `build_linkedin_share()` |
| `scripts/syndicate/generate.py` | `linkedin_commentary()`, `resolve_linkedin_commentary()` |
| `scripts/syndicate/README.md` | LinkedIn usage section |

The one shared function that changed is `_confirm_live_publish()`, which gained a
`platform: str = "Dev.to"` keyword parameter. `cmd_devto` does not pass it, so its prompt
wording is byte-for-byte unchanged — the pre-existing Dev.to tests staying green is the proof.

---

## 9. LinkedIn API facts (verified against Microsoft Learn docs, 2026-07-26)

Re-check these if something 4xxs — LinkedIn moves its API surface periodically.

- `POST https://api.linkedin.com/v2/ugcPosts` with header `X-Restli-Protocol-Version: 2.0.0`
- **The new post's URN comes back in the `X-RestLi-Id` response header, not the body.** A 201
  without that header is treated as a failure (a `RuntimeError`, counted as `failed`).
- ARTICLE share shape: `specificContent["com.linkedin.ugc.ShareContent"]` with
  `shareCommentary.text`, `shareMediaCategory: "ARTICLE"`, and
  `media[].{status: "READY", originalUrl, title.text, description.text}`;
  `visibility["com.linkedin.ugc.MemberNetworkVisibility"] = "PUBLIC"`.
- Author URN: `GET /v2/userinfo` → `sub` → `urn:li:person:{sub}`.

---

## 10. Gotchas and known nits

- **`scripts/syndicate/README.md` says "the 19 blog posts"** — stale, there are now **35**.
  Harmless doc wording; left unfixed to keep this commit scoped to the LinkedIn feature.
- **This subproject has no linter, formatter, type checker, or CI.** `pytest` is the entire
  gate. Do not report a lint pass that did not happen.
- **Running the CLI:** use `scripts/syndicate/run.sh <cmd>` from anywhere — that wrapper
  resolves its own location and is the reliable form. The module form is fiddly: from
  `scripts/` it is `./syndicate/venv/bin/python3 -m syndicate <cmd>` (the venv lives in
  `scripts/syndicate/`, not `scripts/`), and running it from inside `scripts/syndicate/`
  fails outright with `No module named syndicate`.
- **`README.md`'s "Usage" line documents the module form wrongly** — it says to run
  `./venv/bin/python3 -m syndicate` from `scripts/`, which exits 127 because no `venv`
  exists at that level. Verified 2026-09-06. Left unfixed to keep this commit scoped to the
  LinkedIn feature; worth a one-line fix next time README is touched.
- **Tests never touch the real `linkedin_state.json`** — the state path and sidecar dir are
  monkeypatched to `tmp_path`. Keep it that way.

---

## 11. Lifecycle notes

Work follows the workspace lifecycle: PLAN → ASK → CONFIRM → IMPLEMENT → VERIFY, with
per-increment evidence and an independent orchestrator gate re-run. Phase 3 (human
confirmation) already happened — the plan is APPROVED — so L0 and the live smoke are execution
steps, not re-planning ones.

Per-increment cadence if further code work is needed: `/brief` → implementer → `/gate` →
`/evidence` → `/retro` → `/plan-sync` → human checkpoint → context reset.

Evidence numbering for this feature: **06 = L1, 07 = L2, 08 = L3, 09 = live smoke.**
