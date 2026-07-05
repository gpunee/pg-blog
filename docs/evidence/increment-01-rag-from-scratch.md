# Evidence — AI-Tooling Inc 01: RAG from scratch (posts 20/21)

- **Date:** 2026-07-04 · **Plan:** `docs/plans/ai-tooling-series.md` §1(t1)/§3.1/§3.2/§3.3/§3.4/§3.5(t1)/§3a (APPROVED) · **Base:** `868aad8`
- **Implementer:** Sonnet subagent; **orchestrator independently re-ran the full §4.1 gate** (build + acceptance greps + read-through). A sub-agent report is a hypothesis — every line below is the orchestrator's own captured output.

## Delivered (2 posts, no other files)
- `content/posts/20-rag-from-scratch-in-java.md` — 384 lines (Java; anchor post, longer per OQ-1)
- `content/posts/21-rag-from-scratch-in-python.md` — 318 lines (Python)
- Scope covered: fixed-size chunking w/ overlap, embeddings via dedicated provider, from-scratch cosine-similarity + top-k vector store, reranking pass, grounded generation, "retrieved content is untrusted input" (§3a), a deterministic-core testing section, and a "RAG vs. bigger context window" trade-off table.

## Gate (orchestrator's own run)
1. **Build:** `hugo --gc --minify` → **113 pages, no ERROR / no WARN / no REF** (grep of full output for `error|warn|ref|dangling` = 0 matches).
2. **Render:** `public/posts/20-…/index.html` and `public/posts/21-…/index.html` both exist.
3. **Search index:** both URLs present in `public/index.json` (`posts/20-rag-from-scratch-in-java/`, `posts/21-rag-from-scratch-in-python/`).
4. **Taxonomy:** `/categories/java/` lists 20, `/categories/python/` lists 21; `/tags/rag/` and `/tags/embeddings/` exist and list the pair.
5. **Cross-links (backward-only):** refs resolve to existing posts only — 10/11 (grounding), 14/15 (agentic); no forward ref (the "→ Making RAG accurate" back-fill into 20/21 is deferred to Inc 03 per §3.4). Build's no-REF-warning result confirms all resolve.
6. **Front matter:** valid (build would fail otherwise); `categories` matches language; tags per §3.3.
7. **Read-through:**
   - Language fences pure: 9 ```java in post 20, 9 ```python in post 21; awk scan for cross-language idioms (`def`/`self`/`elif` in java, `public class`/`System.out`/`new X` in python) = 0 hits.
   - SDK shape: Python `"claude-opus-4-8"` + `thinking={"type":"adaptive"}`; Java `Model.CLAUDE_OPUS_4_8` + `ThinkingConfigAdaptive`. **`budget_tokens` appears only in explanatory prose ("No budget_tokens here — …"), never in code.**
   - Embeddings grounded, not invented: **no `anthropic.embeddings`/`client.embeddings` call**; posts explicitly state Anthropic has no embeddings endpoint and use Voyage AI. Voyage grounding live-verified by the implementer against `platform.claude.com/docs/.../embeddings.md` (HTTP 200) and the `voyageai-python` SDK source.
   - Secret-shape grep (`sk-ant`, hardcoded `ANTHROPIC_API_KEY=`/`VOYAGE_API_KEY=`, `password=`) = **empty**; all samples read keys from env.
8. **Regression:** `node test/search.test.js` → 4/4 pass (new posts didn't disturb the index shape).

## Deviations (reviewed & accepted → plan-synced)
- **Voyage `voyage-4`** used (not the brief's illustrative `voyage-3`): the live embeddings doc lists `voyage-4` as current-generation, `voyage-3.5` as previous — brief explicitly said verify-live over the example. Accepted.
- **Java uses a plain `java.net.http.HttpClient`** call to Voyage `/v1/embeddings` + `/v1/rerank` (Voyage has no official Java SDK — confirmed by the live doc). Accepted; standard REST path.
- **Added a "Testing the Deterministic Core" section** to both posts — not named in §3.5 bullets but a natural §3b craft extension (test the model-free stages) and legitimate content toward the longer target. Judgment call, accepted.
- Java post 384 lines = 4 over the "~300–380" soft aim; substantive (the testing section), left as-is.

Gate status: PASS. AI-Tooling increment 02 may start.
