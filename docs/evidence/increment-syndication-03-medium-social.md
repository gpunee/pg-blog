# Evidence — Syndication Increment 03: Medium list + social teasers + wrapper

- **Date:** 2026-07-04 · **Plan:** `docs/plans/syndication.md` §3.1 (medium/teasers), §4 (APPROVED) · **Base:** `bfab221` (uncommitted)
- **Implementer:** Sonnet subagent; **orchestrator independently re-ran suite + regeneration.**

## Created / changed (`scripts/syndicate/`)
- `generate.py` (pure `medium_import_list`, `teaser` + helpers), `tests/test_generate.py` (10 tests), `run.sh` (repo-root wrapper, executable), `README.md` (usage). `cli.py` += `medium`/`teasers` subcommands; `test_cli.py` += 2 end-to-end tests.
- Output (regenerable, **untracked**): `scripts/syndication/medium-import-list.md`, `scripts/syndication/teasers/*.md` (19).

## Acceptance (orchestrator's own run)
- `./venv/bin/pytest -q` → **59 passed** (incl. inc 01–02).
- `run.sh medium` + `run.sh teasers` from **repo root** → succeed; Medium list has **19** canonical URLs; **19** teaser files.
- Teaser quality reviewed (post 16): LinkedIn hook + hashtags + canonical link; Reddit title + `r/java`,`r/programming` + etiquette note; HN title + link + "no Show HN for articles". All sections carry the canonical URL.
- Pure/local: ran with **no `DEVTO_API_KEY`**, no network.

## Deviations (reviewed & accepted)
- Output lands at `scripts/syndication/` (anchored to `__file__`, cwd-independent) rather than repo-root `syndication/` as §7 implied — more robust; noted for plan-sync. Generated files left untracked (regenerable; commit decision deferred to owner).
- CLI-level tests added (consistent with how `devto` is tested). No lint/type tooling (not installed).

Gate status: PASS. All three syndication increments complete.
