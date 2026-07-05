# Evidence — AI-Tooling Inc 05: Model Context Protocol (posts 28/29)

- **Date:** 2026-07-04 · **Plan:** `docs/plans/ai-tooling-series.md` §1(t5)/§3.1/§3.2/§3.3/§3.4/§3.5(t5)/§3a (APPROVED) · **Base:** `868aad8`
- **Implementer:** Sonnet subagent; **orchestrator independently re-ran the full §4.1 gate.** Live-doc-critical increment (MCP spec + SDKs).

## Delivered
- `content/posts/28-model-context-protocol-in-java.md` — 267 lines
- `content/posts/29-model-context-protocol-in-python.md` — 215 lines
- Scope: the M×N tool-glue problem MCP solves; a minimal MCP server (whitelisted lookup tool + read-only resource); a client consuming it; wiring MCP into the 14/15 agent loop; contrast with 26/27 framework tool abstractions; honest "MCP vs. direct tool" framing.

## Gate (orchestrator's own run)
1. **Build:** `hugo --gc --minify` → 133 pages, **no ERROR / no WARN / no REF**.
2. **Render + index:** 28, 29 render; both URLs in `public/index.json`.
3. **Taxonomy:** `/categories/{java,python}/` list the pair; `/tags/mcp/` resolves and lists both.
4. **Cross-links (backward-only):** 14/15 (tool-use) + 26/27 (framework tool abstraction) — one each, all existing; build no-REF confirms.
5. **Read-through:** fences pure (awk cross-idiom scan = 0). Secret grep empty. `claude-opus-4-8` used; **no `budget_tokens` in any code fence**. §3a central: untrusted-tool-arg validate/whitelist safe pattern shown + SQL-injection anti-pattern named (10 refs in post 28, 9 in post 29), mirroring 14/26.
6. **Regression:** `node test/search.test.js` → 4/4 pass.

## MCP grounding (implementer live-verified — critical deliverable)
Every MCP API cited a live URL: concepts + JSON-RPC `tools/list`/`tools/call` + transports (modelcontextprotocol.io/docs); **Python** `FastMCP`/`@mcp.tool()`/`@mcp.resource()`/`mcp.run` + `ClientSession`/`stdio_client` (github.com/modelcontextprotocol/python-sdk **v1.x stable branch** — confirmed main is v2-alpha, not recommended) + `langchain_mcp_adapters`; **Java** `McpServer`/`McpSyncServer`/`SyncToolSpecification`/`StdioServerTransportProvider`/`McpClient.sync` (github.com/modelcontextprotocol/java-sdk + `McpSchema.java` source, GAV `io.modelcontextprotocol.sdk:mcp-bom:2.0.0` released) + Spring AI MCP starters.

## Deviations (reviewed & accepted → plan-synced)
- **Java post 267 lines** > ~260 soft ceiling — same accepted rationale as Inc 04 (live-doc-critical topic with extra external API surface to demonstrate + cite; within the post-19/post-26 observed range).
- **MCP-schema → Anthropic `Tool.InputSchema` conversion** (Java "wiring into the loop" section) is the implementer's synthesis of two independently-grounded APIs (MCP `Tool.inputSchema()` map + the post-26 Anthropic `Tool.InputSchema.builder()` shape), not a single cited doc example; flagged in-post via comment. Low risk, kept out of the cited-API list. Accepted.
- Streamable-HTTP transport kept narrative (no code) — scope limited to stdio per brief; no verification risk.

Gate status: PASS. AI-Tooling increment 06 may start.
