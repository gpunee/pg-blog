# Plan: AI-Tooling Blog Series — 8 Java+Python topic pairs (posts 20–35)

Status: APPROVED   <!-- approved by owner 2026-07-04 (Phase 3); build all 8 increments in order -->

**Phase-3 decisions (owner, 2026-07-04):** approve all 8 increments · **RAG-from-scratch posts 20/21 run longer/deeper** than the ~180–260 default (OQ-1) — the anchor topic gets room; the other pairs stay at house length · **all 8 topics are Java+Python pairs** (OQ-3 default kept, 16 posts) · Java-first ordering kept (OQ-2 default) · no companion repo (OQ-4 default) · no `tags.py` alias change (OQ-5 default).

## 1. Goal & Context

**Problem (restated):** The blog (`https://pg-blogs.netlify.app/`, Hugo + ananke, 19 posts)
covers foundational Java/Python engineering and an initial AI slice (reliable LLM apps 10/11,
agentic workflows 14/15). The owner wants to extend the AI track with **8 new AI-tooling topics**,
each written as a **Java + Python pair** — ~16 new posts — that match the existing posts' depth,
voice, front-matter shape, cross-linking, categories/tags, and search/syndication conventions
**exactly**, so the new content groups, searches, and syndicates with **zero infrastructure or
tooling change**.

**The 8 topics (fixed order — do not reorder):**
1. **RAG from scratch** — chunking, embeddings, vector search, reranking; when RAG beats a bigger context window.
2. **Vector databases in practice** — pgvector vs. dedicated stores; HNSW/IVFFlat indexing; recall-vs-latency. (Cross-link DB-indexing posts 18/19.)
3. **Making RAG accurate** — hybrid search, metadata filtering, chunking strategies, measuring retrieval quality.
4. **LLM frameworks vs. the raw SDK** — build the same agent both ways; when a framework earns its weight. (Python: LangChain/LangGraph; Java: LangChain4j / Spring AI.)
5. **MCP (Model Context Protocol)** — build a tool server and consume one.
6. **Evaluating LLM apps** — golden datasets, LLM-as-judge, regression tests in CI. (Cross-link testing posts 16/17.)
7. **Prompt caching & cost control** — token economics, caching, batching, model routing.
8. **Guardrails for LLM apps** — prompt-injection defense, PII redaction, output validation at the trust boundary.

**Serves:** readers of the live site browsing `/categories/{java,python}/`, `/tags/<topic>/`, and
using `/search/`; and the owner extending the AI content library and later syndicating via
`scripts/syndicate/`.

**Success criteria (measurable):**
- 16 new posts published, numbered **20–35**, one Markdown file each in `content/posts/`, filenames
  per §3.2, front matter per §3.3, bodies matching the existing posts' structure/voice/length
  (~180–260 lines / ~1,800–2,600 words, matching posts 10–19).
- Each post carries `categories: [Java]` **or** `[Python]` plus enriched `tags` from §3.3 so
  `/categories/*`, `/tags/*` term pages, and `/index.json` (search) pick them up with **no code
  change** (verified — see §3.6).
- The cross-link web in §3.4 renders (every `{{< ref >}}` resolves, build has no REF warnings).
- `hugo --gc --minify` builds clean after every increment; every new post appears in
  `public/index.json` and at its `/posts/NN-slug/` URL.
- All 19 existing post URLs unchanged; SDK code samples grounded in the bundled `claude-api` skill
  (not model memory); framework/protocol APIs (LangChain/LangGraph, Spring AI, LangChain4j, MCP)
  verified against live docs during implementation; **no real secrets/keys/PII in any post.**

**Non-goals / out of scope:**
- No runnable companion repos, no CI that executes post code, no changes to the Hugo theme,
  search JS, `[outputs]`, or `netlify.toml`.
- No changes to `scripts/syndicate/` behavior. Adding a few tag aliases to `scripts/syndicate/tags.py`
  is **optional polish** (§2 note), not part of the content deliverable — the slugify fallback
  already maps every new tag.
- No deploy/push. This plan stops at "merged locally, builds clean"; publishing to Netlify and
  syndicating are separate owner go-aheads (same posture as prior plans).
- No decision on whether any topic collapses to a single post — every topic is a Java+Python pair
  (see §2 open question OQ-3 if the owner wants an exception).

## 2. Assumptions & Open Questions

**Assumptions (safe/reversible):**
- **A-1 Numbering starts at 20.** Highest existing post is 19 (verified: `content/posts/` tops out
  at `19-…`). New posts are 20–35, contiguous, in topic order.
- **A-2 Java-first ordering within each pair** (even number = Java, odd = Python), matching the 3
  most-recent pairs (14 Java/15 Python, 16/17, 18/19). Reversible; see OQ-2 for the alternative.
- **A-3 Front matter mirrors existing posts** exactly: quoted `title`, unquoted ISO `date`,
  `description` (one sentence, used as SEO + search summary), `tags` (ordered list), `categories`
  (single-element list), `draft: false`. Field ordering per the existing posts (see §3.3).
- **A-4 Dates:** each post dated its implementation date (`date: 2026-07-04` or later), consistent
  with posts 10–19 all dated `2026-07-03`. Ordering on the site is by date then weight; contiguous
  same-day dates are fine (existing posts already share a date).
- **A-5 Cross-links use the `{{< ref "NN-slug.md" >}}` shortcode** (the repo convention adopted at
  posts 14/15/18/19). `ref` fails the build on a dangling target, which is *desirable* — it enforces
  the back-fill discipline in §3.4.
- **A-6 No search/template/config change is required** for new posts to be grouped/searchable —
  `layouts/index.json` emits every regular post in `mainSections`, and ananke auto-generates
  `/categories/*` and `/tags/*` term pages (grounded in `docs/plans/sections-tags-search.md` §3.2–3.3).
  The per-increment gate *verifies* this rather than assuming it.
- **A-7 Posts are illustrative prose with non-executed code samples** — no live API calls, no keys,
  no network, no companion repo. SDK snippets follow `claude-api` skill defaults; framework snippets
  are live-doc-verified minimal examples.
- **A-8 New tags map to Dev.to via `scripts/syndicate/tags.py`** — existing aliases (`AI→ai`,
  `LLM→llm`, `Anthropic→ai`, `Databases→database`, `Testing→testing`, `Performance→performance`,
  `SQL→sql`) cover the leading tags; new specific tags (`RAG`, `Embeddings`, `Vectors`, `MCP`,
  `Evaluation`, `Guardrails`, `Security`, `Cost`, `LangChain`, `LangChain4j`, `Spring AI`) fall
  through `_slugify` to valid lowercase-alnum tags. Since Dev.to keeps only the first 4 (language →
  discipline → specific), syndication maps cleanly with **no code change**.

**Open questions (Phase 2 — none are build-blocking; sensible defaults chosen so planning proceeds):**
- **OQ-1 — RESOLVED (owner, 2026-07-04): RAG-from-scratch posts 20/21 run longer/deeper** (aim
  ~300–380 lines / deeper worked examples); topics 2–8 stay at the ~180–260-line house length.
- **OQ-2 (non-blocking) — Pair ordering.** Default Java-first (A-2). The two *AI-foundation* pairs
  in the repo are Python-first (10 Python/11 Java) while the 3 most-recent pairs are Java-first.
  Confirm Java-first is acceptable, or flip to Python-first for this AI series.
- **OQ-3 — RESOLVED (owner, 2026-07-04): all 8 topics are Java+Python pairs** (16 posts, incl. MCP
  and prompt-caching). No single-post collapse.
- **OQ-4 (non-blocking) — Runnable repo links.** Default: none (self-contained snippets, per A-7).
  Confirm if the owner wants a linked GitHub sample repo (would add a maintenance surface and a
  §3a supply-chain note).
- **OQ-5 (non-blocking) — Update `scripts/syndicate/tags.py` aliases?** Default: no (slugify
  fallback suffices). If the owner wants curated Dev.to tags (e.g. `Embeddings→ai` instead of
  `embeddings`), that is a tiny separate change — flag, don't bundle.

## 3. Design (WHAT / HOW / WHY)

### 3.1 Approach & rationale
- **WHAT:** 16 original Markdown posts added under `content/posts/`, nothing else structural. Each
  post is authored prose in the established house style: `## Introduction` (with a `{{< ref >}}`
  link tying the topic to prior posts) → `---`-separated `##` sections mixing explanation with
  concise, idiomatic, *non-executed* Java or Python code (and SQL where relevant) → a
  `## Practical Checklist` (or `## Anti-Patterns`) table → `## Final Thoughts` / `## Practical
  Takeaways`. This is the exact spine of posts 10, 14, 18 (read as exemplars).
- **WHY pairs, one topic per increment:** mirrors the existing library (every discipline is a
  Java+Python pair) and gives an increment that is small, independently shippable, and leaves the
  site building — the CLAUDE.md §1 iterative model. A topic pair is the natural unit of review.
- **WHY no infra/tooling change:** the taxonomy + search + syndication machinery already treats any
  well-formed post generically (A-6, A-8). Adding structural machinery would violate YAGNI (§3c)
  and risk the frozen URLs / working search. Rejected alternative: a new `/ai/` section or an
  `ai-tooling` taxonomy — unnecessary; `categories` + `tags` already give both browse axes.
- **Implementation-invariant — grounding (mandatory, applies to every increment):**
  - **Anthropic SDK code is grounded in the bundled `claude-api` skill, never written from memory.**
    Invoke/read the skill's `python/claude-api` and `java/claude-api` docs (and `shared/`:
    `prompt-caching.md`, `tool-use.md`, `models.md`, `batches.md`) at implementation time. Required
    shape: **Python** `client.messages.create(model="claude-opus-4-8", thinking={"type":"adaptive"})`,
    `client.messages.parse(..., output_format=Model)`, `@beta_tool` / `tool_runner`; **Java**
    `Model.CLAUDE_OPUS_4_8`, `ThinkingConfigAdaptive`, `BetaToolRunner`, `StructuredMessageCreateParams`.
    **NO `budget_tokens` on Opus 4.8.** Keys via env only (`anthropic.Anthropic()` reads
    `ANTHROPIC_API_KEY`; `AnthropicOkHttpClient.fromEnv()`). This matches the as-built note in
    `sections-tags-search.md` §3.6 (inc 04).
  - **Framework/protocol APIs are verified against live docs at implementation time, not written
    from memory** — LangChain/LangGraph (Python), Spring AI + LangChain4j (Java), and the MCP spec.
    Their surfaces move fast; a snippet that looks plausible but is wrong is worse than none. If a
    live source can't be reached to confirm an API, **stop and ask** (§0) rather than guess. Use the
    `claude-api` skill's `shared/live-sources.md` as the pointer list where relevant.

### 3.2 Post numbering & filenames (exact)

Java-first per pair (A-2); kebab-case `NN-slug.md` matching the existing pattern.

| Topic | # | Filename | Lang |
|------|----|----------|------|
| 1 RAG from scratch | 20 | `20-rag-from-scratch-in-java.md` | Java |
| 1 RAG from scratch | 21 | `21-rag-from-scratch-in-python.md` | Python |
| 2 Vector databases in practice | 22 | `22-vector-databases-in-practice-for-java.md` | Java |
| 2 Vector databases in practice | 23 | `23-vector-databases-in-practice-for-python.md` | Python |
| 3 Making RAG accurate | 24 | `24-making-rag-accurate-in-java.md` | Java |
| 3 Making RAG accurate | 25 | `25-making-rag-accurate-in-python.md` | Python |
| 4 LLM frameworks vs. the raw SDK | 26 | `26-llm-frameworks-vs-the-raw-sdk-in-java.md` | Java |
| 4 LLM frameworks vs. the raw SDK | 27 | `27-llm-frameworks-vs-the-raw-sdk-in-python.md` | Python |
| 5 MCP (Model Context Protocol) | 28 | `28-model-context-protocol-in-java.md` | Java |
| 5 MCP (Model Context Protocol) | 29 | `29-model-context-protocol-in-python.md` | Python |
| 6 Evaluating LLM apps | 30 | `30-evaluating-llm-apps-in-java.md` | Java |
| 6 Evaluating LLM apps | 31 | `31-evaluating-llm-apps-in-python.md` | Python |
| 7 Prompt caching & cost control | 32 | `32-prompt-caching-and-cost-control-in-java.md` | Java |
| 7 Prompt caching & cost control | 33 | `33-prompt-caching-and-cost-control-in-python.md` | Python |
| 8 Guardrails for LLM apps | 34 | `34-guardrails-for-llm-apps-in-java.md` | Java |
| 8 Guardrails for LLM apps | 35 | `35-guardrails-for-llm-apps-in-python.md` | Python |

### 3.3 Front matter & tags (exact per post)

**Shape** (mirror existing posts; field order as posts 10/14/18 — `title`, `date`, `description`,
`tags`, `categories`, `draft`):
```yaml
---
title: "<Title Case, quoted>"
date: 2026-07-04
description: "<one-sentence SEO + search summary, ≤ ~30 words>"
tags:
  - <Language>          # Java or Python — first tag
  - <discipline/topic tags, ordered general → specific>
categories:
  - <Java|Python>       # single element, matches the language
draft: false
---
```

**Tag sets** (ordered language → discipline → specific; the first 4 become the Dev.to tags via
`scripts/syndicate/tags.py`). `categories` = the language. Titles are the author's to finalize but
should follow the existing naming (e.g. "… in Java" / "… for Python").

| # | Suggested title | categories | tags (ordered) |
|---|-----------------|-----------|----------------|
| 20 | RAG From Scratch in Java | Java | Java, AI, LLM, RAG, Embeddings, Anthropic |
| 21 | RAG From Scratch in Python | Python | Python, AI, LLM, RAG, Embeddings, Anthropic |
| 22 | Vector Databases in Practice for Java | Java | Java, AI, Databases, Vectors, RAG, Performance |
| 23 | Vector Databases in Practice for Python | Python | Python, AI, Databases, Vectors, RAG, Performance |
| 24 | Making RAG Accurate in Java | Java | Java, AI, LLM, RAG, Evaluation |
| 25 | Making RAG Accurate in Python | Python | Python, AI, LLM, RAG, Evaluation |
| 26 | LLM Frameworks vs. the Raw SDK in Java | Java | Java, AI, LLM, LangChain4j, Spring AI, Anthropic |
| 27 | LLM Frameworks vs. the Raw SDK in Python | Python | Python, AI, LLM, LangChain, Anthropic |
| 28 | The Model Context Protocol in Java | Java | Java, AI, LLM, MCP, Anthropic |
| 29 | The Model Context Protocol in Python | Python | Python, AI, LLM, MCP, Anthropic |
| 30 | Evaluating LLM Apps in Java | Java | Java, AI, LLM, Evaluation, Testing, Anthropic |
| 31 | Evaluating LLM Apps in Python | Python | Python, AI, LLM, Evaluation, Testing, Anthropic |
| 32 | Prompt Caching and Cost Control in Java | Java | Java, AI, LLM, Performance, Cost, Anthropic |
| 33 | Prompt Caching and Cost Control in Python | Python | Python, AI, LLM, Performance, Cost, Anthropic |
| 34 | Guardrails for LLM Apps in Java | Java | Java, AI, LLM, Security, Guardrails, Anthropic |
| 35 | Guardrails for LLM Apps in Python | Python | Python, AI, LLM, Security, Guardrails, Anthropic |

Notes: Hugo lowercases/hyphenates tags for URLs (`RAG` → `/tags/rag/`, `Spring AI` → `/tags/spring-ai/`);
display text keeps the case above. The `Databases` tag on 22/23 makes them aggregate at `/tags/databases/`
alongside 8/9/18/19; the `Testing` tag on 30/31 aggregates them with 16/17 — this is the intended
cross-topic discoverability. `Anthropic`/`LLM` overlap with `AI` in Dev.to's alias map (both → `ai`)
and are deduped there automatically; they stay in the site tags for richer on-site aggregation.

### 3.4 Cross-link web (WHAT / HOW / WHY)

**Constraint (load-bearing):** `{{< ref "NN-slug.md" >}}` **fails the build if the target post does
not yet exist**. Since increments land in topic order (1→8), a post may only link to (a) existing
posts 1–19, or (b) posts from an *earlier or the same* increment. A desired link from an earlier
post to a later one is added by a **back-fill edit** in the increment that creates the later post,
and that increment re-runs the build gate. This keeps every intermediate state building cleanly.

**Links added at creation (backward only):**

| Increment / posts | Links to (existing or earlier) | Purpose |
|---|---|---|
| Inc 1 · 20/21 RAG | 10/11 (grounding §), 14/15 (agentic) | Situate RAG as the reliable-grounding technique |
| Inc 2 · 22/23 Vector DBs | 18/19 (indexing — HNSW/IVFFlat as index choices), 20/21 (RAG) | Anchor vector indexing in the DB-indexing mental model |
| Inc 3 · 24/25 Making RAG accurate | 20/21 (builds on), 22/23 (vector stores) | Improve the baseline RAG from topic 1 |
| Inc 4 · 26/27 Frameworks | 14/15 (same agent, raw), 20/21 (RAG the framework wraps) | "Same agent, both ways" |
| Inc 5 · 28/29 MCP | 14/15 (tool-use), 26/27 (frameworks' tool abstraction) | MCP as a portable tool interface |
| Inc 6 · 30/31 Evals | 16/17 (testing), 10/11 (evaluate output), 24/25 (retrieval quality) | Evals as the measurement layer |
| Inc 7 · 32/33 Prompt caching | 10/11 (cost/caching §) | Deepen the cost/caching thread |
| Inc 8 · 34/35 Guardrails | 14/15 (validate tool inputs), 10/11 (untrusted output), 24/25 (untrusted RAG sources), 28/29 (MCP tool inputs) | Trust-boundary capstone |

**Back-fill edits (add a forward link into an earlier post when its target lands; re-gate that inc):**

| Performed in increment | Edit |
|---|---|
| Inc 3 (24/25 exist) | Add "→ Making RAG accurate" link into 20/21 (RAG) — **DONE (inc 03):** one sentence at end of "Final Thoughts" in each, +2 lines/file, no other change |
| Inc 6 (30/31 exist) | Add "→ Evaluating LLM apps" link into 24/25 (measuring retrieval quality) — **DONE (inc 06):** one sentence after the retrieval-metrics table in each, no other change |

Keep back-fills minimal (one sentence / one `{{< ref >}}` each) so the earlier post's structure and
already-recorded evidence stay essentially intact; note each back-fill in the *performing*
increment's evidence.

> **As built (inc 08):** posts 34/35 carry **one backward link beyond** the inc-8 row above —
> 34→30 / 35→31 (Evaluating LLM apps). It is backward (targets exist), resolves (build no-REF), and
> is semantically sound (output validation is the guardrail counterpart of evaluation). Kept, same
> posture as inc 07's forward-consistent-link note; no back-fill was performed this increment.

### 3.5 Per-topic content scope & code-substance flags

Each post covers the bullet points listed for its topic in §1. Verification weight varies by how
much real code the topic carries:

- **Topic 1 — RAG from scratch (HEAVY code).** Chunking, embedding calls, a from-scratch cosine /
  top-k vector search, a reranking pass; the "RAG vs. bigger context window" trade-off. Python:
  numpy-style similarity + Anthropic SDK for generation. Java: array math + Anthropic Java SDK.
  **Extra verification:** snippets must be internally consistent (dimensions, API shapes).
- **Topic 2 — Vector databases (HEAVY code / SQL).** pgvector `CREATE EXTENSION` / `vector` column /
  `<->` operators / HNSW + IVFFlat `CREATE INDEX` with real parameters; contrast with a dedicated
  store; recall-vs-latency trade-off; cross-link 18/19. **Extra verification:** pgvector DDL and
  operator syntax verified against live pgvector docs; connection strings are env-var placeholders.
  > **As built (inc 01):** Embeddings grounded on **Voyage AI** (Anthropic has **no** embeddings
  > endpoint — live-verified at `platform.claude.com/docs/.../embeddings.md`). Posts use `voyage-4`
  > (current gen, 1024-dim, `input_type=document|query`) + `rerank-2.5`; Python via the official
  > `voyageai` package, **Java via plain `java.net.http.HttpClient`** to `/v1/embeddings` + `/v1/rerank`
  > (no official Voyage Java SDK). The from-scratch cosine/top-k stays the teaching core. **Later
  > increments that show embeddings (topics 2, 3) must reuse this Voyage grounding, not invent an
  > Anthropic embeddings call.** Both posts also gained a "Testing the Deterministic Core" section
  > (unit-testing the model-free pipeline stages) — a reusable pattern for topic 3/6.
> **As built (inc 02):** pgvector facts live-verified (github.com/pgvector READMEs): operators
> `<->`/`<=>`/`<#>`; HNSW `m=16`/`ef_construction=64`/`hnsw.ef_search=40` (builds w/o data); IVFFlat
> `lists`/`ivfflat.probes` (needs data first). Dedicated-store comparison shipped as a **decision
> table, not vendor code** (avoids ungrounded Pinecone/Weaviate/Qdrant APIs). No LLM-generation code
> in this topic. **Topic 3 should reuse these operator/index facts rather than re-verify.**

- **Topic 3 — Making RAG accurate (MEDIUM).** Hybrid (dense + BM25/keyword) search, metadata
  filtering, chunking strategies, retrieval metrics (recall@k, MRR/nDCG). Shorter snippets + a
  metrics table.
- **Topic 4 — Frameworks vs. raw SDK (HEAVY, live-doc-critical).** Same small agent built (a) on the
  raw Anthropic SDK (grounded in `claude-api`), (b) Python LangChain/LangGraph, (c) Java LangChain4j
  and/or Spring AI. **Highest verification bar:** every framework API live-verified; if a current
  API can't be confirmed, stop and ask. Flag prominently to the implementer.
- **Topic 5 — MCP (HEAVY, live-doc-critical).** Build a minimal MCP tool server and a client that
  consumes one; the protocol's role. **MCP spec + SDK APIs live-verified;** stop-and-ask if unsure.
> **As built (inc 05):** MCP grounded live — Python SDK **v1.x stable branch** (main is v2-alpha,
> not recommended); Java SDK `io.modelcontextprotocol.sdk:mcp-bom:2.0.0` + Spring AI MCP starters;
> stdio transport only (Streamable HTTP narrative). §3a untrusted-tool-arg pattern is central here.
> **Topic 8 (guardrails) forward-links to 28/29 (MCP tool inputs) per §3.4 — that link is added in
> inc 08, not here.**

- **Topic 6 — Evaluating LLM apps (MEDIUM).** Golden datasets, LLM-as-judge (grounded SDK call),
  regression tests wired into CI; cross-link 16/17. Ties to the "evaluate output" theme of 10/11.
- **Topic 7 — Prompt caching & cost control (MEDIUM).** Token economics, `cache_control` prompt
  caching (grounded in `claude-api` `shared/prompt-caching.md`), the Batches API
  (`shared/batches.md`), and model routing (cheap-model triage → strong model). Verify
  `cache_read_input_tokens` usage-check pattern against the skill.
> **As built (inc 07):** Prompt caching + usage-hit-check grounded in `claude-api`
> `shared/prompt-caching.md`; Python Batches in `python/.../batches.md`. **Java Batches had no skill
> doc** — implementer refused to fabricate; orchestrator live-verified the builder from
> `anthropic-sdk-java`'s `BatchExample.java` (`BatchCreateParams`/`resultsStreaming`/
> `MessageBatchIndividualResponse`) and directed the grounded edit. Routing uses `claude-haiku-4-5`
> → `claude-opus-4-8`.

- **Topic 8 — Guardrails (MEDIUM, security-forward).** Prompt-injection defense, PII redaction,
  output validation at the trust boundary — the §3a themes made concrete. Snippets model the
  input-trust boundary (validate/whitelist model-supplied + retrieved content before use).
> **As built (inc 08):** posts 34 (266 lines) / 35 (240). Built around a three-way trust boundary
> (user input / retrieved RAG content / model output); indirect (RAG-borne) injection uses a
> deterministic pre-filter + delimited data channel; output validation reuses the grounded
> `messages.parse` / `StructuredMessageCreateParams` shape from posts 10/11/30/31 (no new API). Java
> "never `eval` model output" rendered as the `javax.script.ScriptEngine.eval(...)` anti-pattern
> (Java has no built-in `eval`) — honest idiomatic equivalent, not a fabricated binding. Post 34 ran
> ~2% over the ~260 soft ceiling to keep every input class's safe/unsafe pairing intact. Details in
> `docs/evidence/increment-08-guardrails.md`.

**Heaviest-verification topics: 1, 2, 4, 5.** Topics 4 and 5 additionally depend on *external*
framework/protocol APIs and carry a stop-and-ask-if-unverifiable rule.

### 3.6 Non-functional requirements
- **Performance:** each post adds one entry to `public/index.json` (a few KB of plain text) and a
  static HTML page. 35 posts is still a tiny index; search stays instant, build stays fast. No new
  runtime cost.
- **Search (no code change) — verified, not assumed:** `layouts/index.json` iterates every regular
  post in `mainSections`; the per-increment gate greps `public/index.json` for each new post's URL,
  proving it indexed without touching search code.
- **Observability/cost:** static site, `$0` recurring, no new infra (see §3e note below).
- **Consistency:** new posts must read like posts 10–19 (§3b) — same section rhythm, checklist
  table, honest "when NOT to" framing, code fenced with correct language hints.

### 3e. Infrastructure & cost
**N/A — no new infrastructure.** These are Markdown files built by the existing Hugo pipeline and
served by the existing Netlify site. No servers, databases, queues, or paid APIs are introduced by
the posts (the pgvector / vector-DB / Anthropic examples are *illustrative snippets*, not deployed
services). **Recurring cost added: $0.** Cheaper alternative considered: N/A (nothing to spend on).

### 3a. Security & Privacy
Static content site; most dimensions are N/A, but the *content* of these posts is security-relevant
because it teaches patterns readers will copy. The bar below is enforced by the per-increment
review gate (§4.1).

- **Authentication** — N/A: no accounts, no server, no auth surface on the blog.
- **Authorization** — N/A: same reason; all content is public.
- **PII / sensitive data** — N/A for the site (no user data collected; queries never leave the
  browser, per `sections-tags-search.md` §3a). **In-content rule:** example data is synthetic
  (`user@example.com`, fake document text); topic 8 (PII redaction) discusses PII handling but uses
  **no real PII** in samples. RAG/eval example corpora are fictional.
- **Secrets** — **no real secret, API key, connection string, or token in any post.** Every SDK
  sample reads keys from the environment (`anthropic.Anthropic()` / `AnthropicOkHttpClient.fromEnv()`
  → `ANTHROPIC_API_KEY`); every pgvector/DB sample uses an env-var placeholder
  (`DATABASE_URL`/`PG_CONN`), never an inline password. Gate greps new posts for hardcoded-secret
  shapes (`sk-`, `ANTHROPIC_API_KEY=`, `password=`, literal keys) and fails on a hit.
- **Input & trust boundaries — the pedagogical core of several posts.** Samples must **model, not
  violate, the trust boundary**: retrieved RAG chunks, MCP tool arguments, and LLM outputs are
  **untrusted input**. Concretely — topic 5 (MCP) shows validating/whitelisting model-supplied tool
  arguments before execution and never string-interpolating them into a shell/SQL command (as posts
  14/15 do); topic 8 (guardrails) shows prompt-injection defense, output validation/schema-parsing
  at the boundary, and PII redaction before text is sent onward; topic 1/3 note that retrieved
  documents can carry injected instructions and must not be trusted as commands. No sample may
  demonstrate an unsafe pattern (e.g. `eval` on model output, raw f-string SQL from a tool arg)
  without explicitly flagging it as the anti-pattern.
- **Threats & mitigations:** (1) *A reader copies an insecure sample into production* → every code
  path that touches untrusted input (tool args, retrieved text, model output) shows the safe
  pattern and names the unsafe one; secrets always via env. (2) *A leaked key in a post* → gate
  grep for secret shapes; env-only convention. (3) *Prompt-injection taught carelessly* → topic 8 is
  explicitly the defense post and the RAG/MCP posts flag the injection surface. (4) *XSS via post
  content into search* → already mitigated site-wide (search renders via `textContent`,
  `sections-tags-search.md` §3a); new posts add no new sink.

## 4. Implementation Steps (iterative increments)

**8 increments, one topic-pair each, in topic order.** Each produces the Java + Python post for one
topic (plus any §3.4 back-fill), leaves `hugo --gc --minify` building clean, and is gated + evidenced
before the next starts. **This is content work — the "Sonnet implements" effort is writing accurate,
well-grounded prose + verified code; there is essentially no Haiku scaffolding** (no boilerplate to
generate — each post is bespoke prose). If a pair's two posts are large, they may be split into two
slices (Java slice, Python slice), each a fresh implementer context, consolidated into one evidence
file at the gate (CLAUDE.md §4 slice rule).

| Inc | Topic / posts | Depends on | Notes |
|-----|---------------|-----------|-------|
| **01** | Topic 1 · RAG from scratch · **20, 21** | existing 10/11, 14/15 | HEAVY code; foundation for inc 03 |
| **02** | Topic 2 · Vector DBs · **22, 23** | existing 18/19; inc 01 | HEAVY SQL; **early anchor** (grounds vector indexing in the DB-indexing posts) |
| **03** | Topic 3 · Making RAG accurate · **24, 25** | inc 01, inc 02 | MEDIUM; **back-fill link into 20/21** |
| **04** | Topic 4 · Frameworks vs SDK · **26, 27** | existing 14/15; inc 01 | HEAVY, live-doc-critical (LangChain/LangGraph, Spring AI, LangChain4j) |
| **05** | Topic 5 · MCP · **28, 29** | existing 14/15; inc 04 | HEAVY, live-doc-critical (MCP spec) |
| **06** | Topic 6 · Evals · **30, 31** | existing 16/17, 10/11; inc 03 | MEDIUM; **back-fill link into 24/25** |
| **07** | Topic 7 · Prompt caching & cost · **32, 33** | existing 10/11 | MEDIUM; ground in `claude-api` prompt-caching/batches docs |
| **08** | Topic 8 · Guardrails · **34, 35** | existing 14/15, 10/11; inc 03, inc 05 | MEDIUM, security-forward; trust-boundary capstone — **DONE (inc 08): Gate PASS, `docs/evidence/increment-08-guardrails.md`** |

**Sequencing rationale:** topic order is fixed by the owner and already satisfies the dependencies —
topic 2 (vector DBs) lands early as an anchor, and topic 3 (making RAG accurate) follows topics 1
and 2 which it builds on. Increments are otherwise loosely coupled through §3.4 links only; each is
independently shippable. Do not start inc N+1 until inc N's evidence records `Gate status: PASS`
(also enforced by the `require-increment-evidence.py` guard).

### 4.0 Context-handoff mapping
Each increment's `implementer` brief (assembled by `/brief NN`) contains **only**:
- The increment's row from §4 + the topic's scope bullets from §1 and §3.5.
- **§3.1** (house style + the two grounding invariants), **§3.2** (that pair's filenames), **§3.3**
  (that pair's front-matter row + the shape block), **§3.4** (that increment's link rows + any
  back-fill it must perform), and **§3a** (the in-content security rules).
- **Pointers, not contents:** "read post 10/14/18 as the style/voice exemplar; read the cross-link
  target posts you reference; read the bundled `claude-api` skill (`python/claude-api`,
  `java/claude-api`, and the relevant `shared/*.md`) before writing any SDK code."
- **Standing invariants (every brief):** posts go in `content/posts/` as `NN-slug.md` per §3.2;
  front-matter shape per §3.3; do not alter posts 1–19 except the explicit §3.4 back-fill; cross-links
  via `{{< ref >}}` (no dangling refs); SDK code grounded in `claude-api` (no `budget_tokens`, env-only
  keys); framework/protocol APIs live-verified, **stop and ask on any unverifiable API or plan gap**;
  no real secrets/PII.

Per-increment section map:

| Inc | Plan sections in brief | Exemplar/target posts to read |
|-----|------------------------|-------------------------------|
| 01 | §1(t1), §3.1, §3.2(20/21), §3.3(20/21), §3.4(inc1), §3.5(t1), §3a | 10, 11, 14, 15; `claude-api` py+java |
| 02 | §1(t2), §3.1, §3.2(22/23), §3.3(22/23), §3.4(inc2), §3.5(t2), §3a | 18, 19, 20, 21; pgvector live docs |
| 03 | §1(t3), §3.1, §3.2(24/25), §3.3(24/25), §3.4(inc3 + back-fill), §3.5(t3), §3a | 20, 21, 22, 23 |
| 04 | §1(t4), §3.1, §3.2(26/27), §3.3(26/27), §3.4(inc4), §3.5(t4), §3a | 14, 15, 20, 21; `claude-api`; LangChain/LangGraph, Spring AI, LangChain4j live docs |
| 05 | §1(t5), §3.1, §3.2(28/29), §3.3(28/29), §3.4(inc5), §3.5(t5), §3a | 14, 15, 26, 27; `claude-api` tool-use; MCP spec live docs |
| 06 | §1(t6), §3.1, §3.2(30/31), §3.3(30/31), §3.4(inc6 + back-fill), §3.5(t6), §3a | 16, 17, 10, 11, 24, 25; `claude-api` |
| 07 | §1(t7), §3.1, §3.2(32/33), §3.3(32/33), §3.4(inc7), §3.5(t7), §3a | 10, 11; `claude-api` `shared/prompt-caching.md`, `shared/batches.md` |
| 08 | §1(t8), §3.1, §3.2(34/35), §3.3(34/35), §3.4(inc8), §3.5(t8), §3a | 14, 15, 10, 11, 24, 25, 28, 29; `claude-api` |

### 4.1 Per-increment gate
For content posts the gate is a clean build + acceptance greps + a read-through review (a blog has
no unit-test surface for prose). Run `/gate NN`, capturing real output. An increment passes only when:
1. **Build clean:** `hugo --gc --minify` completes with **no ERROR and no REF/dangling-`ref` WARNING**
   (a broken cross-link is a hard fail).
2. **Both new posts render:** `public/posts/NN-slug/index.html` exists for both numbers.
3. **Indexed for search (no code change proof):** `public/index.json` contains both new posts' URLs.
4. **Taxonomy resolves:** the Java post appears under `public/categories/java/`, the Python post under
   `public/categories/python/`; each new specific tag term page (e.g. `public/tags/rag/`) exists and
   lists the pair; cross-topic tags aggregate correctly (22/23 at `/tags/databases/`, 30/31 at
   `/tags/testing/`).
5. **Cross-links resolve:** every `{{< ref >}}` in the new posts (and any back-fill) rendered to a real
   `/posts/…/` href (grep generated HTML; covered by #1's no-warning requirement).
6. **Front matter valid:** both posts parse (build would fail otherwise); `categories` matches language;
   tags match §3.3.
7. **Code + security read-through (orchestrator, against the rendered post):** language fences are
   pure (no `def`/`self`/`elif` in a Java block; no `public class`/`;`-terminated lines in a Python
   block — the class of bug caught in earlier increments); SDK snippets match the `claude-api` shape
   (`claude-opus-4-8`, adaptive thinking, no `budget_tokens`); **secret-shape grep is empty**
   (`sk-`, hardcoded `ANTHROPIC_API_KEY=…`, `password=`); untrusted-input samples show the safe
   pattern per §3a. For topics 2/4/5, spot-check that the framework/protocol/DDL APIs used were
   live-verified (implementer cites the source in the increment report).
8. **Evidence** `docs/evidence/increment-<NN>-<slug>.md` written via `/evidence NN` **before** the
   next increment, containing date, base commit, the captured gate output (tails), acceptance
   transcript, deviations, and the literal line **`Gate status: PASS`** (required by the
   `require-increment-evidence.py` guard). Then `/plan-sync NN` back-fills any deviation into this
   plan as an `> **As built (inc NN):** …` note.

## 5. Testing & Verification
- **"Done" per increment** = §4.1 gate green with recorded evidence. **"Done" for the series** =
  all 8 evidence files show PASS, a final full `hugo --gc --minify` is clean with **35 posts**, all
  16 new URLs resolve, all 19 old URLs unchanged, and the sitemap lists 35 posts.
- **Edge cases / failure modes to cover in the gate:**
  - A dangling `{{< ref >}}` (mistyped target or a forward link before its target exists) → build
    WARN/ERROR → hard fail (drives the §3.4 back-fill discipline).
  - Cross-language code leak (Python idiom in a Java fence or vice-versa) → read-through grep.
  - Wrong SDK shape (`budget_tokens`, non-adaptive thinking, hardcoded key) → read-through vs.
    `claude-api`.
  - Unverified framework/protocol API (topics 4/5) → implementer must cite a live source; if none,
    **stop and ask** (do not ship a guessed API).
  - Tag typo breaking cross-topic aggregation (e.g. `Database` vs `Databases`) → gate checks the
    expected term pages.
- **No integration/e2e or new test harness** is introduced — the site's existing Node search test
  (`test/search.test.js`) continues to pass unchanged and is run in the final verify as a regression
  check (new posts must not break the index shape).
- **Optional live verify** (search works in a served build via `hugo server`) at the final gate;
  deploy/syndication re-verify only on explicit owner go-ahead (out of scope here).

## 6. Risks & Rollback
- **Risk: framework/protocol API drift (topics 4, 5) — highest content risk.** A LangChain/LangGraph,
  Spring AI, LangChain4j, or MCP API written from memory could be wrong. *Mitigation:* live-doc
  grounding invariant (§3.1) + stop-and-ask + cite-the-source in evidence. *Rollback:* delete the
  offending post file; prior increments unaffected (posts are independent files).
- **Risk: a code sample ships an error** (the earlier Kotlin-in-Java class of bug). *Mitigation:*
  §4.1 read-through grep + language-pure fences. *Rollback:* edit or revert the single file.
- **Risk: dangling cross-link breaks the build.** *Mitigation:* backward-only links + explicit
  back-fills (§3.4); `ref` fails loudly. *Rollback:* fix/remove the link.
- **Risk: an accidental secret/PII in a sample.** *Mitigation:* env-only convention + secret-shape
  grep in the gate (§3a). *Rollback:* rewrite the sample.
- **Risk: a mistyped tag/category** silently mis-groups a post. *Mitigation:* gate checks the exact
  term pages per §3.3. *Rollback:* front-matter edit.
- **General rollback:** every increment is additive (new files + at most a one-line back-fill into a
  prior post). Reverting an increment = delete its two post files and undo its back-fill; the site
  returns to the previous working state with no migration.

## 7. Impact
- **New files:** 16 posts `content/posts/20…35-*.md` (per §3.2); 8 evidence files
  `docs/evidence/increment-<NN>-<slug>.md`; this plan (`docs/plans/ai-tooling-series.md`).
- **Edited files:** posts **20/21** and **24/25** receive one-line §3.4 back-fill links (in inc 03
  and inc 06 respectively). No other existing post changes.
- **Unchanged:** `hugo.toml`, `netlify.toml`, all theme/layout/search/JS files, `scripts/syndicate/*`
  (optional tag-alias polish is OQ-5, not part of this deliverable), posts 1–19 bodies (except the
  two noted back-fills), all existing `/posts/…/` URLs.
- **Migrations:** none. **Breaking changes:** none (post count 19 → 35; URLs frozen).
- **Docs to update:** this plan (as-built notes at each `/plan-sync`); evidence trail.
- **Deploy:** merge/deploy to Netlify + Dev.to syndication are **separate explicit owner go-aheads**;
  this plan stops at "builds clean locally."
```
