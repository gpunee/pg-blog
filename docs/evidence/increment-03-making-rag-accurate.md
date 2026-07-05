# Evidence — AI-Tooling Inc 03: Making RAG accurate (posts 24/25) + back-fill 20/21

- **Date:** 2026-07-04 · **Plan:** `docs/plans/ai-tooling-series.md` §1(t3)/§3.1/§3.2/§3.3/§3.4(inc3+back-fill)/§3.5(t3)/§3a (APPROVED) · **Base:** `868aad8`
- **Implementer:** Sonnet subagent; **orchestrator independently re-ran the full §4.1 gate.**

## Delivered
- New: `content/posts/24-making-rag-accurate-in-java.md` (202 lines), `content/posts/25-making-rag-accurate-in-python.md` (192 lines).
- **Back-fill (§3.4):** one sentence + `{{< ref >}}` forward link added into `20-…-java.md` (→24) and `21-…-python.md` (→25); each file grew by 2 lines (sentence + spacer), no other change. These were the only existing posts touched.
- Scope: hybrid search (hand-rolled BM25 + Reciprocal Rank Fusion over the post-20/21 cosine ranking), metadata filtering (parameterized/untrusted-input framing), chunking-strategy trade-off table, and a "Measuring Retrieval Quality" section (recall@k, precision@k, MRR, nDCG) with a cumulative-improvement metrics table.

## Gate (orchestrator's own run)
1. **Build:** `hugo --gc --minify` → 121 pages, **no ERROR / no WARN / no REF**.
2. **Render + index:** 24 and 25 render; both URLs in `public/index.json` (25 posts total).
3. **Taxonomy:** `/categories/{java,python}/` list the pair; `/tags/rag/` and `/tags/evaluation/` exist and list 24/25.
4. **Back-fill verified directly** (20/21 are untracked so `git diff` is blank — checked by grep): line 386 of post 20 and line 320 of post 21 carry the `{{< ref "24…" >}}` / `{{< ref "25…" >}}` link; line counts 384→386, 318→320.
5. **Cross-links:** 24→20/22, 25→21/23 (backward), plus back-fills 20→24, 21→25 (targets now exist) — all resolve (build no-REF).
6. **Read-through:** fences pure (4 java / 4 python; awk cross-idiom scan = 0). Secret grep empty. No SDK code (topic is retrieval, not generation) — correct. Metrics all present (BM25×many, MRR, nDCG, recall@k, precision@k, RRF).
7. **Regression:** `node test/search.test.js` → 4/4 pass.

## External grounding (implementer live-verified)
- **Okapi BM25** formula + IDF term vs `en.wikipedia.org/wiki/Okapi_BM25`; **RRF** `1/(k+rank)`, `k=60` vs Elastic RRF docs; `rank_bm25` API shape vs live PyPI (mentioned as a pointer only). Retrieval metrics from first principles (plan-allowed). Reused inc-01 Voyage + inc-02 pgvector facts without re-verifying.

## Deviations (reviewed & accepted → plan-synced)
- **BM25 hand-rolled in both languages** (not Apache Lucene `BM25Similarity`): grounded in the verified stable formula, mirrors the "from scratch" pedagogy of 20/21, keeps Java/Python parallel, avoids ungrounded Lucene wiring — squarely the brief's "keep code framework-light" fallback. Accepted.

Gate status: PASS. AI-Tooling increment 04 may start.
