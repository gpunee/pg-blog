# Evidence — AI-Tooling Inc 06: Evaluating LLM apps (posts 30/31) + back-fill 24/25

- **Date:** 2026-07-04 · **Plan:** `docs/plans/ai-tooling-series.md` §1(t6)/§3.1/§3.2/§3.3/§3.4(inc6+back-fill)/§3.5(t6)/§3a (APPROVED) · **Base:** `868aad8`
- **Implementer:** Sonnet subagent; **orchestrator independently re-ran the full §4.1 gate.**

## Delivered
- New: `content/posts/30-evaluating-llm-apps-in-java.md` (289 lines), `content/posts/31-evaluating-llm-apps-in-python.md` (283 lines).
- **Back-fill (§3.4):** one sentence + `{{< ref >}}` forward link added into `24-…-java.md` (→30) and `25-…-python.md` (→31), after the retrieval-metrics table ("these grade retrieval only; for evaluating the generated answer, see Evaluating LLM apps"). Only existing posts touched.
- Scope: golden/eval datasets, programmatic assertions vs. LLM-as-judge (grounded structured Claude call), regression gates in CI (GitHub Actions), deterministic-core testing, honest caveats (judge bias, eval drift).

## Gate (orchestrator's own run)
1. **Build:** `hugo --gc --minify` → 135 pages, **no ERROR / no WARN / no REF**.
2. **Render + index:** 30, 31 render; both URLs in `public/index.json` (31 posts total).
3. **Taxonomy:** `/categories/{java,python}/` list the pair; **`/tags/evaluation/` aggregates 24/25/30/31**; **`/tags/testing/` aggregates 16/17/30/31** — both intended cross-topic joins.
4. **Back-fill verified directly:** 24 carries the `{{< ref "30…" >}}` link, 25 carries `{{< ref "31…" >}}` (1 each).
5. **Cross-links:** 30/31 → 10/11 (evaluate-output), 16/17 (testing), 24/25 (retrieval quality) — backward; plus back-fills 24→30, 25→31 (targets now exist) — all resolve (build no-REF).
6. **Read-through:** fences pure (awk cross-idiom scan = 0). Secret grep empty; no `budget_tokens` in code; `claude-opus-4-8` used. LLM judge treats the judged output as untrusted data (§3a).
7. **Regression:** `node test/search.test.js` → 4/4 pass.

## Grounding
- LLM-as-judge SDK call reused the approved structured-output shape from posts 10/11 (`messages.parse`/`output_format` Python; `StructuredMessageCreateParams` Java), cross-checked vs. the bundled `claude-api` skill (adaptive thinking, no `budget_tokens`). GitHub Actions syntax (`actions/checkout@v4`, `setup-java@v4`, `setup-python@v5`) is stable schema, not in the live-doc-critical set — used as-is.

## Deviations (reviewed & accepted → plan-synced)
- **Length 289/283 > ~260 soft ceiling** (exemplar post 16 = 269): topic requires five facets (datasets, two scoring methods, CI wiring, deterministic-core testing, caveats). Implementer trimmed CI YAML from two jobs to one (~18 lines) rather than drop a required element. Accepted; flagged not silent.

Gate status: PASS. AI-Tooling increment 07 may start.
