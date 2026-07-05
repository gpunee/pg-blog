# Evidence — AI-Tooling Inc 07: Prompt caching & cost control (posts 32/33)

- **Date:** 2026-07-04 · **Plan:** `docs/plans/ai-tooling-series.md` §1(t7)/§3.1/§3.2/§3.3/§3.4/§3.5(t7)/§3a (APPROVED) · **Base:** `868aad8`
- **Implementer:** Sonnet subagent (+ one orchestrator-directed follow-up to tighten the Java Batches section); **orchestrator independently re-ran the full §4.1 gate.**

## Delivered
- `content/posts/32-prompt-caching-and-cost-control-in-java.md` — 249 lines
- `content/posts/33-prompt-caching-and-cost-control-in-python.md` — 260 lines
- Scope: token economics, `cache_control` prompt caching (breakpoints on system/tools/messages) with the `cache_read_input_tokens`/`cache_creation_input_tokens` hit-check, the Batches API for bulk work, and cheap→strong model routing.

## Gate (orchestrator's own run)
1. **Build:** `hugo --gc --minify` → 139 pages, **no ERROR / no WARN / no REF**.
2. **Render + index:** 32, 33 render; both URLs in `public/index.json` (33 posts total).
3. **Taxonomy:** `/categories/{java,python}/` list the pair; `/tags/cost/` and `/tags/performance/` both list 32/33.
4. **Cross-links (backward-only):** 32→11, 33→10 (§3.4 Inc-7 set) — resolve (build no-REF).
5. **Read-through:** fences pure (awk cross-idiom scan = 0). Secret grep empty; **no `budget_tokens` in code**; `claude-opus-4-8` + `claude-haiku-4-5` (routing) used. `cache_read_input_tokens`/`cache_creation_input_tokens` (Py) and `cacheReadInputTokens`/`cacheCreationInputTokens` (Java) shown correctly across the write-then-read lifecycle.
6. **Regression:** `node test/search.test.js` → 4/4 pass.

## Grounding
- Prompt caching + usage fields grounded in `claude-api` `shared/prompt-caching.md` + language READMEs; Python Batches in `python/claude-api/batches.md`; model IDs/pricing in `shared/models.md`.
- **Java Batches API:** the bundled skill has no `java/.../batches.md`; the implementer correctly **refused to fabricate** the builder and left it narrative. The **orchestrator then live-verified** the exact shape from the official `anthropic-sdk-java` example (`anthropic-java-example/src/main/java/com/anthropic/example/BatchExample.java`, main branch, via WebFetch) and directed a follow-up edit: post 32 now shows a grounded `BatchCreateParams.builder().addRequest(BatchCreateParams.Request.builder().customId(...).params(BatchCreateParams.Request.Params.builder()...))` → `client.messages().batches().create(...)` → `retrieve(BatchRetrieveParams...)` → `resultsStreaming(BatchResultsParams...)` example. This is the AI/ML "ground in real sources, never recall" rule applied end-to-end.

## Deviations (reviewed & accepted → plan-synced)
- Java Batches example pins `Model.CLAUDE_HAIKU_4_5` (the section's scenario is bulk classification; prose states batches work identically across models, so it doesn't contradict the Opus pin). `processingStatus()` terminal-state check kept in prose (exact enum constant not independently confirmed). Accepted.
- Implementer removed a 33→21 cross-link it had briefly added, to match §3.4 exactly. (Note: a 33→21 caching-of-RAG-context link is a reasonable *forward-consistent* backward link since 21 exists; it was removed to stay literal to the plan table — harmless either way.)

Gate status: PASS. AI-Tooling increment 08 may start.
