---
title: "Building Reliable LLM Applications in Java"
date: 2026-07-03
description: "Typed structured outputs, retries and idempotency, grounding over hallucination, evaluation, prompt caching, and agentic control flow — best practices for LLM apps on the JVM with the Anthropic Java SDK."
tags:
  - Java
  - AI
  - LLM
  - Anthropic
  - Best Practices
categories:
  - AI
draft: false
---

## Introduction

LLMs are usually associated with Python, but a great deal of production software — banking, enterprise backends, long-lived services — runs on the JVM, and those systems increasingly need to call language models too. Java's strong typing and mature tooling are genuine assets here: they push you toward exactly the discipline reliable LLM applications require.

The core mindset is the same in any language: **treat model output as a hypothesis to verify, not a fact to trust.** This post covers the practices that make Java LLM applications production-grade, using Anthropic's Claude and the official `anthropic-java` SDK.

---

## Pick the Right Model for the Task

Model choice is a decision, not a default. Match the tier to the difficulty of the task — the strongest model for hard reasoning, a cheaper capable model for high-volume simple work:

```java
import com.anthropic.client.AnthropicClient;
import com.anthropic.client.okhttp.AnthropicOkHttpClient;
import com.anthropic.models.messages.MessageCreateParams;
import com.anthropic.models.messages.Model;

AnthropicClient client = AnthropicOkHttpClient.fromEnv(); // reads ANTHROPIC_API_KEY

MessageCreateParams params = MessageCreateParams.builder()
    .model(Model.CLAUDE_OPUS_4_8)   // strongest tier for hard tasks
    .maxTokens(4096L)
    .addUserMessage("...")
    .build();
```

For high-volume classification, `Model.CLAUDE_HAIKU_4_5` costs a fraction as much. Never run an expensive model where a cheap one suffices; cost and latency are features to track, not afterthoughts.

---

## Get Typed Output — Don't Parse Prose

The biggest source of fragility in LLM apps is scraping structured data out of free-form text. Java's type system makes the better path natural: define a record for the shape you want and let the SDK derive a JSON schema, constrain the model to it, and hand you back a typed object.

```java
import com.anthropic.models.messages.StructuredMessageCreateParams;
import java.util.List;

record Invoice(String vendor, double total, String dueDate) {}

StructuredMessageCreateParams<Invoice> params = MessageCreateParams.builder()
    .model(Model.CLAUDE_OPUS_4_8)
    .maxTokens(1024L)
    .outputConfig(Invoice.class)            // schema derived from the record
    .addUserMessage("Extract invoice fields:\n" + rawText)
    .build();

client.messages().create(params).content().stream()
    .flatMap(block -> block.text().stream())
    .forEach(typed -> {
        Invoice invoice = typed.text();     // a validated Invoice, not a String
        System.out.println(invoice.total()); // a double — no manual JSON parsing
    });
```

This turns "the model usually returns JSON" into "the model returns *this record*." No `ObjectMapper` gymnastics, no defensive null-checking of hand-parsed fields.

---

## Ground the Model — Don't Let It Hallucinate

An LLM will confidently invent facts. For anything that must be correct, supply the source material and instruct the model to answer *only* from it, with an explicit escape hatch:

```java
String prompt = """
    Answer the question using ONLY the context below.
    If the answer is not in the context, say "I don't know."

    <context>
    %s
    </context>

    Question: %s""".formatted(retrievedDocuments, userQuestion);
```

The "only from context" instruction plus the "say I don't know" escape hatch together stop the model from fabricating to fill a gap. For auditability, have it cite which passage it used so a human can verify.

---

## Handle the Unhappy Path

Networks fail and rate limits happen. The Java SDK retries transient errors (429, 5xx, connection failures) with backoff — configure it rather than reinventing it:

```java
AnthropicClient client = AnthropicOkHttpClient.builder()
    .fromEnv()
    .maxRetries(4)
    .build();
```

Catch typed exceptions and branch on retryable vs. terminal — a 400 is a bug in your request, not something to retry:

```java
import com.anthropic.errors.RateLimitException;
import com.anthropic.errors.BadRequestException;

try {
    client.messages().create(params);
} catch (RateLimitException e) {
    // back off and retry
} catch (BadRequestException e) {
    // malformed request — fix the payload, do NOT retry
    throw e;
}
```

For any operation with side effects driven by a model decision — a payment, an outbound email — make it **idempotent**. A retry, or the model, may trigger the same action twice.

---

## Put Control Flow in Code, Judgment in the Model

Use the model for judgment; use Java for bookkeeping. Loops, branching, and fan-out belong in deterministic code. For tool-using (agentic) tasks, drive the loop yourself so you can validate, gate, and log every tool call before executing it:

```java
// Pseudocode shape — loop until the model stops requesting tools
while (true) {
    Message response = client.messages().create(paramsWithTools);
    if ("end_turn".equals(response.stopReason().orElse(null))) {
        break;
    }
    for (ContentBlock block : response.content()) {
        block.toolUse().ifPresent(toolUse -> {
            // YOUR code decides whether this call is allowed, then executes it
            String result = executeValidatedTool(toolUse.name(), toolUse.input());
            // append a tool_result and continue the loop
        });
    }
}
```

The model decides *what* to do; your code decides *whether it's permitted* and records what happened. This is where Java's guardrails — type checks, validation at boundaries, explicit error handling — pay off.

---

## Evaluate Output Like Any Other Untrusted Input

You wouldn't ship a method without a JUnit test. Don't ship a prompt without an eval. Keep a small dataset of representative inputs with known-good outputs and score the model against it whenever you change a prompt or switch models:

```java
double evaluate(List<TestCase> cases) {
    long passed = cases.stream()
        .filter(c -> extractInvoice(c.input()).total() == c.expectedTotal())
        .count();
    return (double) passed / cases.size();
}
```

Evals catch the regression where a prompt tweak that helped one case quietly broke ten others — the LLM equivalent of a failing test suite.

---

## Cache Repeated Context to Cut Cost and Latency

When many requests share a large fixed prefix — a system prompt, a big document, few-shot examples — prompt caching serves that prefix at a fraction of the cost and latency. Mark the stable block with a cache control and keep it first:

```java
import com.anthropic.models.messages.TextBlockParam;
import com.anthropic.models.messages.CacheControlEphemeral;
import java.util.List;

MessageCreateParams params = MessageCreateParams.builder()
    .model(Model.CLAUDE_OPUS_4_8)
    .maxTokens(1024L)
    .systemOfTextBlockParams(List.of(
        TextBlockParam.builder()
            .text(largeSharedContext)
            .cacheControl(CacheControlEphemeral.builder().build())
            .build()))
    .addUserMessage(question)
    .build();

Message response = client.messages().create(params);
System.out.println(response.usage().cacheReadInputTokens()); // >0 means cache hit
```

Caching is a prefix match — put the stable content first and anything that varies per request (the user's question, a timestamp) after it. If `cacheReadInputTokens` stays zero across repeated calls, something volatile is invalidating the prefix.

---

## Practical Checklist

| Practice | Why it matters |
|----------|----------------|
| Match model tier to task difficulty | Don't overpay or under-provision |
| Use typed structured outputs | Records, not hand-parsed JSON |
| Ground answers in provided context + cite | Curbs hallucination |
| Configure SDK retries; catch typed exceptions | Survive transients, fail fast on bugs |
| Make side-effecting actions idempotent | Retries and re-decisions are safe |
| Control flow in code, judgment in the model | Deterministic, debuggable |
| Keep an eval set; score on every change | Catch prompt/model regressions |
| Cache large shared prefixes | Lower cost and latency |
| Never send secrets/PII you don't need to | Anything sent externally may be retained |

---

## Final Thoughts

Reliable LLM applications aren't built by finding the perfect prompt. They're built with the same engineering discipline Java developers already practice: strong types at the boundary, verification of untrusted output, deterministic control flow, explicit error handling, and measurable tests.

The model provides judgment. The typed, tested, guard-railed system around it is what makes that judgment safe to depend on — and that system is exactly the kind of thing the JVM ecosystem is built to run well.
