---
title: "Making RAG Accurate in Python"
date: 2026-07-04
description: "Improving retrieval quality beyond cosine top-k: hybrid dense+BM25 search with Reciprocal Rank Fusion, metadata filtering, chunking strategy, and measuring recall@k, precision@k, MRR, and nDCG."
tags:
  - Python
  - AI
  - LLM
  - RAG
  - Evaluation
categories:
  - Python
draft: false
---

## Introduction

[RAG From Scratch in Python]({{< ref "21-rag-from-scratch-in-python.md" >}}) built a retrieval pipeline out of cosine similarity and a reranking pass, and [Vector Databases in Practice for Python]({{< ref "23-vector-databases-in-practice-for-python.md" >}}) moved that same index into pgvector so it can hold millions of chunks. Neither post asked the question that actually decides whether a RAG system is any good: **does it retrieve the right chunks, and how would you know?**

This post answers that question in two halves. First, three techniques that improve what gets retrieved in the first place — hybrid search that catches what pure vector similarity misses, metadata filtering that narrows the search space before ranking even starts, and chunking choices that shape recall long before a query is ever run. Second, the metrics that turn "this feels better" into a number you can track across a change: recall@k, precision@k, MRR, and nDCG. Everything below is illustrative, non-executed prose code, consistent with the pipeline built in post 21.

---

## Why Cosine Similarity Alone Falls Short

Dense embeddings are excellent at matching *meaning* — a query about "canceling a subscription" retrieves a chunk about "ending recurring billing" even though they share no words. But that strength is also a blind spot: embeddings are comparatively weak at exact matches on things that don't carry much semantic meaning of their own — error codes (`ERR_504_TIMEOUT`), product SKUs, ticket IDs, version numbers, acronyms. A query for `"ERR_504_TIMEOUT"` and a chunk containing that exact string can end up with an unremarkable cosine score, because the embedding model has no strong opinion about what that token means.

Classic keyword search has the opposite profile: it matches exact terms precisely but knows nothing about synonyms or paraphrase. The fix is not to pick one — it's to run both and combine their rankings.

---

## Keyword Search: BM25 From Scratch

BM25 (Okapi BM25) is the standard keyword-ranking function behind most full-text search engines. For a query term, its score rewards documents where the term appears often, penalizes documents where the term is common across the whole corpus (low information value), and normalizes for document length so a long document doesn't win purely by having more words:

```python
import math
from collections import Counter
from dataclasses import dataclass

@dataclass
class Bm25Index:
    tokenized_docs: list[list[str]]
    doc_freq: dict[str, int]
    avg_doc_len: float

def build_bm25_index(tokenized_docs: list[list[str]]) -> Bm25Index:
    doc_freq: dict[str, int] = {}
    for doc in tokenized_docs:
        for term in set(doc):
            doc_freq[term] = doc_freq.get(term, 0) + 1
    avg_doc_len = sum(len(d) for d in tokenized_docs) / len(tokenized_docs)
    return Bm25Index(tokenized_docs=tokenized_docs, doc_freq=doc_freq, avg_doc_len=avg_doc_len)

def bm25_score(index: Bm25Index, query: list[str], doc_index: int, k1: float = 1.5, b: float = 0.75) -> float:
    doc = index.tokenized_docs[doc_index]
    term_freq = Counter(doc)
    n = len(index.tokenized_docs)
    score = 0.0
    for term in query:
        f = term_freq.get(term, 0)
        if f == 0:
            continue
        nq = index.doc_freq.get(term, 0)
        idf = math.log((n - nq + 0.5) / (nq + 0.5) + 1)   # Robertson/Sparck Jones IDF
        numerator = f * (k1 + 1)
        denominator = f + k1 * (1 - b + b * len(doc) / index.avg_doc_len)
        score += idf * numerator / denominator
    return score
```

`k1` (typically 1.2–2.0) controls how quickly term-frequency saturates — extra occurrences of a term matter less and less; `b` (typically 0.75) controls how strongly document length is penalized. These are the same defaults most BM25 implementations ship with (including the popular `rank_bm25` package's `BM25Okapi(tokenized_corpus)` — `bm25.get_scores(tokenized_query)` returns exactly this score per document, if you'd rather not hand-roll it), and — like `ef_search` in post 23 — they're worth tuning against your own eval set (below) rather than trusting a blog's default forever. Tokenize identically for documents and queries (lowercase, split on non-alphanumerics, at minimum) or the term match never happens.

---

## Combining Rankings: Reciprocal Rank Fusion

Once you have two ranked lists for the same query — one from cosine similarity over embeddings, one from BM25 — you need to merge them into a single ordering. **Reciprocal Rank Fusion (RRF)** does this without needing the two score scales to be comparable (cosine scores and BM25 scores live in entirely different ranges): it only looks at each chunk's *rank position* in each list.

```python
def reciprocal_rank_fusion(
    dense_ranked_ids: list[str], bm25_ranked_ids: list[str], k: float = 60.0
) -> dict[str, float]:
    fused: dict[str, float] = {}
    for rank, chunk_id in enumerate(dense_ranked_ids, start=1):
        fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank)
    for rank, chunk_id in enumerate(bm25_ranked_ids, start=1):
        fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return fused
```

Each list contributes `1 / (k + rank)` per chunk (rank starting at 1), and a chunk that shows up near the top of *either* list — or both — accumulates a high fused score. `k` (a constant, commonly **60**) dampens the effect of rank 1 vs. rank 2 so one list's top pick doesn't automatically dominate; it's a tuning knob, not a magic number. Sort `fused` by value descending (`sorted(fused.items(), key=lambda kv: kv[1], reverse=True)`) and you have a single ranking that rewards a chunk for being found by *either* signal — which is exactly the point: dense catches paraphrase, BM25 catches exact tokens, and RRF lets a chunk win on whichever strength applies. Feed the fused top-k into the reranking pass from post 21 exactly as before — RRF replaces cosine-only retrieval, not the whole pipeline.

---

## Metadata Filtering: Narrow Before You Rank

Not every relevance signal lives in the text. A chunk usually carries structured metadata too — `tenant_id`, `document_type`, `published_date`, `access_level` — and filtering on it *before* ranking is often the single cheapest accuracy win available: it's not that the vector or BM25 scores were wrong, it's that a chunk from the wrong tenant or an outdated policy revision was in the candidate set at all.

```python
with conn.cursor() as cur:
    cur.execute(
        "SELECT id, content FROM document_chunks "
        "WHERE tenant_id = %s AND document_type = %s AND published_date >= %s "
        "ORDER BY embedding <=> %s LIMIT %s",
        (tenant_id, document_type, min_published_date, query_embedding, 20),
    )
    rows = cur.fetchall()
```

Every filter value here is a **bind parameter** (`%s`), never an f-string dropped into the query — `tenant_id` and `document_type` typically originate from request context (a logged-in user, an API caller), which makes them untrusted input in exactly the sense post 21 raised for retrieved chunk content: validate and parameterize them the same way you would any other externally-influenced value reaching SQL. Filtering also directly improves the metrics below — restricting the candidate set to the *right* tenant's documents raises precision@k by construction, since irrelevant-tenant chunks can no longer occupy a top-k slot.

---

## Chunking Strategies Revisited: Size, Overlap, and Recall

Post 21 chunked at a fixed `200` words with `40` words of overlap and called it "a reasonable starting point" — reasonable, but not measured. Chunk size and overlap are recall levers, and they pull in opposite directions:

| Choice | Effect on recall | Effect on precision |
|---|---|---|
| Smaller chunks (e.g. 50–100 words) | Each chunk embeds a narrower, more precise idea — easier for a query to land close to the right one | More chunks total; a query with broad intent may need several chunks to reconstruct the full answer |
| Larger chunks (e.g. 400+ words) | Fewer chunks to search; less risk of splitting a complete idea across a boundary | The embedding blends multiple ideas — a query about one paragraph pulls in three others the model didn't ask about |
| More overlap | Reduces the chance a boundary-spanning idea is lost from both neighboring chunks | More storage and more near-duplicate chunks competing for the same top-k slots |
| Less overlap | Cheaper index, no duplicate content | A fact split exactly across the boundary can be invisible to both chunks |
| Semantic/sentence-aware chunking (split on paragraph or heading boundaries instead of a fixed word count) | Chunks align with actual units of meaning, often improving recall over naive fixed-size splitting | More complex ingestion pipeline; chunk sizes become uneven, which complicates capacity planning |

There's no universally correct setting — the right chunk size depends on how self-contained a "unit of meaning" is in your corpus (a runbook step vs. a legal clause vs. a chat transcript). Treat chunk size and overlap as parameters to sweep during evaluation, the same way post 23 swept `ef_search` against a recall-vs-latency curve — except here the curve is recall vs. chunk size, measured against a labeled query set.

---

## Measuring Retrieval Quality: Recall@k, Precision@k, MRR, nDCG

None of the above — hybrid search, filtering, chunking — is worth shipping on faith. Retrieval quality is measurable, given a small labeled set of `(query, relevant_chunk_ids)` pairs:

```python
def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    top_k = set(retrieved_ids[:k])
    return len(top_k & relevant_ids) / len(relevant_ids)

def precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    top_k = retrieved_ids[:k]
    hits = sum(1 for cid in top_k if cid in relevant_ids)
    return hits / len(top_k)

def reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    for i, cid in enumerate(retrieved_ids):
        if cid in relevant_ids:
            return 1.0 / (i + 1)
    return 0.0

def ndcg_at_k(retrieved_ids: list[str], relevance_grades: dict[str, int], k: int) -> float:
    dcg = sum(
        relevance_grades.get(cid, 0) / math.log2(i + 2)
        for i, cid in enumerate(retrieved_ids[:k])
    )
    ideal = sorted(relevance_grades.values(), reverse=True)[:k]
    idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0
```

What each answers: **recall@k** — of all the chunks that were actually relevant, what fraction did the top-k retrieve? **precision@k** — of the top-k retrieved, what fraction were actually relevant? **MRR** (mean reciprocal rank, averaged over queries) — how far down the list is the *first* relevant chunk, on average? **nDCG@k** — like recall, but graded relevance (a "perfect match" chunk scores higher than a "somewhat relevant" one) discounted by position, normalized against the best possible ordering. Average each metric across your labeled query set, not a single query — one lucky or unlucky query tells you nothing about the pipeline.

Run the same eval set through each pipeline variant to see what each change actually bought (illustrative numbers from a synthetic 50-query set — the shape of the improvement is the point, not these exact figures):

| Pipeline variant | Recall@5 | Precision@5 | MRR | nDCG@5 |
|---|---|---|---|---|
| Cosine-only (post 21 baseline) | 0.62 | 0.31 | 0.54 | 0.58 |
| + BM25 hybrid via RRF | 0.74 | 0.38 | 0.66 | 0.69 |
| + rerank (post 21 Step 4) | 0.78 | 0.44 | 0.75 | 0.77 |
| + tenant/date metadata filter | 0.81 | 0.47 | 0.78 | 0.80 |

Each row adds one technique on top of the last, which is exactly how to evaluate a change in production: hold the eval set fixed, change one thing, re-run, and let the metrics — not intuition — decide whether it shipped.

→ These metrics grade *retrieval* only; for evaluating the quality of the *generated answer* built from these chunks — golden datasets, LLM-as-judge, regression gates in CI — see [Evaluating LLM Apps in Python]({{< ref "31-evaluating-llm-apps-in-python.md" >}}).

---

## Practical Checklist

| Practice | Why it matters |
|----------|----------------|
| Run BM25 alongside dense retrieval, not instead of it | Dense catches paraphrase; BM25 catches exact tokens (IDs, codes, acronyms) neither alone covers well |
| Combine rankings with RRF, not raw score averaging | Cosine and BM25 scores aren't on comparable scales; RRF only needs rank position |
| Filter on metadata before ranking, with bind parameters | Cheapest precision win available; filter values are untrusted input like any request-derived value |
| Treat chunk size/overlap as parameters to sweep, not fixed defaults | Recall depends on how self-contained a "unit of meaning" is in your corpus |
| Maintain a labeled `(query, relevant_ids)` eval set | Without it, "this feels more accurate" is not a claim you can verify or regress-test |
| Track recall@k, precision@k, MRR, and nDCG together | Each answers a different question; no single metric tells the whole story |
| Change one pipeline stage at a time, re-measure | Attributing an improvement to the right change requires isolating it |

---

## Final Thoughts

Cosine top-k over embeddings is a good *shortlist* generator, not an accuracy strategy on its own — post 21 said so plainly, and this post is the deeper pass on making that shortlist, and the ranking built from it, actually good. Hybrid search recovers exact-match queries dense retrieval misses; metadata filtering removes irrelevant candidates before ranking ever sees them; chunking strategy shapes what's retrievable before a query is ever run. None of it is worth trusting without measurement — recall@k, precision@k, MRR, and nDCG turn "we improved retrieval" from a feeling into a number you can defend, track, and regress-test the next time someone touches the pipeline.
