---
title: "LLM Frameworks vs. the Raw SDK in Python"
date: 2026-07-04
description: "Building the same small tool-using agent on the raw Anthropic SDK and on LangChain, to see honestly where the framework earns its weight and where it's ceremony."
tags:
  - Python
  - AI
  - LLM
  - LangChain
  - Anthropic
categories:
  - Python
draft: false
---

## Introduction

Every LLM ecosystem now has at least one framework promising to make agents easier to build, and every framework post either oversells the abstraction or dismisses it outright. Neither is useful. The only honest way to evaluate a framework is to build the same thing twice — once on the vendor's raw SDK, once on the framework — and compare what each version actually cost you and actually gave you back.

This post builds the small tool-using agent from [Building Agentic Workflows in Python]({{< ref "15-building-agentic-workflows-in-python.md" >}}) twice: once directly on the Anthropic SDK, once on [LangChain](https://python.langchain.com/) — a Python framework for models, tools, and agent loops built on top of [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview), its lower-level orchestration runtime. We'll also touch the RAG pipeline from [RAG From Scratch in Python]({{< ref "21-rag-from-scratch-in-python.md" >}}) — retrieval is exactly the kind of component a framework's tool abstraction is built to wrap. The goal isn't to crown a winner; it's to give you a way to make this decision for your own project instead of inheriting someone else's blog-post conclusion.

---

## The Agent We're Building Twice

To keep the comparison fair, both versions get the identical agent: one system prompt, two tools, one user turn, running until the model stops asking for tools.

- **`get_weather(location: str) -> str`** — the same illustrative weather lookup from the agentic-workflows post, so the tool-calling shape lines up exactly with what you've already seen built by hand.
- **`calculate(operation, a, b) -> float`** — a second tool with a constrained, whitelisted `operation` argument (`"add" | "subtract" | "multiply" | "divide"`) rather than a free-text expression. This is deliberate: it's the "never `eval` a model-supplied string" lesson from the agentic-workflows post, made concrete as a schema choice instead of a runtime check.

Both tools are defined once and reused unchanged across every version below — the frameworks differ in how they turn a Python function into something the model can call, not in what the agent does.

```python
from typing import Literal
from langchain.tools import tool

@tool
def get_weather(location: str) -> str:
    """Get current weather for a location.

    Args:
        location: City and state, e.g. San Francisco, CA.
    """
    return f"Sunny, 72°F in {location}"

@tool
def calculate(operation: Literal["add", "subtract", "multiply", "divide"], a: float, b: float) -> float:
    """Perform basic arithmetic on two numbers.

    Args:
        operation: One of "add", "subtract", "multiply", "divide".
        a: The first operand.
        b: The second operand.
    """
    if operation == "add":
        return a + b
    if operation == "subtract":
        return a - b
    if operation == "multiply":
        return a * b
    if operation == "divide":
        if b == 0:
            raise ValueError("Division by zero")
        return a / b
    raise ValueError(f"Unknown operation: {operation}")
```

`@tool` here is LangChain's decorator (`from langchain.tools import tool`) — but notice the function itself is plain Python with type hints and a docstring; that part would be identical if you never installed LangChain at all.

---

## Path A: The Raw Anthropic SDK

This is the manual loop from [Building Agentic Workflows in Python]({{< ref "15-building-agentic-workflows-in-python.md" >}}), condensed to this agent's two tools. Every tool call passes through code you wrote and can inspect:

```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env — never hardcode

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get current weather for a location",
        "input_schema": {
            "type": "object",
            "properties": {"location": {"type": "string", "description": "City and state"}},
            "required": ["location"],
        },
    },
    {
        "name": "calculate",
        "description": "Perform basic arithmetic on two numbers",
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": ["add", "subtract", "multiply", "divide"]},
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["operation", "a", "b"],
        },
    },
]

MAX_ITERATIONS = 10
messages = [{"role": "user", "content": "What's the weather in Austin, and what's 12 divided by 4?"}]
iterations = 0

while True:
    iterations += 1
    if iterations > MAX_ITERATIONS:
        raise RuntimeError("Agent exceeded iteration cap — stopping")

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=16000,
        thinking={"type": "adaptive"},
        tools=TOOLS,
        messages=messages,
    )
    if response.stop_reason == "end_turn":
        break

    messages.append({"role": "assistant", "content": response.content})
    tool_results = []
    for block in response.content:
        if block.type != "tool_use":
            continue
        # Validate/whitelist BEFORE executing — block.input is model-provided, untrusted data
        result = execute_validated_tool(block.name, block.input)  # dispatches to get_weather/calculate
        tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(result)})
    messages.append({"role": "user", "content": tool_results})
```

Roughly 40 lines, all of it visible: the JSON schemas, the loop, the iteration cap, and one explicit choke point (`execute_validated_tool`) where every tool call is checked before it runs.

---

## Path B: LangChain — Two Levels of Abstraction

LangChain gives you the same choice the raw SDK does — write the loop, or hand it off — but at a different point in the abstraction stack. `langchain-anthropic`'s `ChatAnthropic` wraps the messages API; `bind_tools` replaces hand-written JSON schemas with the same typed functions you already defined.

```bash
pip install -U langchain langchain-anthropic
```

### B1 — The Low-Level Loop (`bind_tools`), for Comparable Control

```python
from langchain_anthropic import ChatAnthropic
from langchain.messages import HumanMessage, ToolMessage

model = ChatAnthropic(model="claude-opus-4-8", max_tokens=16000, thinking={"type": "adaptive"})
model_with_tools = model.bind_tools([get_weather, calculate])

MAX_ITERATIONS = 10
messages = [HumanMessage("What's the weather in Austin, and what's 12 divided by 4?")]
response = model_with_tools.invoke(messages)

iterations = 0
while response.tool_calls:
    iterations += 1
    if iterations > MAX_ITERATIONS:
        raise RuntimeError("Agent exceeded iteration cap — stopping")
    tool_messages = []
    for tool_call in response.tool_calls:
        # tool_call["args"] is still model-provided, untrusted data — validate before dispatch
        result = execute_validated_tool(tool_call["name"], tool_call["args"])
        tool_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
    messages = [*messages, response, *tool_messages]
    response = model_with_tools.invoke(messages)
```

This is nearly a line-for-line match with the raw SDK loop, iteration cap included — `bind_tools` generates the JSON schema from the function signature and docstring instead of you writing it by hand, and `.tool_calls` gives you parsed dicts instead of raw content blocks. Everything else — the `while` loop, the cap, the validation choke point, the message bookkeeping — is still your code.

### B2 — The High-Level Harness (`create_agent`), for Convenience

```python
from langchain.agents import create_agent

agent = create_agent(
    model=model,  # the same ChatAnthropic instance, thinking config included
    tools=[get_weather, calculate],
    system_prompt="You are a helpful assistant with weather and calculator tools.",
)

result = agent.invoke({
    "messages": [{"role": "user", "content": "What's the weather in Austin, and what's 12 divided by 4?"}]
})
final_message = result["messages"][-1]
print(final_message.content)
```

`create_agent` runs the entire loop — call, detect tool use, execute, feed back, repeat — internally, on top of LangGraph. Nine lines replace the `while` loop entirely; the trade-off is that the validation you wrote explicitly in `execute_validated_tool` above now has to live *inside* `get_weather`/`calculate` themselves (the same manual-loop-vs-tool-runner trade-off the agentic-workflows post made about the Anthropic SDK's own tool runner — a framework doesn't remove that trade-off, it just relocates it).

---

## Where the Framework Actually Earns Its Weight

For *this* agent — two tools, one provider, one turn — `create_agent` mostly buys convenience you could get from the SDK's own tool runner. The framework's case gets much stronger the moment your requirements grow past a single call:

| Need | Raw SDK | LangChain |
|---|---|---|
| Swap providers (Anthropic → another model) without rewriting the agent | Rewrite the call and the tool schema format | Swap the `model=` argument; `@tool`-decorated functions are provider-agnostic |
| Multi-turn conversation persisted across process restarts | Hand-roll message-log storage and replay | `checkpointer=` + `thread_id` (built on LangGraph's durable execution) |
| Retry/fallback policy for transient model or tool errors | Wrap every call site in `try`/`except` yourself | `ModelRetryMiddleware`, `ToolRetryMiddleware` — declared once, applied everywhere |
| PII redaction or other cross-cutting guardrails | A function you remember to call at every boundary | `PIIMiddleware` — a policy applied to the loop, not to each call site |
| Typed hand-off between agent steps | `client.messages.parse(..., output_format=Model)` | `create_agent(..., response_format=Model)` — same idea, same win over parsing prose |

The pattern across every row: the framework's value shows up when there's a *policy* (retry, redaction, persistence, provider choice) that should apply uniformly across many call sites, not when there's one call site. A single small agent has, definitionally, one call site.

---

## Where It's Ceremony

For the agent this post builds, `create_agent` costs you a second dependency (`langchain` on top of `langchain-anthropic`), an abstraction layer between your code and the documented Anthropic API shape, and a framework release cadence you now inherit — LangChain's own agent API has changed shape more than once as the ecosystem matured, which is exactly the risk this post's verification bar exists to catch (every snippet above was checked against the current docs, not memory, as of this writing). None of that is a reason to avoid frameworks; it's a reason to install one for a *reason* — the middleware table above, not habit.

**Rule of thumb:** reach for `bind_tools` (or the raw SDK) while you have one provider, one call site, and no cross-cutting policy to enforce. Reach for `create_agent` when you need at least one row from the table above — provider portability, persisted multi-turn state, or middleware you'd otherwise duplicate by hand.

---

## The Trust Boundary Doesn't Move

Whichever path you pick, the security posture from [Building Agentic Workflows in Python]({{< ref "15-building-agentic-workflows-in-python.md" >}}) is unchanged: `tool_call.input` (raw SDK), `tool_call["args"]` (`bind_tools`), and the arguments a `@tool`-decorated function receives from `create_agent` are all **the same untrusted, model-provided data**. A framework generating your JSON schema does not validate the *values* the model sends back — `calculate`'s `Literal["add", "subtract", "multiply", "divide"]` rejects an out-of-set operation at the type-coercion layer, but a tool with a free-text argument still needs the same whitelist-and-bound-range discipline regardless of which of the three call shapes above invoked it. Never string-interpolate a tool argument into a shell command or SQL query, framework or no framework.

---

## Practical Checklist

| Practice | Why it matters |
|----------|----------------|
| Build the raw-SDK version first, even briefly | Gives you a control to compare the framework against, and a fallback if the framework misbehaves |
| Pick a framework for a *policy* you need repeated everywhere, not for one call site | The convenience win is in cross-cutting concerns (retries, redaction, persistence), not a single loop |
| Keep tool functions provider-agnostic (typed args, docstrings) | The same `@tool`-decorated function works with `bind_tools` and `create_agent` unchanged |
| Validate tool arguments inside the tool, not just at a manual choke point | `create_agent` moves the choke point *into* the tool function — validation has to move with it |
| Verify framework APIs against current docs before shipping | Framework surfaces move faster than SDK surfaces; a stale snippet is worse than none |
| Never `eval` a model-supplied expression | Prefer a whitelisted enum + typed operands, as `calculate` does here, over parsing free text |

---

## Final Thoughts

The raw SDK and a framework are solving different problems: the SDK gives you the documented shape of one provider's API; a framework gives you a shape that's supposed to stay stable while providers, persistence, and policy requirements change underneath it. For a single small agent, that stability is mostly unrealized — you're paying the abstraction's overhead without yet needing what it buys. Build the raw version first so you know exactly what the framework is doing on your behalf, and add the framework layer only once a specific requirement — provider portability, persisted state, a cross-cutting guardrail — asks for it by name.
