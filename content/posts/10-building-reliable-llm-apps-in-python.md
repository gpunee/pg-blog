---
title: "Building Reliable LLM Applications in Python"
date: 2026-07-03
description: "Structured outputs, retries and idempotency, grounding over hallucination, evaluating model output, prompt caching, and treating cost and latency as features — best practices for LLM apps in Python with the Anthropic SDK."
tags:
  - Python
  - AI
  - LLM
  - Anthropic
  - Best Practices
categories:
  - AI
draft: false
---

## Introduction

Calling an LLM API is easy. Building an application on top of one that is *reliable* — that fails predictably, doesn't hallucinate its way into wrong answers, and doesn't surprise you with a bill — is a real engineering discipline.

The core mindset shift: **treat model output as a hypothesis to verify, not a fact to trust.** This post covers the practices that make Python LLM applications production-grade, using Anthropic's Claude and the official `anthropic` SDK.

---

## Pick the Right Model for the Task

Model choice is a decision, not a default. Match the tier to the difficulty of the task:

```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment

# Hard reasoning / agentic work → the strongest model
response = client.messages.create(
    model="claude-opus-4-8",
    max_tokens=4096,
    messages=[{"role": "user", "content": "..."}],
)

# High-volume, cost-sensitive classification → a cheaper capable model
cheap = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=256,
    messages=[{"role": "user", "content": "Classify sentiment: ..."}],
)
```

Never run an expensive model where a cheap one suffices, and never under-provision where quality matters. Cost and latency are features — track them.

---

## Get Structured Output — Don't Parse Prose

The single biggest source of fragility in LLM apps is scraping structured data out of free-form text. Prefer typed outputs validated against a schema. With the Anthropic SDK, `messages.parse()` validates the response against a Pydantic model for you:

```python
from pydantic import BaseModel

class Invoice(BaseModel):
    vendor: str
    total: float
    due_date: str

response = client.messages.parse(
    model="claude-opus-4-8",
    max_tokens=1024,
    messages=[{"role": "user", "content": f"Extract invoice fields:\n{raw_text}"}],
    output_format=Invoice,
)

invoice = response.parsed_output   # a validated Invoice instance
print(invoice.total)               # a float, guaranteed — no regex, no json.loads
```

The validation happens against a schema the model is constrained to, so you get a typed object instead of a string you have to hope parses. Structured output turns "the model usually returns JSON" into "the model returns *this shape*."

---

## Ground the Model — Don't Let It Hallucinate

An LLM will confidently invent facts. For anything that must be correct, give the model the source material and instruct it to answer *only* from that material — retrieval-augmented generation (RAG) in its simplest form:

```python
prompt = f"""Answer the question using ONLY the context below.
If the answer is not in the context, say "I don't know."

<context>
{retrieved_documents}
</context>

Question: {user_question}"""
```

Two things make this reliable: the explicit "only from context" instruction, and an explicit escape hatch ("say I don't know") so the model isn't pressured to fabricate. Then **cite** — have the model point at which passage it used, so a human can verify.

---

## Handle the Unhappy Path

Networks fail and rate limits happen. The Anthropic SDK already retries transient errors (429, 5xx, connection errors) with exponential backoff — configure it rather than reinventing it:

```python
client = anthropic.Anthropic(max_retries=4, timeout=30.0)
```

Catch the *specific* exceptions and branch on retryable vs. terminal:

```python
try:
    response = client.messages.create(...)
except anthropic.RateLimitError as exc:
    retry_after = int(exc.response.headers.get("retry-after", "60"))
    # back off and retry
except anthropic.BadRequestError:
    # a 400 is a bug in our request — do NOT retry, fix the payload
    raise
```

For any operation with side effects (charging a card, sending an email based on a model decision), make it **idempotent** — the model, or a retry, may trigger the same action twice.

---

## Put Control Flow in Code, Judgment in the Model

Use the model for judgment; use code for bookkeeping. Loops, branching, and fan-out belong in deterministic Python — not in a prompt asking the model to "keep going until done." For agentic tasks with tools, drive the loop yourself so you can intercept, validate, and log each tool call:

```python
messages = [{"role": "user", "content": user_input}]
while True:
    response = client.messages.create(
        model="claude-opus-4-8", max_tokens=4096,
        tools=tools, messages=messages,
    )
    if response.stop_reason == "end_turn":
        break
    messages.append({"role": "assistant", "content": response.content})

    tool_results = []
    for block in response.content:
        if block.type == "tool_use":
            result = execute_tool(block.name, block.input)   # YOUR validated code
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })
    messages.append({"role": "user", "content": tool_results})
```

The model decides *what* to do; your code decides *whether it's allowed* and records what happened.

---

## Evaluate Output Like Any Other Untrusted Input

You wouldn't ship a function without tests. Don't ship a prompt without evals. Build a small dataset of representative inputs with known-good outputs, and score the model against it whenever you change a prompt or model:

```python
def evaluate(cases: list[dict]) -> float:
    passed = 0
    for case in cases:
        out = extract_invoice(case["input"])
        if out.total == case["expected_total"]:
            passed += 1
    return passed / len(cases)
```

Evals catch the regression where a prompt tweak that helped one case quietly broke ten others — the LLM equivalent of a failing unit test.

---

## Cache Repeated Context to Cut Cost and Latency

If many requests share a large fixed prefix — a system prompt, a big document, few-shot examples — prompt caching serves that prefix at a fraction of the price and latency:

```python
response = client.messages.create(
    model="claude-opus-4-8",
    max_tokens=1024,
    system=[{
        "type": "text",
        "text": large_shared_context,
        "cache_control": {"type": "ephemeral"},
    }],
    messages=[{"role": "user", "content": question}],
)
# Verify it worked:
print(response.usage.cache_read_input_tokens)  # >0 means the cache was hit
```

Caching is a prefix match: keep the stable content first and put anything that varies per request (timestamps, the user's question) *after* it. If `cache_read_input_tokens` stays zero across repeated calls, something volatile is invalidating the prefix.

---

## Practical Checklist

| Practice | Why it matters |
|----------|----------------|
| Match model tier to task difficulty | Don't overpay or under-provision |
| Use structured outputs, not prose parsing | Typed data, no brittle regex |
| Ground answers in provided context + cite | Curbs hallucination |
| Configure SDK retries; branch on error type | Survive transient failures, fail fast on bugs |
| Make side-effecting actions idempotent | Retries and re-decisions are safe |
| Control flow in code, judgment in the model | Deterministic, debuggable |
| Keep an eval set; score on every change | Catch prompt/model regressions |
| Cache large shared prefixes | Lower cost and latency |
| Never send secrets/PII you don't need to | Anything sent externally may be retained |

---

## Final Thoughts

Reliable LLM applications aren't built by finding the perfect prompt. They're built with the same engineering discipline as any other system: strong typing at the boundary, verification of untrusted output, deterministic control flow, graceful failure handling, and measurable evaluation.

The model provides judgment. Everything around it — the structure, the checks, the guardrails — is your job. Get that right, and the LLM becomes a dependable component instead of a source of surprises.
