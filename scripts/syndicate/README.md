# Syndicate

Publishes/syndicates the 19 blog posts under `content/posts/` to other platforms while keeping
`pg-blogs.netlify.app` as the canonical original (POSSE — Publish on Own Site, Syndicate
Elsewhere). See `docs/plans/syndication.md` for the full design.

- **Dev.to** — automated via its write API. Drafts by default; nothing goes live without
  `--publish`.
- **Medium** — no write API exists, so this generates an import checklist instead
  (`syndicate medium`). Importing via Medium's own tool sets the story's canonical URL back to
  the original post, which is what we want for SEO.
- **LinkedIn / Reddit / Hacker News** — not hosted copies, just distribution. `syndicate teasers`
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
