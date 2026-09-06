# Evidence — increment-syndication-06 · LinkedIn L1 (payload + commentary resolution)

> Continues the `increment-syndication-*` series (01–05 = the Dev.to/Medium/teasers effort).
> Plan `docs/plans/linkedin-syndication.md` §4.1 maps **06 = L1, 07 = L2, 08 = L3, 09 = live smoke**.

- **Date:** 2026-07-26
- **Plan:** `docs/plans/linkedin-syndication.md` (Status: APPROVED) — Increment L1
- **Base commit:** `4c429ee` (working tree; L1 changes uncommitted — deploy/commit is a separate owner-authorized step)
- **Model:** implementer = Sonnet; orchestrator re-ran the gate independently.

## Delivered
- `scripts/syndicate/payload.py` (+33 lines, purely additive) — `build_linkedin_share(post: Post, author_urn: str, commentary: str, visibility: str = "PUBLIC") -> dict`. Pure, no network; builds the ugcPosts ARTICLE share exactly per plan §3.3 and **always** appends `post.canonical_url` to the commentary text.
- `scripts/syndicate/generate.py` (+30 lines, purely additive) — `linkedin_commentary(post: Post) -> str` (generated fallback = `_linkedin_hook` text only, no canonical) and `resolve_linkedin_commentary(post: Post, sidecar_dir: Path) -> str` (§3.3.1 precedence: non-empty `sidecar_dir/<slug>.md` wins, else generated fallback). `sidecar_dir` is an injected param — no hardcoded path this increment.
- `scripts/syndicate/tests/test_linkedin_payload.py` (new) — 11 tests across all four L1 acceptance groups.

## Gate (orchestrator's own run — independent of the subagent report)
1. **Full test suite:** `cd scripts/syndicate && ./venv/bin/pytest -q` → **`82 passed in 0.45s`** (71 pre-existing + 11 new). Acceptance is demonstrated against running code — the 11 tests execute the real `build_linkedin_share` / `resolve_linkedin_commentary` / `linkedin_commentary`.
2. **Acceptance groups (plan §4 L1), all green:**
   - (1) exact ARTICLE dict shape (author, `lifecycleState:"PUBLISHED"`, ShareContent/media/`PUBLIC` visibility) + parametrized check that `shareCommentary.text` ends with `post.canonical_url` for varied commentary.
   - (2) non-empty `<slug>.md` sidecar in `tmp_path` → returned verbatim (≠ generated fallback).
   - (3) sidecar absent / empty / whitespace-only → generated fallback (3 tests) + `linkedin_commentary` never contains the canonical URL.
   - (4) `load_posts()` over all **35** real posts → builds without error, every share `shareMediaCategory == "ARTICLE"`.
3. **Additive-only invariant verified:** `git diff --stat` = `generate.py` +30 / `payload.py` +33, **0 deletions** → existing `teaser()` and `cli.py` provably untouched; `linkedin.py` not created (that is L2). Existing suite stays green.
4. **Static checks:** no ruff/mypy/pyproject configured for this package (confirmed repo-wide) — pytest is the full static+test gate, consistent with the prior `syndicate` increments.

## Grounding
- The ARTICLE-share payload shape is grounded in plan §3.3/§3.4, which the planner verified against LinkedIn's live docs (Microsoft Learn "Share on LinkedIn", 2026-07-26). No API shape written from memory. Nothing required stop-and-ask.

## Deviations
- **None behavioral.** One placement judgment call: the two new `generate.py` functions were appended after `teaser()` at the file bottom (rather than beside `_linkedin_hook`) to keep the diff strictly additive and avoid disturbing the existing teaser block. Placement only — no behavior change. Not a plan deviation; no plan-sync entry required.

## Gate status: PASS
Next: Increment L2 (`increment-syndication-07`) — `LinkedInClient`, network path, mocked tests.
