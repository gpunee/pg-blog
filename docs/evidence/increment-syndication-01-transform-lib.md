# Evidence — Syndication Increment 01: core transform library

- **Date:** 2026-07-04 · **Plan:** `docs/plans/syndication.md` §3.1/3.3 (APPROVED) · **Base:** `bfab221` (uncommitted)
- **Implementer:** Sonnet subagent; **orchestrator independently re-ran pytest + real-post smoke.**

## Created (`scripts/syndicate/`)
- `posts.py` (`Post` dataclass, `find_repo_root`, `load_posts` — skips `search.md`/drafts, computes canonical), `transform.py` (`rewrite_cross_links`, `strip_shortcodes` code-fence-safe, `to_portable_markdown`), `tags.py` (`devto_tags` — alias map, order-preserving dedupe, ≤4).
- Tests: `test_transform.py`, `test_tags.py`, `test_posts.py` (added — `posts.py` is new logic, per §6.12).
- `requirements.txt` (`python-frontmatter`, `pytest`); gitignored `venv/`. `.gitignore` += `scripts/syndicate/venv/`, `.env`, `__pycache__/`, `*.pyc`.

## Acceptance (orchestrator's own run)
- `./venv/bin/pytest -q` → **19 passed**.
- Real-post smoke: **19 posts** load; **no `{{<`/`{{%` remains** in any transformed body; post 14 cross-link rewrites to absolute `https://pg-blogs.netlify.app/posts/11-…/`; canonical URLs correct; **all 19 posts yield ≤4 alphanumeric-only tags**.
- Sample tags eyeballed: post 1 → `[java,programming,backend,softwareengineering]`; post 8 → `[java,database,performance]`; post 12 → `[java,architecture,softwareengineering]`; post 14 → `[java,ai,llm]`.
- No `content/`/`hugo.toml`/`layouts/` touched; `venv/` never shows as untracked.

## Deviations (reviewed & accepted)
- Added `test_posts.py` (good — covers new logic). Added `__pycache__/`,`*.pyc` to `.gitignore` (hygiene). Cross-link rewrite also handles `{{% ref %}}` defensively. No lint/type tooling run (ruff/black/mypy not installed; only syntax-checked) — noted as a possible repo-wide follow-up.

Gate status: PASS. Syndication increment 02 may start.
