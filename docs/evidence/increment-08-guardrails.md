# Evidence — AI-Tooling Inc 08: Guardrails for LLM apps (posts 34/35) — FINAL increment

- **Date:** 2026-07-05 · **Plan:** `docs/plans/ai-tooling-series.md` §1(t8)/§3.1/§3.2/§3.3/§3.4(inc8)/§3.5(t8)/§3a (APPROVED) · **Base:** `c19b36c`
- **Implementer:** Sonnet subagent; **orchestrator independently re-ran the full §4.1 gate.** Security-forward, trust-boundary capstone.

## Delivered
- `content/posts/34-guardrails-for-llm-apps-in-java.md` — 266 lines
- `content/posts/35-guardrails-for-llm-apps-in-python.md` — 240 lines
- Scope: the three-way trust boundary (user input / retrieved RAG content / model output), direct prompt-injection defense, indirect (RAG-borne) prompt-injection defense with a deterministic pre-filter + delimited data channel, input validation/whitelisting at the tool boundary, schema-validated output (`messages.parse` / `StructuredMessageCreateParams`, never `eval`/`exec`/shell/SQL-interpolation of model output), and PII redaction on synthetic data — closing with an Anti-Patterns table + Final Thoughts.

## Gate (orchestrator's own run)
1. **Build:** `hugo --gc --minify` → 145 pages, **no ERROR / no WARN / no REF** (`gate-08-build.txt`).
2. **Render + index:** 34, 35 render in `public/`; both URLs in `public/index.json` (**35 posts total**) (`gate-08-acceptance.txt`).
3. **Taxonomy:** `/categories/{java,python}/` list the pair; **`/tags/guardrails/` and `/tags/security/`** term pages exist and each list 34 + 35.
4. **Cross-links (backward-only, all targets exist):** post 34 (Java) → 11, 14, 24, 28, 30; post 35 (Python) → 10, 15, 25, 29, 31 — every `{{< ref >}}` rendered to a real `/posts/…/` href (`gate-08-crosslinks-fm.txt`); build no-REF confirms resolution.
5. **Front matter:** both parse; field order per §3.3; tags `Java|Python, AI, LLM, Security, Guardrails, Anthropic`; `categories` matches language; `date: 2026-07-05`.
6. **Read-through (security core):** secret-shape grep **empty** (`sk-`/`ANTHROPIC_API_KEY=`/`password=`); **no `budget_tokens`**; `claude-opus-4-8` (Py) / `CLAUDE_OPUS_4_8` (Java) — 3 each. Injection (11/11), anti-pattern/unsafe (26/25), redact-PII (12/12), validate-whitelist-schema (19/19) all present in both — every untrusted-input path pairs the SAFE pattern with the named anti-pattern per §3a (`gate-08-security.txt`).
7. **Fence purity:** 9 `java` fences (post 34) / 9 `python` fences (post 35). Cross-idiom scan: the two flags in post 35 are `# UNSAFE — …;` **Python comment** lines (prose semicolon), verified in context (lines 39–41, 79–81) — **not** Java leaks; code is genuine Python (`prompt = … + user_input`). Clean (`gate-08-fences.txt`).
8. **Regression:** `node test/search.test.js` → **4/4 pass**; new posts 34/35 correctly indexed in the "docker" match set (`gate-08-searchtest.txt`).

## Grounding
- Anthropic SDK shapes grounded in the bundled `claude-api` skill (`python/claude-api/README.md`, `java/claude-api/README.md`) and cross-validated against the identical already-shipped usage in posts 10/11 (reliable LLM) and 30/31 (evals): Python `client.messages.create(model="claude-opus-4-8", thinking={"type":"adaptive"})` + `client.messages.parse(..., output_format=Model)`; Java `Model.CLAUDE_OPUS_4_8` + `ThinkingConfigAdaptive` + `StructuredMessageCreateParams` via `.outputConfig(Class)`. No API written from memory; nothing required stop-and-ask.

## Deviations (reviewed & accepted → plan-synced)
- **Post 34 length 266 > ~260 soft ceiling** (~2% over): further trimming would drop a required safe/unsafe pairing (the topic mandates one per input class). Within observed range (post 19=289, post 26=285). Post 35 = 240, in band. Accepted; flagged not silent.
- **Extra backward cross-link 34→30 / 35→31 (Evaluating LLM apps)** beyond the plan's §3.4 inc-08 row (which lists 14/15, 10/11, 24/25, 28/29): the link is backward (targets exist), resolves (build no-REF), and is semantically sound — output validation is the guardrail counterpart of evaluation. Same posture as inc 07's forward-consistent-link note; kept. Plan-synced as an as-built note.
- **Java "never `eval` model output" rendered as `javax.script.ScriptEngine.eval(modelOutput)`** — Java has no built-in `eval`; the ScriptEngine form is the honest Java-idiomatic arbitrary-code-execution anti-pattern, not a fabricated API. Judgment call, flagged.

Gate status: PASS. This is the final AI-Tooling increment — series-level VERIFY follows (35-post clean build + URL/sitemap check).
