---
title: "Making RAG Accurate in Java"
date: 2026-07-04
description: "Improving retrieval quality beyond cosine top-k: hybrid dense+BM25 search with Reciprocal Rank Fusion, metadata filtering, chunking strategy, and measuring recall@k, precision@k, MRR, and nDCG."
tags:
  - Java
  - AI
  - LLM
  - RAG
  - Evaluation
categories:
  - Java
draft: false
---

## Introduction

[RAG From Scratch in Java]({{< ref "20-rag-from-scratch-in-java.md" >}}) built a retrieval pipeline out of cosine similarity and a reranking pass, and [Vector Databases in Practice for Java]({{< ref "22-vector-databases-in-practice-for-java.md" >}}) moved that same index into pgvector so it can hold millions of chunks. Neither post asked the question that actually decides whether a RAG system is any good: **does it retrieve the right chunks, and how would you know?**

This post answers that question in two halves. First, three techniques that improve what gets retrieved in the first place — hybrid search that catches what pure vector similarity misses, metadata filtering that narrows the search space before ranking even starts, and chunking choices that shape recall long before a query is ever run. Second, the metrics that turn "this feels better" into a number you can track across a change: recall@k, precision@k, MRR, and nDCG. Everything below is illustrative, non-executed prose code, consistent with the pipeline built in post 20.

---

## Why Cosine Similarity Alone Falls Short

Dense embeddings are excellent at matching *meaning* — a query about "canceling a subscription" retrieves a chunk about "ending recurring billing" even though they share no words. But that strength is also a blind spot: embeddings are comparatively weak at exact matches on things that don't carry much semantic meaning of their own — error codes (`ERR_504_TIMEOUT`), product SKUs, ticket IDs, version numbers, acronyms. A query for `"ERR_504_TIMEOUT"` and a chunk containing that exact string can end up with an unremarkable cosine score, because the embedding model has no strong opinion about what that token means.

Classic keyword search has the opposite profile: it matches exact terms precisely but knows nothing about synonyms or paraphrase. The fix is not to pick one — it's to run both and combine their rankings.

---

## Keyword Search: BM25 From Scratch

BM25 (Okapi BM25) is the standard keyword-ranking function behind most full-text search engines. For a query term, its score rewards documents where the term appears often, penalizes documents where the term is common across the whole corpus (low information value), and normalizes for document length so a long document doesn't win purely by having more words:

```java
import java.util.*;
import java.util.stream.*;

record Bm25Index(List<List<String>> tokenizedDocs, Map<String, Integer> docFreq, double avgDocLen) {}

static Bm25Index buildBm25Index(List<List<String>> tokenizedDocs) {
    Map<String, Integer> docFreq = new HashMap<>();
    for (List<String> doc : tokenizedDocs) {
        for (String term : new HashSet<>(doc)) docFreq.merge(term, 1, Integer::sum);
    }
    double avgDocLen = tokenizedDocs.stream().mapToInt(List::size).average().orElse(0);
    return new Bm25Index(tokenizedDocs, docFreq, avgDocLen);
}

static double bm25Score(Bm25Index index, List<String> query, int docIndex, double k1, double b) {
    List<String> doc = index.tokenizedDocs().get(docIndex);
    Map<String, Long> termFreq = doc.stream().collect(Collectors.groupingBy(t -> t, Collectors.counting()));
    int n = index.tokenizedDocs().size();
    double score = 0.0;
    for (String term : query) {
        long f = termFreq.getOrDefault(term, 0L);
        if (f == 0) continue;
        int nq = index.docFreq().getOrDefault(term, 0);
        double idf = Math.log((n - nq + 0.5) / (nq + 0.5) + 1);   // Robertson/Sparck Jones IDF
        double numerator = f * (k1 + 1);
        double denominator = f + k1 * (1 - b + b * doc.size() / index.avgDocLen());
        score += idf * numerator / denominator;
    }
    return score;
}
```

`k1` (typically 1.2–2.0) controls how quickly term-frequency saturates — extra occurrences of a term matter less and less; `b` (typically 0.75) controls how strongly document length is penalized. These are the same defaults most BM25 implementations ship with, and — like `ef_search` in post 22 — they're worth tuning against your own eval set (below) rather than trusting a blog's default forever. Tokenize identically for documents and queries (lowercase, split on non-alphanumerics, at minimum) or the term match never happens.

---

## Combining Rankings: Reciprocal Rank Fusion

Once you have two ranked lists for the same query — one from cosine similarity over embeddings, one from BM25 — you need to merge them into a single ordering. **Reciprocal Rank Fusion (RRF)** does this without needing the two score scales to be comparable (cosine scores and BM25 scores live in entirely different ranges): it only looks at each chunk's *rank position* in each list.

```java
static Map<String, Double> reciprocalRankFusion(
        List<String> denseRankedIds, List<String> bm25RankedIds, double k) {
    Map<String, Double> fused = new HashMap<>();
    for (int rank = 0; rank < denseRankedIds.size(); rank++) {
        fused.merge(denseRankedIds.get(rank), 1.0 / (k + rank + 1), Double::sum);
    }
    for (int rank = 0; rank < bm25RankedIds.size(); rank++) {
        fused.merge(bm25RankedIds.get(rank), 1.0 / (k + rank + 1), Double::sum);
    }
    return fused;
}
```

Each list contributes `1 / (k + rank)` per chunk (rank starting at 1), and a chunk that shows up near the top of *either* list — or both — accumulates a high fused score. `k` (a constant, commonly **60**) dampens the effect of rank 1 vs. rank 2 so one list's top pick doesn't automatically dominate; it's a tuning knob, not a magic number. Sort the fused map by value descending and you have a single ranking that rewards a chunk for being found by *either* signal — which is exactly the point: dense catches paraphrase, BM25 catches exact tokens, and RRF lets a chunk win on whichever strength applies. Feed the fused top-k into the reranking pass from post 20 exactly as before — RRF replaces cosine-only retrieval, not the whole pipeline.

---

## Metadata Filtering: Narrow Before You Rank

Not every relevance signal lives in the text. A chunk usually carries structured metadata too — `tenant_id`, `document_type`, `published_date`, `access_level` — and filtering on it *before* ranking is often the single cheapest accuracy win available: it's not that the vector or BM25 scores were wrong, it's that a chunk from the wrong tenant or an outdated policy revision was in the candidate set at all.

```java
try (PreparedStatement search = conn.prepareStatement(
        "SELECT id, content FROM document_chunks " +
        "WHERE tenant_id = ? AND document_type = ? AND published_date >= ? " +
        "ORDER BY embedding <=> ? LIMIT ?")) {
    search.setString(1, tenantId);
    search.setString(2, documentType);
    search.setObject(3, minPublishedDate);
    search.setObject(4, new PGvector(queryEmbedding));
    search.setInt(5, 20);
    ResultSet rs = search.executeQuery();
}
```

Every filter value here is a **bind parameter**, never string-concatenated — `tenantId` and `documentType` typically originate from request context (a logged-in user, an API caller), which makes them untrusted input in exactly the sense post 20 raised for retrieved chunk content: validate and parameterize them the same way you would any other externally-influenced value reaching SQL. Filtering also directly improves the metrics below — restricting the candidate set to the *right* tenant's documents raises precision@k by construction, since irrelevant-tenant chunks can no longer occupy a top-k slot.

---

## Chunking Strategies Revisited: Size, Overlap, and Recall

Post 20 chunked at a fixed `200` words with `40` words of overlap and called it "a reasonable starting point" — reasonable, but not measured. Chunk size and overlap are recall levers, and they pull in opposite directions:

| Choice | Effect on recall | Effect on precision |
|---|---|---|
| Smaller chunks (e.g. 50–100 words) | Each chunk embeds a narrower, more precise idea — easier for a query to land close to the right one | More chunks total; a query with broad intent may need several chunks to reconstruct the full answer |
| Larger chunks (e.g. 400+ words) | Fewer chunks to search; less risk of splitting a complete idea across a boundary | The embedding blends multiple ideas — a query about one paragraph pulls in three others the model didn't ask about |
| More overlap | Reduces the chance a boundary-spanning idea is lost from both neighboring chunks | More storage and more near-duplicate chunks competing for the same top-k slots |
| Less overlap | Cheaper index, no duplicate content | A fact split exactly across the boundary can be invisible to both chunks |
| Semantic/sentence-aware chunking (split on paragraph or heading boundaries instead of a fixed word count) | Chunks align with actual units of meaning, often improving recall over naive fixed-size splitting | More complex ingestion pipeline; chunk sizes become uneven, which complicates capacity planning |

There's no universally correct setting — the right chunk size depends on how self-contained a "unit of meaning" is in your corpus (a runbook step vs. a legal clause vs. a chat transcript). Treat chunk size and overlap as parameters to sweep during evaluation, the same way post 22 swept `ef_search` against a recall-vs-latency curve — except here the curve is recall vs. chunk size, measured against a labeled query set.

---

## Measuring Retrieval Quality: Recall@k, Precision@k, MRR, nDCG

None of the above — hybrid search, filtering, chunking — is worth shipping on faith. Retrieval quality is measurable, given a small labeled set of `(query, relevant_chunk_ids)` pairs:

```java
static double recallAtK(List<String> retrievedIds, Set<String> relevantIds, int k) {
    Set<String> topK = new HashSet<>(retrievedIds.subList(0, Math.min(k, retrievedIds.size())));
    topK.retainAll(relevantIds);
    return (double) topK.size() / relevantIds.size();
}

static double precisionAtK(List<String> retrievedIds, Set<String> relevantIds, int k) {
    List<String> topK = retrievedIds.subList(0, Math.min(k, retrievedIds.size()));
    long hits = topK.stream().filter(relevantIds::contains).count();
    return (double) hits / topK.size();
}

static double reciprocalRank(List<String> retrievedIds, Set<String> relevantIds) {
    for (int i = 0; i < retrievedIds.size(); i++) {
        if (relevantIds.contains(retrievedIds.get(i))) return 1.0 / (i + 1);
    }
    return 0.0;
}

static double ndcgAtK(List<String> retrievedIds, Map<String, Integer> relevanceGrades, int k) {
    double dcg = 0;
    for (int i = 0; i < Math.min(k, retrievedIds.size()); i++) {
        int rel = relevanceGrades.getOrDefault(retrievedIds.get(i), 0);
        dcg += rel / (Math.log(i + 2) / Math.log(2));
    }
    List<Integer> ideal = relevanceGrades.values().stream()
        .sorted(Comparator.reverseOrder()).limit(k).toList();
    double idcg = IntStream.range(0, ideal.size())
        .mapToDouble(i -> ideal.get(i) / (Math.log(i + 2) / Math.log(2))).sum();
    return idcg == 0 ? 0.0 : dcg / idcg;
}
```

What each answers: **recall@k** — of all the chunks that were actually relevant, what fraction did the top-k retrieve? **precision@k** — of the top-k retrieved, what fraction were actually relevant? **MRR** (mean reciprocal rank, averaged over queries) — how far down the list is the *first* relevant chunk, on average? **nDCG@k** — like recall, but graded relevance (a "perfect match" chunk scores higher than a "somewhat relevant" one) discounted by position, normalized against the best possible ordering. Average each metric across your labeled query set, not a single query — one lucky or unlucky query tells you nothing about the pipeline.

Run the same eval set through each pipeline variant to see what each change actually bought (illustrative numbers from a synthetic 50-query set — the shape of the improvement is the point, not these exact figures):

| Pipeline variant | Recall@5 | Precision@5 | MRR | nDCG@5 |
|---|---|---|---|---|
| Cosine-only (post 20 baseline) | 0.62 | 0.31 | 0.54 | 0.58 |
| + BM25 hybrid via RRF | 0.74 | 0.38 | 0.66 | 0.69 |
| + rerank (post 20 Step 4) | 0.78 | 0.44 | 0.75 | 0.77 |
| + tenant/date metadata filter | 0.81 | 0.47 | 0.78 | 0.80 |

Each row adds one technique on top of the last, which is exactly how to evaluate a change in production: hold the eval set fixed, change one thing, re-run, and let the metrics — not intuition — decide whether it shipped.

→ These metrics grade *retrieval* only; for evaluating the quality of the *generated answer* built from these chunks — golden datasets, LLM-as-judge, regression gates in CI — see [Evaluating LLM Apps in Java]({{< ref "30-evaluating-llm-apps-in-java.md" >}}).

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

Cosine top-k over embeddings is a good *shortlist* generator, not an accuracy strategy on its own — post 20 said so plainly, and this post is the deeper pass on making that shortlist, and the ranking built from it, actually good. Hybrid search recovers exact-match queries dense retrieval misses; metadata filtering removes irrelevant candidates before ranking ever sees them; chunking strategy shapes what's retrievable before a query is ever run. None of it is worth trusting without measurement — recall@k, precision@k, MRR, and nDCG turn "we improved retrieval" from a feeling into a number you can defend, track, and regress-test the next time someone touches the pipeline.
