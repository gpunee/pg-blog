# Evidence — Syndication Inc 04 (Medium table fix): paste-ready checklist snippets

- **Date:** 2026-07-04 · **Plan:** `docs/plans/syndication.md` §8 (§8.1–§8.4) · **Base:** `868aad8` (syndication tool committed) + this session's uncommitted post work
- **Trigger:** owner report — Medium Import-by-URL renders the "Practical Checklist"/table sections blank (Medium has no table support). **Decision (Phase 3): surgical snippet approach** (keep import-by-URL; emit each post's tables as paste-ready bullet lists).
- **Implementer:** Sonnet subagent; **orchestrator independently re-ran the suite + regeneration + source-fidelity spot-checks.**

## Delivered (`scripts/syndicate/`)
- `transform.py`: `table_to_bullets(table_md)` (1-col → `- c1`; 2-col → `- **c1** — c2`; N-col → `- **c1** — <h2>: c2; <h3>: c3` with header labels; inline `**bold**`/`` `code` ``/links preserved), `extract_table_sections(body_md)` (tables in doc order + nearest preceding `##`/`###` heading; **fenced-code tables ignored** via the existing `_FENCED_CODE_RE` split).
- `generate.py`: `medium_checklist_snippets(post)` (title + `Canonical:` line + per-table `**heading**` + bullets; `""` when no tables); `medium_import_list` now warns Medium drops tables + revised step 4.
- `cli.py`: `medium` also writes `scripts/syndication/medium-checklists/<slug>.md` for every table-bearing post.
- `tests/`: +12 tests (transform 8, generate 3, cli 1).

## Gate (orchestrator's own run)
- **`./venv/bin/pytest -q` → 71 passed** (59 existing + 12 new).
- **`./run.sh medium`** → wrote `medium-import-list.md` (27 posts) + **23 checklist files** (matches the 23 table-bearing posts).
- **No stray pipes:** `grep -l '|' medium-checklists/*.md` = **0 files**.
- **Fidelity spot-checks (orchestrator, against source):**
  - Post 10 "Practical Checklist" (2-col) → 9 bullets, one per row, heading preserved, no pipes.
  - Post 23: the "HNSW | IVFFlat" table is genuinely 3-col (`| | HNSW | IVFFlat |`) → rendered `- **Build time** — HNSW: Slower; IVFFlat: Faster` (header labels correct); the "Dedicated Vector Store" table is 2-col (col2 = `**pgvector** — one system…`) → rendered `- **c1** — c2` correctly. **No column dropped in either.** Inline code/bold/links preserved verbatim.
- **Instructions:** import-list now carries the "Medium drops tables → paste from `medium-checklists/<slug>.md`" note + revised step 4.
- **Unchanged (verified):** no `content/`, `hugo.toml`, layout, or Dev.to-path edits; output confined to the gitignored `scripts/syndication/`.

## Deviations (reviewed & accepted)
- Headingless-table label rule (§8.1 left "which generic label when") resolved by implementer: `Checklist` if the post's only table is headingless, else `Table N`. Not exercised by the real corpus (every real table has a preceding heading); synthetic-test-only.
- No code-fenced table exists in the corpus, so fence-skip is covered by unit test only, not a real-post spot-check. Acceptable — the unit test is deterministic.
- No lint/type tooling in the project (pytest is the gate), consistent with prior increments.

Gate status: PASS. Owner can use it now: `scripts/syndicate/run.sh medium` → paste `scripts/syndication/medium-checklists/<slug>.md` bullets where a table imported blank.
