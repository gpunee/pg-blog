# Evidence — AI-Tooling Inc 04: LLM frameworks vs. the raw SDK (posts 26/27)

- **Date:** 2026-07-04 · **Plan:** `docs/plans/ai-tooling-series.md` §1(t4)/§3.1/§3.2/§3.3/§3.4/§3.5(t4)/§3a (APPROVED) · **Base:** `868aad8`
- **Implementer:** Sonnet subagent; **orchestrator independently re-ran the full §4.1 gate.** Highest-verification increment (external framework APIs).

## Delivered
- `content/posts/26-llm-frameworks-vs-the-raw-sdk-in-java.md` — 285 lines (raw SDK + LangChain4j + Spring AI)
- `content/posts/27-llm-frameworks-vs-the-raw-sdk-in-python.md` — 244 lines (raw SDK + LangChain `bind_tools` + `create_agent`)
- Same small agent (weather + whitelisted-arithmetic calculator) built each way; honest "when the framework earns its weight" framing.

## Gate (orchestrator's own run)
1. **Build:** `hugo --gc --minify` → 129 pages, **no ERROR / no WARN / no REF**.
2. **Render + index:** 26, 27 render; both URLs in `public/index.json` (27 posts total).
3. **Taxonomy:** `/categories/{java,python}/` list the pair; new tag pages `/tags/langchain4j/`, `/tags/spring-ai/`, `/tags/langchain/` all resolve and list the posts.
4. **Cross-links (backward-only):** 14/15 (same agent raw, ×3 each) + 20/21 (RAG, ×1 each) — all existing; build no-REF confirms.
5. **Read-through:** fences pure (awk cross-idiom scan = 0). Secret grep empty. `claude-opus-4-8`/`Model.CLAUDE_OPUS_4_8` used; **no `budget_tokens` inside any code fence** (only prose). Untrusted tool-arg handling mirrors 14/15 (whitelist, no interpolation).
6. **Regression:** `node test/search.test.js` → 4/4 pass.

## Framework API grounding (implementer live-verified — the critical deliverable here)
Every framework API cited a live URL: **LangChain** `ChatAnthropic`/`bind_tools`/`@tool`/`ToolMessage` (python.langchain.com/docs/integrations/chat/anthropic), `create_agent` (docs.langchain.com/oss/python/langchain/agents); **LangChain4j** `@Tool`/`@P`/`AiServices`/`AnthropicChatModel` (docs.langchain4j.dev + GitHub source, GAV `dev.langchain4j:langchain4j-anthropic:1.17.1`); **Spring AI** `@Tool`/`ChatClient`/`AnthropicChatModel` (docs.spring.io/spring-ai). LangGraph kept **narrative only** (positioned as the runtime under `create_agent`) — no ungrounded graph code shown.

## Deviations (reviewed & accepted → plan-synced)
- **Java post 285 lines** > ~260 soft ceiling but < observed max (post 19 = 289): the brief required LangChain4j *and* Spring AI = three code paths. Accepted (clarity over trimming a verified snippet).
- **LangChain4j `thinkingType("adaptive")` is an inference**, not a copied doc example — docs confirm the `thinkingType` param + adaptive support but the only full code sample used `"enabled"`+budget. Implementer made the inference explicit in the post's prose (grounded on the raw Anthropic `"type":"adaptive"` value). Accepted as transparent; low risk. **Note for future edits:** if a live LangChain4j adaptive example surfaces, reconcile.
- Spring AI calculator tool references the LangChain4j `calculate()` body ("same whitelisted-operation body as above") instead of repeating it — length control; full validated logic shown once. Accepted.

Gate status: PASS. AI-Tooling increment 05 may start.
