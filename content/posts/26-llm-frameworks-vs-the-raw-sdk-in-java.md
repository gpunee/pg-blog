---
title: "LLM Frameworks vs. the Raw SDK in Java"
date: 2026-07-04
description: "Building the same small tool-using agent on the raw Anthropic Java SDK, LangChain4j, and Spring AI, to see honestly where each framework earns its weight."
tags:
  - Java
  - AI
  - LLM
  - LangChain4j
  - Spring AI
  - Anthropic
categories:
  - Java
draft: false
---

## Introduction

Every LLM ecosystem now has at least one framework promising to make agents easier to build, and every framework post either oversells the abstraction or dismisses it outright. Neither is useful. The only honest way to evaluate a framework is to build the same thing twice — once on the vendor's raw SDK, once on the framework — and compare what each version actually cost you and actually gave you back.

This post builds the small tool-using agent from [Building Agentic Workflows in Java]({{< ref "14-building-agentic-workflows-in-java.md" >}}) three ways: on the raw Anthropic Java SDK, on [LangChain4j](https://docs.langchain4j.dev/), and on [Spring AI](https://docs.spring.io/spring-ai/reference/). We'll also touch the RAG pipeline from [RAG From Scratch in Java]({{< ref "20-rag-from-scratch-in-java.md" >}}) — retrieval is exactly the kind of component a framework's tool abstraction is built to wrap. The goal isn't to crown a winner; it's to give you a way to make this decision for your own project instead of inheriting someone else's blog-post conclusion.

---

## The Agent We're Building Three Times

To keep the comparison fair, every version gets the identical agent: one system prompt, two tools, one user turn, running until the model stops asking for tools.

- **`getWeather(String location)`** — the same illustrative weather lookup from the agentic-workflows post, so the tool-calling shape lines up exactly with what you've already seen built by hand.
- **`calculate(String operation, double a, double b)`** — a second tool with a constrained, whitelisted `operation` argument (`add` / `subtract` / `multiply` / `divide`) rather than a free-text expression. This is deliberate: it's the "never build a shell/SQL string from model input" lesson from the agentic-workflows post, made concrete as a schema choice instead of a runtime check.

Every framework below turns the *same* two methods into tool schemas — they differ in how a Java method becomes something the model can call, not in what the agent does.

---

## Path A: The Raw Anthropic Java SDK

This is the manual loop from [Building Agentic Workflows in Java]({{< ref "14-building-agentic-workflows-in-java.md" >}}), condensed to this agent's two tools. Every tool call passes through code you wrote and can inspect:

```java
import com.anthropic.client.AnthropicClient;
import com.anthropic.client.okhttp.AnthropicOkHttpClient;
import com.anthropic.core.JsonValue;
import com.anthropic.models.messages.*;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

AnthropicClient client = AnthropicOkHttpClient.fromEnv(); // reads ANTHROPIC_API_KEY

Tool getWeatherTool = Tool.builder().name("get_weather").description("Get current weather for a location")
    .inputSchema(Tool.InputSchema.builder()
        .properties(Tool.InputSchema.Properties.builder()
            .putAdditionalProperty("location", JsonValue.from(Map.of("type", "string"))).build())
        .required(List.of("location")).build())
    .build();

Tool calculateTool = Tool.builder().name("calculate").description("Perform basic arithmetic on two numbers")
    .inputSchema(Tool.InputSchema.builder()
        .properties(Tool.InputSchema.Properties.builder()
            .putAdditionalProperty("operation", JsonValue.from(
                Map.of("type", "string", "enum", List.of("add", "subtract", "multiply", "divide"))))
            .putAdditionalProperty("a", JsonValue.from(Map.of("type", "number")))
            .putAdditionalProperty("b", JsonValue.from(Map.of("type", "number"))).build())
        .required(List.of("operation", "a", "b")).build())
    .build();

List<MessageParam> messages = new ArrayList<>();
messages.add(MessageParam.builder().role(MessageParam.Role.USER)
    .content("What's the weather in Austin, and what's 12 divided by 4?").build());

int iterations = 0;
final int maxIterations = 10;
Message response;
while (true) {
    if (++iterations > maxIterations) throw new IllegalStateException("Agent exceeded iteration cap — stopping");

    response = client.messages().create(MessageCreateParams.builder()
        .model(Model.CLAUDE_OPUS_4_8).maxTokens(16000L)
        .thinking(ThinkingConfigAdaptive.builder().build())
        .addTool(getWeatherTool).addTool(calculateTool)
        .messages(messages)
        .build());

    if (response.stopReason().isPresent() && response.stopReason().get().toString().equals("end_turn")) break;

    messages.add(MessageParam.builder().role(MessageParam.Role.ASSISTANT)
        .contentOfBlockParams(toBlockParams(response.content())).build());

    List<ContentBlockParam> toolResults = new ArrayList<>();
    for (ContentBlock block : response.content()) {
        block.toolUse().ifPresent(toolUse -> {
            // Validate/whitelist BEFORE executing — toolUse.input() is model-provided, untrusted data
            String result = executeValidatedTool(toolUse.name(), toolUse.input());
            toolResults.add(ContentBlockParam.ofToolResult(ToolResultBlockParam.builder()
                .toolUseId(toolUse.id()).content(result).build()));
        });
    }
    messages.add(MessageParam.builder().role(MessageParam.Role.USER)
        .contentOfBlockParams(toolResults).build());
}
```

All of it visible: the hand-written `Tool` schemas, the loop, the iteration cap, and one explicit choke point (`executeValidatedTool`) where every tool call is checked before it runs.

---

## Path B: LangChain4j — `@Tool` Methods + `AiServices`

LangChain4j replaces hand-written `Tool` schemas with reflection over annotated methods, and replaces the `while` loop with a proxy interface. Add the core library and the Anthropic model module:

```xml
<dependency>
    <groupId>dev.langchain4j</groupId>
    <artifactId>langchain4j</artifactId>
    <version>1.17.1</version>
</dependency>
<dependency>
    <groupId>dev.langchain4j</groupId>
    <artifactId>langchain4j-anthropic</artifactId>
    <version>1.17.1</version>
</dependency>
```

Define both tools as plain methods, annotated with `@Tool`/`@P`:

```java
import dev.langchain4j.agent.tool.Tool;
import dev.langchain4j.agent.tool.P;

class AgentTools {
    @Tool("Get current weather for a location")
    String getWeather(@P("City and state, e.g. San Francisco, CA") String location) {
        return "Sunny, 72F in " + location;
    }

    @Tool("Perform basic arithmetic on two numbers")
    double calculate(@P("One of: add, subtract, multiply, divide") String operation,
                      @P("First operand") double a, @P("Second operand") double b) {
        if (operation.equals("divide") && b == 0) throw new IllegalArgumentException("Division by zero");
        return switch (operation) {
            case "add" -> a + b;
            case "subtract" -> a - b;
            case "multiply" -> a * b;
            case "divide" -> a / b;
            default -> throw new IllegalArgumentException("Unknown operation: " + operation);
        };
    }
}
```

Wire an `AnthropicChatModel` and a proxy interface through `AiServices` — this is where `create_agent`'s Python equivalent shows up on the Java side:

```java
import dev.langchain4j.model.anthropic.AnthropicChatModel;
import dev.langchain4j.model.chat.ChatModel;
import dev.langchain4j.service.AiServices;

ChatModel model = AnthropicChatModel.builder()
    .apiKey(System.getenv("ANTHROPIC_API_KEY"))
    .modelName("claude-opus-4-8")
    .thinkingType("adaptive")
    .maxTokens(16000)
    .build();

interface Assistant {
    String chat(String userMessage);
}

Assistant assistant = AiServices.builder(Assistant.class)
    .chatModel(model)
    .tools(new AgentTools())
    .build();

String answer = assistant.chat("What's the weather in Austin, and what's 12 divided by 4?");
System.out.println(answer);
```

`AiServices` generates the tool JSON schema from each `@Tool` method's signature and `@P` descriptions, runs the request/tool-execute/reprocess loop internally, and returns the final answer as a plain `String` — the entire loop from Path A collapses into one `.chat(...)` call, at the cost of the trade-off the agentic-workflows post named for the SDK's own tool runner: validation now lives *inside* `getWeather`/`calculate`, not at a single choke point you control. (`thinkingType("adaptive")` omits `thinkingBudgetTokens` deliberately — a token budget has no meaning for adaptive mode, the same "no `budget_tokens` on Opus 4.8" rule as the raw SDK.)

---

## Path C: Spring AI — `@Tool` Methods + `ChatClient`

Spring AI takes the same annotation-driven approach through its own `@Tool`/`@ToolParam` types and a `ChatClient` builder, with `ToolCallingAdvisor` managing the loop instead of `AiServices`:

```xml
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-starter-model-anthropic</artifactId>
</dependency>
```

The tool class is the same shape as LangChain4j's, with Spring AI's own annotations in place of `@Tool`/`@P` — `calculate`'s whitelisted-operation body is identical to the LangChain4j version above:

```java
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;

class AgentTools {
    @Tool(description = "Get current weather for a location")
    String getWeather(@ToolParam(description = "City and state, e.g. San Francisco, CA") String location) {
        return "Sunny, 72F in " + location;
    }

    @Tool(description = "Perform basic arithmetic on two numbers")
    double calculate(@ToolParam(description = "add/subtract/multiply/divide") String operation,
                      @ToolParam double a, @ToolParam double b) {
        // same whitelisted-operation body as the LangChain4j calculate() above
        return dispatchCalculate(operation, a, b);
    }
}
```

```java
import org.springframework.ai.anthropic.AnthropicChatModel;
import org.springframework.ai.anthropic.AnthropicChatOptions;
import org.springframework.ai.chat.client.ChatClient;

var chatModel = AnthropicChatModel.builder()
    .options(AnthropicChatOptions.builder()
        .model("claude-opus-4-8")
        .thinkingAdaptive()
        .maxTokens(16000)
        .apiKey(System.getenv("ANTHROPIC_API_KEY"))
        .build())
    .build();

String answer = ChatClient.create(chatModel)
    .prompt("What's the weather in Austin, and what's 12 divided by 4?")
    .tools(new AgentTools())
    .call()
    .content();
```

`ChatClient` auto-registers `ToolCallingAdvisor` whenever `.tools(...)` is present, so the loop is handled the same way `AiServices` handles it in LangChain4j. In a Spring Boot app, `AnthropicChatModel` and `ChatClient.Builder` are typically autoconfigured beans (via the starter + `spring.ai.anthropic.api-key`) rather than built by hand as shown here.

---

## Where the Framework Actually Earns Its Weight

For *this* agent — two tools, one provider, one turn — both frameworks mostly buy convenience over the SDK's own manual loop. Their case gets much stronger once your requirements grow past a single call:

| Need | Raw SDK | LangChain4j | Spring AI |
|---|---|---|---|
| Java method → tool schema | Hand-write `Tool.InputSchema` | `@Tool`/`@P` reflection | `@Tool`/`@ToolParam` reflection |
| Swap chat model/provider | Rewrite the request builder | Swap `ChatModel` behind `AiServices` | Swap the bean behind `ChatClient` |
| Spring-managed config/DI | You own the wiring | Usable, not Spring-native | First-class: properties + autoconfigured beans |
| RAG retrieval as a component | Hand-roll (RAG-from-scratch post) | Built-in `EmbeddingStore` abstractions | Built-in `VectorStore`/`Advisor` abstractions |
| Typed step hand-off | `StructuredMessageCreateParams<T>` | Structured Outputs on return type | `.entity(Class)` on `ChatClient` |

The pattern across every row: the framework's value shows up when there's a *policy or integration surface* (Spring wiring, a swappable model, a retrieval abstraction) that should apply uniformly across a larger application, not when there's one call site. A single small agent has, definitionally, one call site.

---

## Where It's Ceremony

For the agent this post builds, either framework costs an extra module dependency, an abstraction layer over the documented Anthropic request/response shape, and a release cadence to track alongside the SDK's — both frameworks' tool/model APIs have evolved across releases, exactly the risk this post's verification bar exists to catch (every snippet above was checked against current docs and source, not memory). That's not a reason to avoid frameworks; it's a reason to install one for a *reason*.

**Rule of thumb:** stay on the raw SDK while you have one provider, one call site, and no Spring/DI application around the agent. Reach for LangChain4j when you want annotation-driven tools and built-in RAG abstractions without full Spring. Reach for Spring AI when the agent already lives inside a Spring Boot application and autoconfiguration, `ChatClient`, and `@ToolParam` fit the codebase's existing idioms.

---

## The Trust Boundary Doesn't Move

Whichever path you pick, the security posture from [Building Agentic Workflows in Java]({{< ref "14-building-agentic-workflows-in-java.md" >}}) is unchanged: `toolUse.input()` (raw SDK) and the arguments a `@Tool`-annotated method receives (LangChain4j, Spring AI) are all **the same untrusted, model-provided data**. A framework generating your JSON schema does not validate the *values* the model sends back — `calculate`'s whitelisted `operation` string still needs a `default ->` branch that rejects anything unexpected, regardless of which of the three call shapes above invoked it. Never string-interpolate a tool argument into a shell command or SQL query, framework or no framework.

---

## Practical Checklist

| Practice | Why it matters |
|----------|----------------|
| Build the raw-SDK version first, even briefly | Gives you a control to compare frameworks against, and a fallback if one misbehaves |
| Pick a framework for Spring wiring, provider portability, or built-in RAG — not for one call site | The convenience win is in cross-cutting integration, not a single loop |
| Keep `@Tool` methods' validation inside the method | `AiServices`/`ChatClient` move the choke point *into* the tool — validation has to move with it |
| Verify framework APIs (annotation packages, builder methods) against current docs before shipping | Framework surfaces move faster than SDK surfaces; a stale snippet is worse than none |
| Never build a shell/SQL string from a tool argument | Prefer a whitelisted `switch` with a rejecting `default`, as `calculate` does here |
| Match dependency versions to your build (langchain4j-bom / Spring AI BOM) | Both frameworks version their modules together — mixing versions is a common source of runtime errors |

---

## Final Thoughts

The raw SDK and a framework solve different problems: the SDK gives you the documented shape of one provider's API; a framework gives you an integration surface — Spring beans, a swappable chat model, a RAG abstraction — meant to stay stable as the application grows around it. For a single small agent, that stability is mostly unrealized — you pay the abstraction's overhead without yet needing what it buys. Build the raw version first so you know what the framework does on your behalf, and add LangChain4j or Spring AI only once a specific requirement asks for it by name.
