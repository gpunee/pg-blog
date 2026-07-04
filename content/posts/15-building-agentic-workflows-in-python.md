---
title: "Building Agentic Workflows in Python"
description: "When a tool-calling loop earns its complexity over a single call or a scripted pipeline, the manual and SDK-provided agentic loops in Python, and the guardrails — validation, approval, iteration caps — that keep an agent safe to run."
date: 2026-07-03
tags:
  - Python
  - AI
  - Agentic
  - LLM
  - Anthropic
categories:
  - Python
draft: false
---

## Introduction

"Agent" has become the word for any program that calls an LLM more than once, which makes it a word worth being precise about. An agent, in the sense this post uses, is a loop: the model decides which tool to call next, your code executes it, and the result feeds back in — repeating until the model decides it's done. That's a genuinely different (and riskier) shape than a single request/response call.

This post builds on [Building Reliable LLM Applications in Python]({{< ref "10-building-reliable-llm-apps-in-python.md" >}}): everything said there about retries, structured output, and evaluation still applies once you add a loop — it just applies to *every iteration*, and now the model is also choosing which side effects to trigger. We'll cover when an agent is actually warranted, the loop itself (manual and SDK-assisted), and the safety controls that make handing a model the wheel defensible.

---

## When to Build an Agent — and When Not To

Reach for an agent only when the task is genuinely multi-step and open-ended: the number and order of actions can't be known ahead of time, so a fixed pipeline can't express it. Most tasks that *feel* agentic are actually better served by something simpler and more debuggable. There's a ladder, and you should stop climbing it the moment the task is satisfied:

1. **A single LLM call.** Classify this ticket. Summarize this document. If one prompt in, one answer out solves it, that's the whole system.
2. **A code-orchestrated workflow.** A fixed sequence of LLM calls and deterministic steps — call the model to extract fields, validate them in code, call the model again to draft a reply. The *order* of steps is known in advance and lives in Python, not in the model's head.
3. **An agent.** The model itself decides which tool to call, how many times, and in what order, based on what it learns from each result. Reserve this for tasks where that open-endedness is the point — a research assistant that doesn't know in advance how many searches it needs, a debugging helper that has to react to whatever the last command printed.

Before building step 3, run the task past four checks. If any answer is "no," stay at step 1 or 2:

- **Complexity** — is the task actually variable enough that a fixed sequence can't express it? If you can already write down the steps, write them down — in code, not in a system prompt.
- **Value** — does solving it well matter enough to justify the added latency, cost, and failure surface of a loop? A loop that runs five model calls to do what one call could do is a net loss.
- **Viability** — can the model reliably succeed at each step with the tools you can realistically give it? An agent whose tools are unreliable or ambiguous will loop, retry the wrong thing, or confidently do the wrong thing with confidence.
- **Cost of error** — what happens when it gets a step wrong? An agent that can send an email or delete a record needs a fundamentally different safety posture than one that only reads.

An agent is a deliberate escalation, not a default. Most production LLM features never need one.

---

## The Agentic Loop

Once an agent is warranted, the shape is the same regardless of the tools involved: call the model with a list of available tools; if it responds asking to use one (`stop_reason == "tool_use"`), execute that tool in your own code and send the result back as a `tool_result`; repeat until the model responds with `end_turn`. Two ways to run that loop in Python — write it by hand for full control, or let the SDK's tool runner drive it for you.

### The Manual Loop — Full Control

Writing the loop yourself means every tool call passes through your code before it executes, which is where you validate arguments, log the decision, and gate anything irreversible:

```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env — never hardcode

MAX_ITERATIONS = 10

messages = [{"role": "user", "content": user_input}]
iterations = 0

while True:
    iterations += 1
    if iterations > MAX_ITERATIONS:
        raise RuntimeError("Agent exceeded iteration cap — stopping")

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=16000,
        thinking={"type": "adaptive"},
        tools=tools,
        messages=messages,
    )

    if response.stop_reason == "end_turn":
        break

    tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

    # Log the assistant turn (including any tool_use requests) before acting on it
    messages.append({"role": "assistant", "content": response.content})

    tool_results = []
    for tool in tool_use_blocks:
        # Validate BEFORE executing — tool.input is model-provided, untrusted data
        result = execute_validated_tool(tool.name, tool.input)
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": tool.id,
            "content": result,
        })
    messages.append({"role": "user", "content": tool_results})

final_text = next(b.text for b in response.content if b.type == "text")
```

Two things earn their keep here that a convenience runner would hide: the `MAX_ITERATIONS` cap, and the log point right before the tool result round-trip. Both are cheap to add and expensive to retrofit after an agent has looped in production for an hour.

### The SDK Tool Runner — Convenience

When you don't need to intercept every call — a low-stakes, read-only agent, or a prototype — the beta tool runner drives the same loop for you. Decorate a plain function with `@beta_tool`; its docstring becomes the tool description the model sees:

```python
from anthropic import beta_tool

@beta_tool
def get_weather(location: str) -> str:
    """Get current weather for a location.

    Args:
        location: City and state, e.g. San Francisco, CA.
    """
    return f"Sunny, 72°F in {location}"

runner = client.beta.messages.tool_runner(
    model="claude-opus-4-8",
    max_tokens=16000,
    tools=[get_weather],
    messages=[{"role": "user", "content": "Weather in Paris?"}],
)
for message in runner:
    ...  # each iteration is a BetaMessage; loop ends when Claude is done
```

The trade-off is explicit: the runner is fewer lines, but your validation and approval logic has to live *inside* the tool function rather than at a single choke point between the model and execution. For anything past a read-only demo, the manual loop's explicit checkpoint is worth the extra code.

---

## Determinism Where It Matters

The loop's *shape* — how many iterations are allowed, what counts as done, how a failed tool call is retried — belongs in Python, not in a system prompt asking the model to "keep trying until it works." As covered in [Building Reliable LLM Applications in Python]({{< ref "10-building-reliable-llm-apps-in-python.md" >}}), use the model for judgment (which tool, with what arguments, when to stop) and code for bookkeeping (the loop, the retry policy, the cap, the audit log). An agent that reasons its own way through retry logic in natural language is slower, more expensive, and less predictable than an `except` block that already knows what to do with a transient failure.

---

## Structured Hand-offs Between Steps

Free-text hand-offs between agent steps are where errors compound silently — a slightly malformed field from step two becomes a wrong argument in step three's tool call. Where a step's output needs to be *used* by the next step (not just displayed to a person), get it back as a validated, typed object instead of prose to re-parse:

```python
from pydantic import BaseModel

class PlanStep(BaseModel):
    action: str
    done: bool

response = client.messages.parse(
    model="claude-opus-4-8",
    max_tokens=16000,
    messages=[{"role": "user", "content": "What is the next step, and are we done?"}],
    output_format=PlanStep,
)

step = response.parsed_output   # a validated PlanStep, not a string to parse
if step.done:
    ...  # stop the loop deterministically — no guessing from prose
```

A validated `PlanStep` either parses or raises; there's no regex trying to guess whether the model meant "done" or "we're basically done."

---

## Safety and Cost — Mandatory, Not Optional

An agent is a program that decides, at runtime, which of your functions to call and with what arguments — based on text it read. Treat every tool as an attack surface accordingly:

- **Validate and whitelist tool inputs.** `tool.input` (or a tool function's arguments) is model-provided data and must be treated as untrusted, exactly like a request body from the network. Whitelist allowed values, bound numeric ranges, and reject anything that doesn't fit the tool's contract *before* it reaches your execution code — never string-interpolate a model-supplied argument into a shell command or a SQL query.
- **Require human approval before irreversible or outward-facing actions.** Reading a file or querying an API is one risk tier; sending an email, deleting a record, or moving money is another. Gate the latter behind an explicit approval step — a human confirmation, a dry-run preview, or at minimum a hard-coded allowlist of safe operations — never let the model's own judgment be the last check before an irreversible effect.
- **Cap loop iterations.** Every agentic loop needs a hard `MAX_ITERATIONS` (or a wall-clock timeout). Without one, a confused model can loop indefinitely, burning tokens and possibly retrying a failing tool call forever.
- **Track token cost and latency as first-class metrics.** An agent's cost is the sum of every iteration, not one call — instrument `response.usage` per turn and alert on runaway loops the same way you'd alert on a runaway retry storm.
- **Never hardcode API keys.** Every example above reads `ANTHROPIC_API_KEY` via `anthropic.Anthropic()` — no key ever appears in source, config committed to version control, or logs.

---

## Practical Takeaways

- Climb the ladder only as far as the task requires: single call → code-orchestrated workflow → agent. Most tasks stop at step one or two.
- Run the four checks — complexity, value, viability, cost of error — before building a loop; any "no" is a reason to stay simpler.
- The manual loop trades verbosity for a single choke point to validate, log, and gate every tool call; the SDK tool runner trades that control for convenience — pick deliberately, not by default.
- Keep control flow (the loop, retries, the iteration cap) in Python; keep the model doing judgment.
- Use structured, typed hand-offs between steps instead of parsing prose.
- Validate tool inputs as untrusted data, gate irreversible actions behind approval, cap iterations, and instrument cost — an agent without these is a liability, not a feature.
