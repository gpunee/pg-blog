---
title: "Prompt Caching and Cost Control in Java"
date: 2026-07-04
description: "Token economics, cache_control prompt caching, the Batches API, and cheap-to-strong model routing — controlling LLM spend in Java without sacrificing quality."
tags:
  - Java
  - AI
  - LLM
  - Performance
  - Cost
  - Anthropic
categories:
  - Java
draft: false
---

## Introduction

We already covered picking the right model tier for the task and caching a large shared prefix in {{< ref "11-building-reliable-llm-apps-in-java.md" >}}. Those two lines were the tip of a bigger discipline: **LLM cost is not a fixed line item, it's an engineering variable** — one you can measure and shrink with the same rigor you'd apply to database query time or container memory.

This post goes deeper: how input/output pricing actually works, the exact `cache_control` shape and how to *prove* a cache hit rather than assume one, the Batches API for work that isn't latency-sensitive, and model routing — using a cheap model to triage, escalating only the hard cases to a stronger one. The honest framing throughout: **measure before you optimize.** Every technique here has a cost of its own; applied to the wrong workload, "optimization" makes things slower or more expensive.

---

## Token Economics: Why the Prefix Is the Bill

Anthropic (like every hosted LLM provider) prices **input and output tokens separately, and output is always pricier** — the model has to generate output autoregressively, one token informed by all the ones before it, while input can be processed in parallel. Representative pricing from the current model catalog:

| Model | Input | Output |
|---|---:|---:|
| Claude Opus 4.8 | $5.00 / MTok | $25.00 / MTok |
| Claude Sonnet 5 | $3.00 / MTok | $15.00 / MTok |
| Claude Haiku 4.5 | $1.00 / MTok | $5.00 / MTok |

Two consequences follow directly:

1. **Long system prompts, tool definitions, and RAG context are read on *every* request**, not written once. A 20K-token system prompt sent on every one of 10,000 requests is 200M input tokens — at Opus 4.8 rates, $1,000 before a single output token is generated. The **shared prefix**, not the user's question, is usually where the money goes.
2. **A verbose model wastes money twice** — once on the extra output tokens themselves, and again because the next turn's `messages` history now carries that verbosity forward as input on every subsequent call. Trimming `max_tokens` and asking for concise output is a cost lever, not just a style preference.

This is why the two techniques below — caching the stable prefix, and not re-running the expensive model on requests a cheap one could handle — are the highest-leverage cost levers available, in that order.

---

## Prompt Caching: Pay to Write Once, Read Cheaply

Prompt caching lets you mark a **stable prefix** of a request — a system prompt, a tool list, retrieved RAG context — so a subsequent request with an identical prefix reads it back at a fraction of the price instead of reprocessing it. Grounded in the bundled `claude-api` skill's `shared/prompt-caching.md`:

- **It's a prefix match.** The cache key is derived from the exact bytes up to each `cache_control` breakpoint. One byte different anywhere in the prefix — an interpolated timestamp, a reordered key, a different tool list — invalidates everything after it.
- **Render order is `tools` → `system` → `messages`.** A breakpoint on the last `system` block caches tools *and* system together.
- **Cache reads cost ~0.1× the base input price; cache writes cost 1.25× (5-minute TTL) or 2× (1-hour TTL).** With a 5-minute TTL, two requests already break even (1.25× + 0.1× vs. 2×); a 1-hour TTL needs about three.
- **Minimum cacheable prefix is model-dependent** — Opus 4.8 needs at least 4,096 tokens. A shorter prefix silently won't cache: no error, just `cacheCreationInputTokens() == 0`.

### The exact shape

The Java SDK carries `cache_control` on a `TextBlockParam`. Use `.systemOfTextBlockParams(...)` — the plain `.system(String)` overload can't attach cache control:

```java
import com.anthropic.client.AnthropicClient;
import com.anthropic.client.okhttp.AnthropicOkHttpClient;
import com.anthropic.models.messages.CacheControlEphemeral;
import com.anthropic.models.messages.Message;
import com.anthropic.models.messages.MessageCreateParams;
import com.anthropic.models.messages.Model;
import com.anthropic.models.messages.TextBlockParam;

import java.util.List;

AnthropicClient client = AnthropicOkHttpClient.fromEnv(); // reads ANTHROPIC_API_KEY

// STABLE_SYSTEM_PROMPT holds the tool docs / policy text / retrieved corpus —
// large, and byte-identical across many requests.
MessageCreateParams params = MessageCreateParams.builder()
    .model(Model.CLAUDE_OPUS_4_8)
    .maxTokens(1024L)
    .systemOfTextBlockParams(List.of(
        TextBlockParam.builder()
            .text(STABLE_SYSTEM_PROMPT)
            .cacheControl(CacheControlEphemeral.builder().build())   // default TTL: 5 minutes
            .build()))
    .addUserMessage(userQuestion)   // varies per request — no cache_control here
    .build();

Message response = client.messages().create(params);
```

For a longer-lived prefix (a corpus that's reused across a bursty traffic pattern with gaps longer than five minutes), pass an explicit TTL:

```java
TextBlockParam.builder()
    .text(STABLE_SYSTEM_PROMPT)
    .cacheControl(CacheControlEphemeral.builder()
        .ttl(CacheControlEphemeral.Ttl.TTL_1H)
        .build())
    .build()
```

### Confirming a cache hit — don't assume, check the field

The response `usage` object is the ground truth. `input_tokens` reports **only the uncached remainder** — total prompt size is the sum of all three fields:

```java
var usage = response.usage();
System.out.println("cache write: " + usage.cacheCreationInputTokens());  // paid ~1.25x
System.out.println("cache read:  " + usage.cacheReadInputTokens());     // paid ~0.1x
System.out.println("uncached:    " + usage.inputTokens());              // paid full price
```

The first call against a new prefix shows `cacheCreationInputTokens() > 0` and `cacheReadInputTokens() == 0` — that request paid the write premium. Every subsequent call with the *same* prefix, inside the TTL, should show `cacheReadInputTokens() > 0` and `cacheCreationInputTokens() == 0`. If `cacheReadInputTokens()` stays zero across repeated, apparently-identical requests, something in the prefix is silently different — a non-deterministic-order tool list, an interpolated request ID, a system prompt built with a `HashMap` instead of a `LinkedHashMap`. Diff the rendered bytes to find it before you conclude caching "doesn't work here."

**Architectural rule that matters more than marker placement:** don't change the tool list or the model mid-session, and don't interpolate a timestamp or user ID into the system prompt — both sit ahead of the breakpoint and invalidate the whole prefix on every call. Push anything that varies per request to the end of `messages`, after the last cache-control marker.

---

## The Batches API: Half Price When Latency Doesn't Matter

Not every LLM call needs a response in two seconds. Nightly report summarization, bulk document classification, backfilling embeddings metadata, re-scoring an eval set — none of these are latency-sensitive, and all of them are exactly the workload the **Message Batches API** is priced for: **50% off standard token pricing**, in exchange for asynchronous processing (most batches finish within an hour; the ceiling is 24 hours).

The bundled skill's grounding for this endpoint (`python/claude-api/batches.md`) documents the Python and TypeScript shapes fully: submit a list of `{custom_id, params}` request items via `client.messages.batches.create(requests=[...])`, poll `client.messages.batches.retrieve(batch_id)` until `processing_status == "ended"`, then stream `client.messages.batches.results(batch_id)`, matching each result back to its `custom_id`. Every Messages API feature — including prompt caching — works inside a batch, so a batch of 10,000 classification calls that all share one large system prompt gets **both** the 50% batch discount and the cache-read discount on the shared prefix.

The Java SDK exposes the same endpoint under `com.anthropic.models.messages.batches`. Each item pairs a `customId` with its own request params, submitted in one `BatchCreateParams`:

```java
import com.anthropic.client.AnthropicClient;
import com.anthropic.models.messages.Model;
import com.anthropic.models.messages.batches.BatchCreateParams;
import com.anthropic.models.messages.batches.BatchResultsParams;
import com.anthropic.models.messages.batches.BatchRetrieveParams;
import com.anthropic.models.messages.batches.MessageBatch;
import com.anthropic.models.messages.batches.MessageBatchIndividualResponse;
import com.anthropic.core.http.StreamResponse;

BatchCreateParams params = BatchCreateParams.builder()
    .addRequest(BatchCreateParams.Request.builder()
        .customId("invoice-42")
        .params(BatchCreateParams.Request.Params.builder()
            .model(Model.CLAUDE_HAIKU_4_5)   // a cheap model is a natural batch target
            .maxTokens(1024)
            .addUserMessage("Classify as positive/negative/neutral: " + reviewText)
            .build())
        .build())
    // .addRequest(...) again per item — one batch can hold up to 100,000
    .build();

MessageBatch batch = client.messages().batches().create(params);

// Poll until processing finishes — most batches complete within an hour
MessageBatch status = client.messages().batches().retrieve(
    BatchRetrieveParams.builder().messageBatchId(batch.id()).build());
// inspect status.processingStatus() in a loop until it reports the batch has ended

// Stream results back, matched by customId
try (StreamResponse<MessageBatchIndividualResponse> results =
        client.messages().batches().resultsStreaming(
            BatchResultsParams.builder().messageBatchId(batch.id()).build())) {
    results.stream().forEach(result -> {
        // result.customId() ties this back to the request that produced it;
        // result.result() carries the succeeded/errored/canceled/expired outcome
    });
}
```

**The cost tradeoff to weigh honestly:** batching trades latency for a guaranteed 50% discount. It's a clear win for bulk, non-interactive work; it is the *wrong* tool the moment a human is waiting on the response, and it adds operational complexity (submit, poll or webhook, reconcile results by `custom_id`, handle `errored`/`expired` items) that a synchronous call doesn't have. Don't reach for it until you've confirmed — with real usage data — that the workload is actually bulk and actually not latency-sensitive.

---

## Model Routing: Let the Cheap Model Triage

The other lever, orthogonal to caching and batching, is **not sending every request to your most expensive model.** A large fraction of real traffic — sentiment classification, intent detection, "is this ticket urgent," simple extraction — is well within a cheap model's competence. Route those to `claude-haiku-4-5` and reserve `claude-opus-4-8` for the requests that actually need it.

A simple, honest pattern: run the cheap model first with instructions to flag its own uncertainty, and escalate only when it says so.

```java
record Triage(String label, boolean confident) {}

Triage triageWithHaiku(String ticketText) {
    MessageCreateParams params = MessageCreateParams.builder()
        .model(Model.CLAUDE_HAIKU_4_5)
        .maxTokens(100L)
        .addUserMessage("""
            Classify this support ticket as billing/technical/other.
            If you are not confident, say so explicitly.

            Ticket: %s

            Respond as: <label>|<confident:yes/no>""".formatted(ticketText))
        .build();

    String reply = client.messages().create(params).content().stream()
        .flatMap(block -> block.text().stream())
        .findFirst()
        .map(block -> block.text())
        .orElse("other|no");

    String[] parts = reply.split("\\|");
    return new Triage(parts[0].trim(), parts.length > 1 && parts[1].trim().equalsIgnoreCase("yes"));
}

String handleTicket(String ticketText) {
    Triage triage = triageWithHaiku(ticketText);
    if (triage.confident()) {
        return triage.label();   // cheap model handled it — done
    }
    // Escalate only the uncertain fraction to the stronger model
    MessageCreateParams escalation = MessageCreateParams.builder()
        .model(Model.CLAUDE_OPUS_4_8)
        .maxTokens(500L)
        .addUserMessage("Carefully classify and explain this ticket: " + ticketText)
        .build();
    return client.messages().create(escalation).content().stream()
        .flatMap(block -> block.text().stream())
        .findFirst()
        .map(block -> block.text())
        .orElse("other");
}
```

If 80% of tickets are confidently triaged by Haiku at $1/$5 per MTok, and only 20% escalate to Opus at $5/$25, the blended cost is a fraction of routing everything to Opus — with no quality loss on the easy majority, because the escalation path exists precisely for the cases where the cheap model says "I'm not sure." The failure mode to guard against is a cheap model that's *overconfident* — always check the escalation rate against a labeled sample before trusting the split, and set the threshold (here, a literal self-reported confidence flag) based on measured accuracy, not vibes.

---

## Measure Before You Optimize

Every technique in this post has a cost of its own — a cache write premium, batch operational complexity, an extra triage call before the "real" one. None of them are free, and applied blindly they can make a system *more* expensive:

- Caching a prefix that changes every request pays the write premium with zero reads — worse than no caching.
- Batching latency-sensitive traffic breaks the product; the 50% saving doesn't matter if users are staring at a spinner.
- Routing to a cheap model without measuring its accuracy on your actual distribution can silently degrade quality while looking like a cost win on the invoice.

Instrument first: log `cacheReadInputTokens()` / `cacheCreationInputTokens()` / `inputTokens()` per request, track cost per request type, and know your actual latency requirements before reaching for any of these. Optimize the workload that's actually expensive, not the one you assume is.

---

## Practical Checklist

| Practice | Why it matters |
|----------|----------------|
| Put the stable prefix (system prompt, tools, RAG context) first, volatile content last | Prefix match — anything after a byte change is uncached |
| Add `cache_control` only where the prefix meets the model's minimum token count | Below the minimum, it silently writes and never reads |
| Verify with `cacheReadInputTokens()`, not assumption | A silent invalidator produces zero reads with no error |
| Reach for the Batches API only for non-interactive bulk work | 50% discount, but async — wrong tool under a human waiting |
| Combine batching with caching on shared prefixes | Discounts stack; both apply independently |
| Route easy/high-volume requests to a cheap model, escalate on low confidence | Blended cost drops without lowering quality on hard cases |
| Measure cost and latency per request type before optimizing | "Optimizing" the wrong workload can make things worse |

---

## Final Thoughts

Cost control for LLM applications is not a separate discipline from correctness — it's the same engineering discipline applied to a new kind of expensive, external call. The prefix is the bill, caching turns a repeatedly-read prefix into a cheap read, batching turns non-urgent bulk work into a 50%-off job, and routing turns "always use the strongest model" into "use the model the task actually needs." None of it replaces measurement: instrument the usage fields, know your latency requirements, and let real numbers — not assumptions — decide which lever to pull.
