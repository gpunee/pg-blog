---
title: "Prompt Caching and Cost Control in Python"
date: 2026-07-04
description: "Token economics, cache_control prompt caching, the Batches API, and cheap-to-strong model routing — controlling LLM spend in Python without sacrificing quality."
tags:
  - Python
  - AI
  - LLM
  - Performance
  - Cost
  - Anthropic
categories:
  - Python
draft: false
---

## Introduction

{{< ref "10-building-reliable-llm-apps-in-python.md" >}} closed with a section on picking the right model per task and caching a shared prefix. That was the entry point into a bigger discipline: **LLM spend is an engineering variable, not a fixed bill** — one you can measure and reduce with the same rigor you'd apply to query latency or memory footprint.

This post goes deeper on four levers: how input/output pricing actually works and why the *prefix* is usually where the money goes, the exact `cache_control` shape and how to prove a cache hit instead of assuming one, the Batches API for work that isn't latency-sensitive, and model routing — a cheap model triaging requests and escalating only the hard ones. The throughline is honest: **measure before you optimize.** Every lever here has its own cost; misapplied, it makes things slower or pricier, not cheaper.

---

## Token Economics: Why the Prefix Is the Bill

LLM providers price input and output tokens separately, and **output always costs more** — generation is autoregressive (each token depends on every one before it), while input can be processed in parallel. Representative pricing from the current model catalog:

| Model | Input | Output |
|---|---:|---:|
| Claude Opus 4.8 | $5.00 / MTok | $25.00 / MTok |
| Claude Sonnet 5 | $3.00 / MTok | $15.00 / MTok |
| Claude Haiku 4.5 | $1.00 / MTok | $5.00 / MTok |

Two things follow:

1. **A long system prompt, tool list, or RAG context is billed as input on *every* request**, not written once. Send a 20K-token system prompt on 10,000 requests and that's 200M input tokens — at Opus 4.8 rates, $1,000 before the model has generated a single output token. The **shared prefix**, not the user's actual question, is usually the dominant cost.
2. **Verbose output costs twice** — once directly (more output tokens billed at the higher rate), and again because the next turn's history carries that verbosity forward as input. Asking for concise output and setting a sane `max_tokens` is a cost control, not just a style choice.

This is why the two techniques below — caching the stable prefix, and not running every request through the most expensive model — are the highest-leverage levers, in that order.

---

## Prompt Caching: Pay to Write Once, Read Cheaply

Prompt caching marks a **stable prefix** of a request — a system prompt, tool definitions, retrieved RAG context — so a later request with an identical prefix reads it back cheaply instead of reprocessing it. Grounded in the bundled `claude-api` skill's `shared/prompt-caching.md`:

- **It's a prefix match.** The cache key derives from the exact bytes up to each `cache_control` breakpoint. One byte different anywhere in the prefix — an interpolated timestamp, a reordered JSON key, a reordered tool list — invalidates everything downstream of it.
- **Render order is `tools` → `system` → `messages`.** A breakpoint on the last `system` block caches tools *and* system together.
- **Cache reads cost ~0.1× base input price; cache writes cost 1.25× (5-minute TTL) or 2× (1-hour TTL).** At a 5-minute TTL, two requests already break even (1.25× + 0.1× vs. 2× uncached); a 1-hour TTL needs roughly three requests to pay off the higher write cost.
- **The minimum cacheable prefix is model-dependent** — Opus 4.8 needs at least 4,096 tokens. Below that, `cache_control` silently does nothing: no error, just `cache_creation_input_tokens: 0`.

### The exact shape

```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment

# STABLE_SYSTEM_PROMPT holds the tool docs / policy text / retrieved corpus —
# large, and byte-identical across many requests.
response = client.messages.create(
    model="claude-opus-4-8",
    max_tokens=1024,
    system=[{
        "type": "text",
        "text": STABLE_SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"},   # default TTL: 5 minutes
    }],
    messages=[{"role": "user", "content": user_question}],  # varies — no marker here
)
```

For a prefix reused across bursty traffic with gaps longer than five minutes, pass an explicit 1-hour TTL instead:

```python
"cache_control": {"type": "ephemeral", "ttl": "1h"}
```

### Confirming a cache hit — don't assume, check the field

The response `usage` object is the ground truth. `input_tokens` reports **only the uncached remainder** — total prompt size is the sum of all three fields:

```python
usage = response.usage
print("cache write:", usage.cache_creation_input_tokens)  # paid ~1.25x
print("cache read: ", usage.cache_read_input_tokens)      # paid ~0.1x
print("uncached:   ", usage.input_tokens)                 # paid full price
```

The first call against a new prefix shows `cache_creation_input_tokens > 0` and `cache_read_input_tokens == 0` — that request paid the write premium. Every subsequent call with the *same* prefix, inside the TTL, should show `cache_read_input_tokens > 0` and `cache_creation_input_tokens == 0`. If `cache_read_input_tokens` stays zero across repeated, apparently-identical requests, something in the prefix is silently different — `datetime.now()` baked into the system prompt, a `uuid4()` near the front, `json.dumps(d)` without `sort_keys=True`, or a tool list assembled from an unordered `set`. Diff the rendered prompt bytes between two calls to find it before concluding caching "doesn't help here."

**Architectural rule that matters more than marker placement:** don't change the tool list or model mid-session — both render at the front of the request and invalidate the whole prefix on any change. Don't interpolate a timestamp or user ID into the system prompt; push anything that varies per request to the end of `messages`, after the last `cache_control` marker.

---

## The Batches API: Half Price When Latency Doesn't Matter

Not every call needs a response in two seconds. Nightly report summarization, bulk document classification, backfilling embeddings metadata, re-scoring an eval set — none are latency-sensitive, and all are exactly the workload the **Message Batches API** is priced for: **50% off standard token pricing**, in exchange for asynchronous processing (most batches finish within an hour; the hard ceiling is 24 hours; results stay available for 29 days).

Grounded in the bundled `claude-api` skill's `python/claude-api/batches.md`. Submit a list of requests, each with a `custom_id` you choose to match results back later:

```python
import anthropic
import time
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

client = anthropic.Anthropic()

items_to_classify = [
    "The product quality is excellent!",
    "Terrible customer service, never again.",
    "It's okay, nothing special.",
]

batch = client.messages.batches.create(
    requests=[
        Request(
            custom_id=f"classify-{i}",
            params=MessageCreateParamsNonStreaming(
                model="claude-haiku-4-5",   # cheap model — a simple classification task
                max_tokens=50,
                messages=[{
                    "role": "user",
                    "content": f"Classify as positive/negative/neutral (one word): {text}",
                }],
            ),
        )
        for i, text in enumerate(items_to_classify)
    ]
)
print(f"Created batch: {batch.id}")

# Poll until done — most batches finish well under an hour
while True:
    batch = client.messages.batches.retrieve(batch.id)
    if batch.processing_status == "ended":
        break
    time.sleep(10)

# Stream results, matched back to custom_id
results = {}
for result in client.messages.batches.results(batch.id):
    match result.result.type:
        case "succeeded":
            msg = result.result.message
            results[result.custom_id] = next(
                (b.text for b in msg.content if b.type == "text"), ""
            )
        case "errored":
            print(f"[{result.custom_id}] error — fix and retry, or safe to retry if server error")
        case "expired" | "canceled":
            print(f"[{result.custom_id}] did not complete — resubmit if still needed")

for custom_id, label in sorted(results.items()):
    print(f"{custom_id}: {label}")
```

Every Messages API feature — including prompt caching — works inside a batch. A batch of 10,000 classification calls that all share one large system prompt gets **both** the 50% batch discount and the cache-read discount on the shared prefix, applied independently:

```python
shared_system = [
    {"type": "text", "text": "You are a support-ticket classifier."},
    {"type": "text", "text": large_policy_document, "cache_control": {"type": "ephemeral"}},
]

batch = client.messages.batches.create(
    requests=[
        Request(
            custom_id=f"ticket-{i}",
            params=MessageCreateParamsNonStreaming(
                model="claude-haiku-4-5",
                max_tokens=50,
                system=shared_system,
                messages=[{"role": "user", "content": ticket_text}],
            ),
        )
        for i, ticket_text in enumerate(tickets)
    ]
)
```

**The cost tradeoff to weigh honestly:** batching trades latency for a guaranteed 50% discount plus operational complexity — submit, poll (or wait for a webhook), reconcile by `custom_id`, and handle `errored`/`expired` items that a synchronous call never has to. It's a clear win for bulk, non-interactive work, and the *wrong* tool the moment a human is waiting on the response. Confirm the workload is actually bulk and actually not latency-sensitive — with real traffic data — before reaching for it.

---

## Model Routing: Let the Cheap Model Triage

The other lever, orthogonal to caching and batching, is **not sending every request to your most expensive model.** A large share of real traffic — sentiment classification, intent detection, "is this ticket urgent," simple extraction — is well within a cheap model's competence. Route those to `claude-haiku-4-5` and reserve `claude-opus-4-8` for requests that actually need it.

A simple, honest pattern: run the cheap model first, have it flag its own uncertainty, and escalate only when it does.

```python
def triage_with_haiku(ticket_text: str) -> tuple[str, bool]:
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": f"""Classify this support ticket as billing/technical/other.
If you are not confident, say so explicitly.

Ticket: {ticket_text}

Respond as: <label>|<confident:yes/no>""",
        }],
    )
    text = next((b.text for b in response.content if b.type == "text"), "other|no")
    label, _, confident_flag = text.partition("|")
    return label.strip(), confident_flag.strip().lower() == "yes"


def handle_ticket(ticket_text: str) -> str:
    label, confident = triage_with_haiku(ticket_text)
    if confident:
        return label   # cheap model handled it — done

    # Escalate only the uncertain fraction to the stronger model
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=500,
        messages=[{"role": "user", "content": f"Carefully classify and explain this ticket: {ticket_text}"}],
    )
    return next((b.text for b in response.content if b.type == "text"), "other")
```

If 80% of tickets are confidently triaged by Haiku at $1/$5 per MTok, and only 20% escalate to Opus at $5/$25, the blended cost is a fraction of routing everything through Opus — with no quality loss on the easy majority, because the escalation path exists exactly for the cases where the cheap model says "I'm not sure." The failure mode to guard against is a cheap model that's *overconfident*: measure the triage's accuracy against a labeled sample before trusting the split, and tune the confidence threshold from that measurement, not from vibes.

---

## Measure Before You Optimize

Every technique above has a cost of its own — a cache write premium, batch operational overhead, an extra triage call before the "real" one. Applied blindly, any of them can make a system *more* expensive:

- Caching a prefix that changes every request pays the write premium with zero reads — worse than not caching.
- Batching latency-sensitive traffic breaks the product; a 50% saving doesn't matter if a user is staring at a spinner.
- Routing to a cheap model without measuring its accuracy on your real traffic distribution can silently degrade quality while looking like a cost win on the invoice.

Instrument first: log `cache_read_input_tokens` / `cache_creation_input_tokens` / `input_tokens` per request, track cost per request type, and know your actual latency requirements before reaching for any of these levers. Optimize the workload that's actually expensive — not the one you assume is.

---

## Practical Checklist

| Practice | Why it matters |
|----------|----------------|
| Put the stable prefix (system prompt, tools, RAG context) first, volatile content last | Prefix match — anything after a byte change is uncached |
| Add `cache_control` only where the prefix meets the model's minimum token count | Below the minimum, it silently writes and never reads |
| Verify with `cache_read_input_tokens`, not assumption | A silent invalidator produces zero reads with no error |
| Reach for the Batches API only for non-interactive bulk work | 50% discount, but async — wrong tool under a human waiting |
| Combine batching with caching on shared prefixes | Discounts stack; both apply independently |
| Route easy/high-volume requests to a cheap model, escalate on low confidence | Blended cost drops without lowering quality on hard cases |
| Measure cost and latency per request type before optimizing | "Optimizing" the wrong workload can make things worse |

---

## Final Thoughts

Cost control for LLM applications isn't a separate discipline from correctness — it's the same engineering discipline applied to a new, expensive kind of external call. The prefix is the bill; caching turns a repeatedly-read prefix into a cheap read; batching turns non-urgent bulk work into a 50%-off job; routing turns "always call the strongest model" into "call the model the task actually needs." None of it replaces measurement — instrument the usage fields, know your latency requirements, and let real numbers, not assumptions, decide which lever to pull.
