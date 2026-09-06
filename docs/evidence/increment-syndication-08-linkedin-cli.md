# Evidence — increment-syndication-08 · LinkedIn L3 (`linkedin` CLI subcommand)

> Plan `docs/plans/linkedin-syndication.md` §4.1: **08 = L3**. Continues the `increment-syndication-*` series. Final code increment (09 = owner-run live smoke).

- **Date:** 2026-07-26
- **Plan:** `docs/plans/linkedin-syndication.md` (Status: APPROVED) — Increment L3
- **Base commit:** `4c429ee` (working tree; L1+L2+L3 changes uncommitted — deploy/commit is a separate owner-authorized step)
- **Model:** implementer = Sonnet; orchestrator re-ran the whole gate and read the code/tests/README independently.

## Delivered
- `scripts/syndicate/cli.py` (modified, **additive**) — `linkedin` subparser + `cmd_linkedin`, plus helpers `_linkedin_state_path()`, `_linkedin_sidecar_dir()`, `_linkedin_commentary_source()`, `_preview_author_urn()`, `_print_linkedin_preview()`. `cmd_devto`/`cmd_medium`/`cmd_teasers` bodies untouched.
  - **Preview (default, or `--dry-run`, incl. `--publish --dry-run`) — zero network:** `LinkedInClient` is never constructed on this branch (structural, not conditional). Prints per post: author URN (`LINKEDIN_AUTHOR_URN` env or the `urn:li:person:<resolved-at-publish-time>` placeholder), visibility, commentary **source** (`sidecar`/`generated`), and the full resolved commentary + canonical (via `build_linkedin_share`). Footer: `LinkedIn has no draft state; nothing was posted. Re-run with --publish to post live.`
  - **Live (`--publish`) — §3.5 steps 1–5:** token guard (no token → exit 1, zero network) → `_confirm_live_publish(..., platform="LinkedIn")` (non-TTY without `--yes` refuses) → per post: skip if slug already in `linkedin_state.json` (no create call), else resolve `author_urn` **lazily once** (env, else `get_person_urn()`), `build_linkedin_share` → `create_ugc_post`, `save_state` **only after** a confirmed URN. Summary: `Shared: N, skipped(already): M, failed: K.`
  - **Error handling (§3.2/§3.5 L2 as-built):** the create call is wrapped in `except (LinkedInError, RuntimeError)` — a non-2xx (`LinkedInError`) **and** a malformed-success 201 missing `X-RestLi-Id` (`RuntimeError`) both count as `failed`, print `[slug] FAILED: …`, and continue; state stays clean because it's written only after a good URN.
- `scripts/syndicate/README.md` (modified, additive) — new **LinkedIn** section: command usage, `LINKEDIN_ACCESS_TOKEN`/`LINKEDIN_AUTHOR_URN` env setup (token shown as a placeholder — no real value written), sidecar-override how-to, idempotency behavior. Intro bullet list moved LinkedIn out of the teasers-only bucket into its own automated entry.
- `scripts/syndicate/linkedin_state.json` (new) — exactly `{}` (committed initial idempotency map, `slug → urn`; holds only public URNs, no secrets).
- `scripts/syndicate/linkedin/.gitkeep` (new) — tracks the committed sidecar override dir (under `scripts/syndicate/`, NOT the gitignored `scripts/syndication/`).
- `scripts/syndicate/tests/test_cli_linkedin.py` (new) — 17 mock-network tests; `ExplodingLinkedInClient` proves the preview path never constructs a client, `FakeLinkedInClient` programmable per test; state-path + sidecar-dir monkeypatched to `tmp_path` so the committed `linkedin_state.json` is never mutated.

## Gate (orchestrator's own run — independent of the subagent report)
1. **Full suite:** `cd scripts/syndicate && ./venv/bin/pytest -q` → **`111 passed in 0.54s`** (94 pre-existing incl. L1+L2 + 17 new). The pre-existing `test_cli.py` devto tests staying green proves `cmd_devto`/`_confirm_live_publish` are behaviorally unchanged by the added `platform` kwarg.
2. **Acceptance (plan §4 L3), against running code, zero network:** `./run.sh linkedin --all --dry-run` → exit 0, **35** `^\[slug\]` preview lines (`grep -c` = 35), footer present exactly once. Head/tail:
   ```
   [1-why-java-still-matters-today] author=urn:li:person:<resolved-at-publish-time> visibility=PUBLIC source=generated
   With Go, Rust, Python, and JavaScript dominating headlines, is Java still relevant? … including the mistakes that are easy to make and expensive to unwind.

   https://pg-blogs.netlify.app/posts/1-why-java-still-matters-today/
   …
   https://pg-blogs.netlify.app/posts/35-guardrails-for-llm-apps-in-python/

   LinkedIn has no draft state; nothing was posted. Re-run with --publish to post live.
   ```
   (Zero-network is enforced structurally *and* by the test suite: every preview test injects `ExplodingLinkedInClient`, whose construction raises — a network touch would have failed the 111.)
3. **§4-L3 acceptance points, each pinned by a test (17 total):** default + `--dry-run` + `--publish --dry-run` all zero-network with footer; sidecar `<slug>.md` → `source=sidecar` verbatim, absent → `source=generated`; `--only` numeric-prefix filter + unknown prefix → "No posts selected."; already-in-state slug → skipped, no create call; `--publish` no token → exit 1 zero network; non-TTY no `--yes` → refuse; `--publish --yes` → exactly one `create_ugc_post`, URN recorded in state; mixed `LinkedInError` + malformed-success `RuntimeError` → both `failed`, batch continues, state holds only successes; `LINKEDIN_AUTHOR_URN` set → 0 `get_person_urn` calls, unset → exactly 1 for the batch.
4. **Additive-only proof (repo root):** `git status --porcelain` shows tracked-modified = only `README.md`, `cli.py` (L3) + `generate.py`, `payload.py` (L1); `linkedin.py`, `linkedin/`, `linkedin_state.json`, the three `test_linkedin*` files, plan + evidence are `??` untracked-new. `git check-ignore` on the new linkedin paths → none ignored (sidecar dir is correctly under the tracked `scripts/syndicate/` tree, not the gitignored `scripts/syndication/`).
5. **State + fixtures verified:** `linkedin_state.json` = `{}`; `scripts/syndicate/linkedin/.gitkeep` present (0 bytes).
6. **Secrets:** README token line is a placeholder (`your-linkedin-access-token`); no token value in any file/log. `LINKEDIN_ACCESS_TOKEN` read env-only via `LinkedInClient`; `linkedin_state.json` holds only public URNs.
7. **Static checks:** no ruff/black/mypy/CI configured for this subproject (re-confirmed) — pytest is the whole gate, consistent with increments 01–07; the file parses and matches neighbor conventions.

## Deviations / judgment calls
1. **`_confirm_live_publish` generalized in place** with `platform: str = "Dev.to"` (new keyword-defaulted param) rather than a wrapper. `cmd_devto` doesn't pass it → its prompt wording is byte-for-byte unchanged (devto tests green); `cmd_linkedin` passes `platform="LinkedIn"`. Chosen over a wrapper to avoid duplicating the TTY/`--yes` logic. Additive; recorded as an as-built plan note via plan-sync.
2. **`--publish --dry-run` resolves to preview** (`if args.dry_run or not args.publish:`) — the plan enumerated the "no `--publish`" and "`--publish`" branches but not the combination; resolved toward the safer network-free reading, matching devto's `--dry-run` precedence. Pinned by `test_dry_run_with_publish_flag_still_previews_zero_network`. Recorded as an as-built note.
3. **Author URN resolved lazily** — on the first post that actually needs sharing (after the skip check), not eagerly before the loop — so an all-already-shared batch makes zero `get_person_urn` calls. Consistent with the plan's "once per run, cached" language; pinned by the two author-URN tests. Recorded as an as-built note.

## Gate status: PASS
Next: Increment L0 (owner preflight — create LinkedIn app, add "Share on LinkedIn" product, mint token, `export LINKEDIN_ACCESS_TOKEN`) → then increment-syndication-09 (owner-run live smoke: `run.sh linkedin --only NN --publish` on one post, verify the share + URN in `linkedin_state.json`). Both are owner actions; the tool is code-complete and gated PASS through L3.
