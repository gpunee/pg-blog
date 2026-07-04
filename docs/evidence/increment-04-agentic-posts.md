# Evidence — Increment 04: Agentic workflow posts (Java + Python)

- **Date:** 2026-07-03 · **Plan:** §3.4 + §3.2 rows 14–15 (APPROVED) · **Base:** `9f6848c` (uncommitted)
- **Implementer:** Sonnet subagent, briefed with **API patterns the orchestrator grounded from the bundled `claude-api` skill docs** (python/java README + tool-use); **orchestrator independently re-audited** the shipped code.

## Created
- `content/posts/14-building-agentic-workflows-in-java.md` — agent ladder + 4 gating checks, manual loop with MAX_ITERATIONS cap + input validation, `BetaToolRunner` path, `StructuredMessageCreateParams<PlanStep>` hand-off, safety/cost section; cross-links post 11.
- `content/posts/15-building-agentic-workflows-in-python.md` — parallel: manual `stop_reason == "end_turn"` loop with iteration cap, `@beta_tool` + `tool_runner`, `messages.parse(output_format=PlanStep)`, same safety/cost section; cross-links post 10.

## Acceptance (orchestrator's own run)
- Build **clean**, 15 posts.
- Post 14 → `categories/java/`, post 15 → `categories/python/`; both aggregate at `tags/agentic/` and `tags/ai/`; both post dirs exist.
- **Stale-API audit (orchestrator):** `budget_tokens`/`budgetTokens` → **none**; model literals are **only** `claude-opus-4-8` / `Model.CLAUDE_OPUS_4_8`; **no hardcoded keys** (`sk-ant`/`api_key="`/`apiKey("` → none).
- **API-correctness spot check:** Java uses `AnthropicOkHttpClient.fromEnv`, `ThinkingConfigAdaptive`, `BetaToolRunner`, `StructuredMessageCreateParams`, `ToolResultBlockParam`, `OutputConfig.Effort` — all matching the grounded skill patterns. Python uses `thinking={"type":"adaptive"}`, `messages.parse(output_format=...)`, `beta_tool`, `tool_runner`, `stop_reason`.
- All 3 Python blocks in post 15 `compile()` clean.

## Deviations
- Cross-links use Hugo's `{{< ref "…" >}}` shortcode (no prior post cross-linked; build resolves them with no warnings) — a *new* convention, additive.
- Post 14/15 front-matter field order is `title, description, date` vs siblings' `title, date, description` — functionally identical YAML, no build/behaviour effect. Noted, not corrected.
- Uncommitted (owner authorization pending).

Gate status: PASS. Increment 05 may start.
