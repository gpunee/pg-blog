---
title: "Building Agentic Workflows in Java"
description: "When a tool-calling loop earns its complexity over a single call or a scripted pipeline, the manual and SDK-provided agentic loops in Java, and the guardrails — validation, approval, iteration caps — that keep an agent safe to run."
date: 2026-07-03
tags:
  - Java
  - AI
  - Agentic
  - LLM
  - Anthropic
categories:
  - Java
draft: false
---

## Introduction

"Agent" has become the word for any program that calls an LLM more than once, which makes it a word worth being precise about. An agent, in the sense this post uses, is a loop: the model decides which tool to call next, your code executes it, and the result feeds back in — repeating until the model decides it's done. That's a genuinely different (and riskier) shape than a single request/response call.

This post builds on [Building Reliable LLM Applications in Java]({{< ref "11-building-reliable-llm-apps-in-java.md" >}}): everything said there about retries, typed output, and evaluation still applies once you add a loop — it just applies to *every iteration*, and now the model is also choosing which side effects to trigger. We'll cover when an agent is actually warranted, the loop itself (manual and SDK-assisted), and the safety controls that make handing a model the wheel defensible.

---

## When to Build an Agent — and When Not To

Reach for an agent only when the task is genuinely multi-step and open-ended: the number and order of actions can't be known ahead of time, so a fixed pipeline can't express it. Most tasks that *feel* agentic are actually better served by something simpler and more debuggable. There's a ladder, and you should stop climbing it the moment the task is satisfied:

1. **A single LLM call.** Classify this ticket. Summarize this document. If one prompt in, one answer out solves it, that's the whole system.
2. **A code-orchestrated workflow.** A fixed sequence of LLM calls and deterministic steps — call the model to extract fields, validate them in code, call the model again to draft a reply. The *order* of steps is known in advance and lives in Java, not in the model's head.
3. **An agent.** The model itself decides which tool to call, how many times, and in what order, based on what it learns from each result. Reserve this for tasks where that open-endedness is the point — a research assistant that doesn't know in advance how many searches it needs, a debugging helper that has to react to whatever the last command printed.

Before building step 3, run the task past four checks. If any answer is "no," stay at step 1 or 2:

- **Complexity** — is the task actually variable enough that a fixed sequence can't express it? If you can already write down the steps, write them down — in code, not in a system prompt.
- **Value** — does solving it well matter enough to justify the added latency, cost, and failure surface of a loop? A loop that runs five model calls to do what one call could do is a net loss.
- **Viability** — can the model reliably succeed at each step with the tools you can realistically give it? An agent whose tools are unreliable or ambiguous will loop, retry the wrong thing, or confidently do the wrong thing with confidence.
- **Cost of error** — what happens when it gets a step wrong? An agent that can send an email or delete a record needs a fundamentally different safety posture than one that only reads.

An agent is a deliberate escalation, not a default. Most production LLM features never need one.

---

## The Agentic Loop

Once an agent is warranted, the shape is the same regardless of the tools involved: call the model with a list of available tools; if it responds asking to use one (`stop_reason` is `tool_use`), execute that tool in your own code and send the result back as a `tool_result`; repeat until the model responds with `end_turn`. Two ways to run that loop in Java — write it by hand for full control, or let the SDK's tool runner drive it for you.

### The Manual Loop — Full Control

Writing the loop yourself means every tool call passes through your code before it executes, which is where you validate arguments, log the decision, and gate anything irreversible:

```java
import com.anthropic.client.AnthropicClient;
import com.anthropic.client.okhttp.AnthropicOkHttpClient;
import com.anthropic.models.messages.*;
import java.util.List;
import java.util.ArrayList;

AnthropicClient client = AnthropicOkHttpClient.fromEnv(); // reads ANTHROPIC_API_KEY

List<MessageParam> messages = new ArrayList<>();
messages.add(MessageParam.builder()
    .role(MessageParam.Role.USER)
    .content(userInput)
    .build());

Message response;
int iterations = 0;
while (true) {
    if (++iterations > MAX_ITERATIONS) {
        throw new IllegalStateException("Agent exceeded iteration cap — stopping");
    }

    MessageCreateParams params = MessageCreateParams.builder()
        .model(Model.CLAUDE_OPUS_4_8)
        .maxTokens(16000L)
        .thinking(ThinkingConfigAdaptive.builder().build())
        .tools(tools)
        .messages(messages)
        .build();

    response = client.messages().create(params);

    if (response.stopReason().isPresent()
            && response.stopReason().get().toString().equals("end_turn")) {
        break;
    }

    // Log the assistant turn (including any tool_use requests) before acting on it
    messages.add(MessageParam.builder()
        .role(MessageParam.Role.ASSISTANT)
        .contentOfBlockParams(toBlockParams(response.content()))
        .build());

    List<ContentBlockParam> toolResults = new ArrayList<>();
    for (ContentBlock block : response.content()) {
        block.toolUse().ifPresent(toolUse -> {
            // Validate BEFORE executing — tool.input is model-provided, untrusted data
            String result = executeValidatedTool(toolUse.name(), toolUse.input());
            toolResults.add(ContentBlockParam.ofToolResult(
                ToolResultBlockParam.builder()
                    .toolUseId(toolUse.id())
                    .content(result)
                    .build()));
        });
    }
    messages.add(MessageParam.builder()
        .role(MessageParam.Role.USER)
        .contentOfBlockParams(toolResults)
        .build());
}
```

Two things earn their keep here that a convenience runner would hide: the `MAX_ITERATIONS` cap, and the log point right before the tool result round-trip. Both are cheap to add and expensive to retrofit after an agent has looped in production for an hour.

### The SDK Tool Runner — Convenience

When you don't need to intercept every call — a low-stakes, read-only agent, or a prototype — the beta tool runner drives the same loop for you. Define each tool as a small class implementing `Supplier`, annotated so the SDK can derive its JSON schema:

```java
import com.anthropic.models.beta.messages.MessageCreateParams;
import com.anthropic.models.beta.messages.BetaMessage;
import com.anthropic.helpers.BetaToolRunner;
import com.fasterxml.jackson.annotation.JsonClassDescription;
import com.fasterxml.jackson.annotation.JsonPropertyDescription;
import java.util.function.Supplier;

@JsonClassDescription("Get the weather in a given location")
static class GetWeather implements Supplier<String> {
    @JsonPropertyDescription("The city and state, e.g. San Francisco, CA")
    public String location;

    @Override
    public String get() {
        return "Sunny, 72F in " + location;
    }
}

BetaToolRunner runner = client.beta().messages().toolRunner(
    MessageCreateParams.builder()
        .model("claude-opus-4-8")
        .maxTokens(16000L)
        .addTool(GetWeather.class)
        .addUserMessage("What's the weather in San Francisco?")
        .build());

for (BetaMessage message : runner) {
    // each iteration is a BetaMessage; the loop ends when Claude is done
}
```

The trade-off is explicit: the runner is fewer lines, but your validation and approval logic has to live *inside* the tool's `get()` method rather than at a single choke point between the model and execution. For anything past a read-only demo, the manual loop's explicit checkpoint is worth the extra code.

---

## Determinism Where It Matters

The loop's *shape* — how many iterations are allowed, what counts as done, how a failed tool call is retried — belongs in Java, not in a system prompt asking the model to "keep trying until it works." As covered in [Building Reliable LLM Applications in Java]({{< ref "11-building-reliable-llm-apps-in-java.md" >}}), use the model for judgment (which tool, with what arguments, when to stop) and code for bookkeeping (the loop, the retry policy, the cap, the audit log). An agent that reasons its own way through retry logic in natural language is slower, more expensive, and less predictable than a `catch` block that already knows what to do with a transient failure.

---

## Structured Hand-offs Between Steps

Free-text hand-offs between agent steps are where errors compound silently — a slightly malformed field from step two becomes a wrong argument in step three's tool call. Where a step's output needs to be *used* by the next step (not just displayed to a person), get it back as a typed, schema-validated object instead of prose to re-parse:

```java
import com.anthropic.models.messages.StructuredMessageCreateParams;

record PlanStep(String action, boolean done) {}

StructuredMessageCreateParams<PlanStep> params = MessageCreateParams.builder()
    .model(Model.CLAUDE_OPUS_4_8)
    .maxTokens(16000L)
    .outputConfig(PlanStep.class)
    .addUserMessage("What is the next step, and are we done?")
    .build();

client.messages().create(params).content().stream()
    .flatMap(block -> block.text().stream())
    .forEach(typed -> {
        PlanStep step = typed.text(); // a validated PlanStep, not a String to parse
        if (step.done()) {
            // stop the loop deterministically — no guessing from prose
        }
    });
```

A typed `PlanStep` either deserializes or it doesn't; there's no regex trying to guess whether the model meant "done" or "we're basically done."

---

## Safety and Cost — Mandatory, Not Optional

An agent is a program that decides, at runtime, which of your functions to call and with what arguments — based on text it read. Treat every tool as an attack surface accordingly:

- **Validate and whitelist tool inputs.** `toolUse.input()` is model-provided data and must be treated as untrusted, exactly like a request body from the network. Whitelist allowed values, bound numeric ranges, and reject anything that doesn't fit the tool's contract *before* it reaches your execution code — never string-interpolate a model-supplied argument into a shell command or a SQL query.
- **Require human approval before irreversible or outward-facing actions.** Reading a file or querying an API is one risk tier; sending an email, deleting a record, or moving money is another. Gate the latter behind an explicit approval step — a human confirmation, a dry-run preview, or at minimum a hard-coded allowlist of safe operations — never let the model's own judgment be the last check before an irreversible effect.
- **Cap loop iterations.** Every agentic loop needs a hard `MAX_ITERATIONS` (or a wall-clock timeout). Without one, a confused model can loop indefinitely, burning tokens and possibly retrying a failing tool call forever.
- **Track token cost and latency as first-class metrics.** An agent's cost is the sum of every iteration, not one call — instrument `usage()` per turn and alert on runaway loops the same way you'd alert on a runaway retry storm.
- **Never hardcode API keys.** Every example above reads `ANTHROPIC_API_KEY` via `AnthropicOkHttpClient.fromEnv()` — no key ever appears in source, config committed to version control, or logs.

---

## Practical Takeaways

- Climb the ladder only as far as the task requires: single call → code-orchestrated workflow → agent. Most tasks stop at step one or two.
- Run the four checks — complexity, value, viability, cost of error — before building a loop; any "no" is a reason to stay simpler.
- The manual loop trades verbosity for a single choke point to validate, log, and gate every tool call; the SDK tool runner trades that control for convenience — pick deliberately, not by default.
- Keep control flow (the loop, retries, the iteration cap) in Java; keep the model doing judgment.
- Use structured, typed hand-offs between steps instead of parsing prose.
- Validate tool inputs as untrusted data, gate irreversible actions behind approval, cap iterations, and instrument cost — an agent without these is a liability, not a feature.
