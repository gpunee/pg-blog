# Syndicate

Publishes/syndicates the 19 blog posts under `content/posts/` to other platforms while keeping
`pg-blogs.netlify.app` as the canonical original (POSSE — Publish on Own Site, Syndicate
Elsewhere). See `docs/plans/syndication.md` for the full design.

- **Dev.to** — automated via its write API. Drafts by default; nothing goes live without
  `--publish`.
- **LinkedIn** — automated, personal-profile "Share" via the LinkedIn API (`syndicate linkedin`).
  Unlike Dev.to there is no draft state on LinkedIn's side: previewing is always network-free, and
  only `--publish` posts live.
- **Medium** — no write API exists, so this generates an import checklist instead
  (`syndicate medium`). Importing via Medium's own tool sets the story's canonical URL back to
  the original post, which is what we want for SEO.
- **Reddit / Hacker News** — not hosted copies, just distribution. `syndicate teasers`
  generates a per-post snippet with a suggested hook/title and the canonical link for each.

## Setup

```sh
cd scripts/syndicate
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## Usage

All commands can be run either from `scripts/` with `./venv/bin/python3 -m syndicate <command>`,
or from anywhere via the wrapper `scripts/syndicate/run.sh <command>` (it resolves its own
location, so it works regardless of your current directory).

### Dev.to

```sh
# Preview every payload (canonical URL, cleaned body, tags) with zero network calls:
scripts/syndicate/run.sh devto --all --dry-run

# Preview a subset by numeric filename prefix:
scripts/syndicate/run.sh devto --only 16,17 --dry-run

# Create/update as drafts on Dev.to (requires DEVTO_API_KEY):
scripts/syndicate/run.sh devto --all

# Go live (drafts are the default; this is the only way to publish):
scripts/syndicate/run.sh devto --all --publish
```

Set the API key first (never commit it):

```sh
export DEVTO_API_KEY="your-dev-to-api-key"
```

Re-running is idempotent: `state.json` tracks `slug -> devto_article_id` so a second run updates
existing articles instead of creating duplicates (with a canonical-URL match as a fallback if
`state.json` is ever lost).

### LinkedIn

Shares a short commentary + the canonical link to the **owner's personal LinkedIn profile** via the
"Share on LinkedIn" API (a `ugcPosts` ARTICLE share). LinkedIn's API has no draft concept, so this
command behaves a bit differently from Dev.to: **previewing never touches the network**, and
**only `--publish` makes a live call.**

```sh
# Preview every post's resolved commentary + canonical link, zero network calls:
scripts/syndicate/run.sh linkedin --all

# --dry-run is equivalent to the default (no --publish) — also zero network:
scripts/syndicate/run.sh linkedin --all --dry-run

# Preview a subset by numeric filename prefix:
scripts/syndicate/run.sh linkedin --only 16,17

# Post live to LinkedIn (requires LINKEDIN_ACCESS_TOKEN):
scripts/syndicate/run.sh linkedin --all --publish
```

Every preview run (default, or with `--dry-run`, with or without `--publish` also present) prints,
per post: the author URN, the post visibility, whether the commentary came from a **sidecar**
override or was **generated**, and the full resolved commentary text with the canonical link — then
ends with:

```
LinkedIn has no draft state; nothing was posted. Re-run with --publish to post live.
```

Set the API token first (never commit it):

```sh
export LINKEDIN_ACCESS_TOKEN="your-linkedin-access-token"
```

By default the author URN is resolved once per run via `GET /v2/userinfo` (OpenID Connect `sub`
claim). If you already know it, set it to skip that lookup:

```sh
export LINKEDIN_AUTHOR_URN="urn:li:person:XXXXXXXXXX"
```

**Overriding the auto-generated commentary:** create `scripts/syndicate/linkedin/<slug>.md` with your
own commentary text (no front matter, just the text you want posted — the canonical link is appended
automatically). If that file exists and is non-empty, it's used verbatim instead of the generated
hook; the preview always shows which source (`sidecar` vs `generated`) was used for a given post.

Re-running is idempotent: `linkedin_state.json` tracks `slug -> urn` for posts already shared, so a
second `--publish` run skips them (no duplicate create call) rather than re-posting. A post that
fails to share (bad request, malformed response, etc.) is **not** recorded, so it's retried on the
next `--publish` run.

### Medium

```sh
scripts/syndicate/run.sh medium
```

Writes `scripts/syndication/medium-import-list.md` — a checklist with every post's canonical URL
and the manual import steps. No network, no key required.

### Teasers (LinkedIn / Reddit / Hacker News)

```sh
scripts/syndicate/run.sh teasers
```

Writes one file per post to `scripts/syndication/teasers/<slug>.md`, each with a LinkedIn hook +
hashtags, a suggested Reddit title + subreddits, and a suggested Hacker News title — all carrying
the canonical link. No network, no key required.

## Tests

```sh
cd scripts/syndicate
./venv/bin/pytest -q
```
