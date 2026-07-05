---
title: "The Model Context Protocol in Java"
date: 2026-07-04
description: "What MCP is, why it exists, and how to build a minimal tool server and a client that consumes it in Java — with an honest look at when the protocol earns its weight."
tags:
  - Java
  - AI
  - LLM
  - MCP
  - Anthropic
categories:
  - Java
draft: false
---

## Introduction

Every agent needs tools, and every tool needs a way to reach the model. [Building Agentic Workflows in Java]({{< ref "14-building-agentic-workflows-in-java.md" >}}) built that connection by hand — a hand-written `Tool` schema, a loop that dispatches on `toolUse.name()`. [LLM Frameworks vs. the Raw SDK in Java]({{< ref "26-llm-frameworks-vs-the-raw-sdk-in-java.md" >}}) showed LangChain4j and Spring AI turning an annotated Java method into that same schema via reflection. Both are still *bespoke*: the tool lives inside one process, wired to one agent, in one language.

The [Model Context Protocol](https://modelcontextprotocol.io) (MCP) solves a different problem: it standardizes the *wire format* between an AI application and a tool server, so the server doesn't have to be rewritten per agent, per framework, or per language. This post covers what that buys you, builds a minimal MCP server and a client that consumes it — both on the official Java SDK — and gives an honest answer to when reaching for a protocol is worth it over a direct tool call.

---

## The Problem MCP Solves

Without a shared protocol, every pairing of *agent framework* and *tool* needs its own glue code: a LangChain4j tool wrapper, a Spring AI `@Tool` method, a hand-rolled schema for the raw SDK — three integrations for one capability, repeated for every tool and every framework you add. That's an M×N integration problem.

MCP flattens it to M+N. A **server** exposes tools, resources, and prompts once, over a standard JSON-RPC protocol. Any **host** application — Claude Code, Claude Desktop, VS Code, or your own agent — creates an MCP **client** that speaks that same protocol, regardless of which framework built the host. Write the server once; every MCP-aware host can use it without new integration code.

The protocol itself is intentionally boring: [JSON-RPC 2.0](https://www.jsonrpc.org/) messages for lifecycle negotiation, tool discovery, and tool execution. Discovery (`tools/list`) and execution (`tools/call`) are the two calls that matter for this post:

```json
// tools/list response (abbreviated)
{ "jsonrpc": "2.0", "id": 2, "result": { "tools": [
  { "name": "get_account_balance", "description": "Look up the balance for an account by ID",
    "inputSchema": { "type": "object",
      "properties": { "accountId": { "type": "string" } }, "required": ["accountId"] } }
]}}
```

Two transports cover most cases: **stdio** (a local subprocess, one client per server — what this post uses) and **Streamable HTTP** (a remote server, many clients, standard bearer-token auth). Source: [MCP architecture overview](https://modelcontextprotocol.io/docs/learn/architecture).

---

## Building a Minimal MCP Server

The official Java SDK (`io.modelcontextprotocol.sdk`, [Tier 2](https://modelcontextprotocol.io/community/sdk-tiers)) needs no external framework — its core `mcp` module ships stdio and HTTP transports directly ([Java MCP Server docs](https://java.sdk.modelcontextprotocol.io/latest/server/)):

```xml
<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>io.modelcontextprotocol.sdk</groupId>
      <artifactId>mcp-bom</artifactId>
      <version>2.0.0</version>
      <type>pom</type>
      <scope>import</scope>
    </dependency>
  </dependencies>
</dependencyManagement>
<dependencies>
  <dependency>
    <groupId>io.modelcontextprotocol.sdk</groupId>
    <artifactId>mcp</artifactId>
  </dependency>
</dependencies>
```

The tool is a read-only account-balance lookup — deliberately simple, and deliberately keyed by ID rather than a free-text query, for reasons the next section makes concrete:

```java
import io.modelcontextprotocol.server.McpServer;
import io.modelcontextprotocol.server.McpSyncServer;
import io.modelcontextprotocol.server.McpServerFeatures.SyncToolSpecification;
import io.modelcontextprotocol.server.transport.StdioServerTransportProvider;
import io.modelcontextprotocol.json.McpJsonDefaults;
import io.modelcontextprotocol.spec.McpSchema.*;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

// A fixed, in-memory dataset — stands in for a real accounts service
private static final Map<String, Double> ACCOUNTS = Map.of(
    "ACC-100001", 542.10, "ACC-100002", 12.50);
private static final Pattern ACCOUNT_ID = Pattern.compile("^ACC-\\d{6}$");

Map<String, Object> inputSchema = Map.of(
    "type", "object",
    "properties", Map.of("accountId", Map.of("type", "string",
        "description", "Account ID, e.g. ACC-100001")),
    "required", List.of("accountId"));

SyncToolSpecification balanceTool = SyncToolSpecification.builder()
    .tool(Tool.builder("get_account_balance", inputSchema)
        .description("Look up the balance for an account by ID")
        .build())
    .callHandler((exchange, request) -> {
        Object raw = request.arguments().get("accountId");
        // Validate/whitelist BEFORE using — request.arguments() is model-provided, untrusted data
        if (!(raw instanceof String accountId) || !ACCOUNT_ID.matcher(accountId).matches()) {
            return CallToolResult.builder()
                .content(List.of(TextContent.builder("Invalid account ID format").build()))
                .isError(true).build();
        }
        Double balance = ACCOUNTS.get(accountId);
        String text = balance != null ? "Balance for " + accountId + ": $" + balance
                                       : "No account found for " + accountId;
        return CallToolResult.builder().content(List.of(TextContent.builder(text).build())).build();
    })
    .build();

StdioServerTransportProvider transportProvider =
    new StdioServerTransportProvider(McpJsonDefaults.getMapper());

McpSyncServer server = McpServer.sync(transportProvider)
    .serverInfo("accounts-server", "1.0.0")
    .capabilities(ServerCapabilities.builder().tools(true).build())
    .build();

server.addTool(balanceTool);
```

A read-only **resource** — MCP's second primitive, for data the model can load into context without an action attached — is a few lines more:

```java
server.addResource(new McpServerFeatures.SyncResourceSpecification(
    Resource.builder("docs://refund-policy", "Refund Policy")
        .description("Current refund policy text").mimeType("text/plain").build(),
    (exchange, request) -> ReadResourceResult.builder(List.of(TextResourceContents.builder(
        "docs://refund-policy", "Refunds are issued within 5 business days.").build())).build()));
```

Source for the tool/resource specification shapes: [Java MCP Server docs](https://java.sdk.modelcontextprotocol.io/latest/server/). `StdioServerTransportProvider` communicates over stdin/stdout — never `System.out.println` in a stdio server; it corrupts the JSON-RPC stream (the same [logging warning](https://modelcontextprotocol.io/docs/develop/build-server) every language's quickstart repeats).

---

## The Trust Boundary Doesn't Move

`request.arguments()` in a tool's call handler is **the same untrusted, model-provided data** as `toolUse.input()` in the raw SDK loop (post 14) or the arguments a `@Tool`-annotated method receives (post 26) — MCP standardizes the wire format, not the trust model. The SDK does validate the *shape* of arguments against `inputSchema` before your handler ever runs (a JSON Schema 2020-12 check, on by default, per the [migration notes](https://github.com/modelcontextprotocol/java-sdk/blob/main/MIGRATION-2.0.md)) — but shape validation only confirms `accountId` is a string, not that it's a *safe* string. The regex check above still has to happen inside the handler.

Never skip that second check by trusting the schema alone:

```java
// UNSAFE — never do this: string-interpolating a tool argument into a query
String sql = "SELECT balance FROM accounts WHERE id = '" + accountId + "'"; // SQL injection

// SAFE — validate/whitelist first (as balanceTool does above), then use a fixed lookup
// or a parameterized query — never string-built from model input
```

The lesson from post 14's `executeValidatedTool` carries over unchanged: whitelist the shape you expect, reject anything else, and never let a tool argument reach a shell command, file path, or SQL string by concatenation.

---

## Building a Client That Consumes the Server

A client connects over the same stdio transport, discovers the tool, and calls it — no knowledge of how the server was implemented:

```java
import io.modelcontextprotocol.client.McpClient;
import io.modelcontextprotocol.client.McpSyncClient;
import io.modelcontextprotocol.client.transport.ServerParameters;
import io.modelcontextprotocol.client.transport.StdioClientTransport;
import io.modelcontextprotocol.spec.McpSchema.*;

ServerParameters params = ServerParameters.builder("java")
    .args("-jar", "/path/to/accounts-mcp-server.jar")
    .build();
var transport = new StdioClientTransport(params, McpJsonDefaults.getMapper());

McpSyncClient client = McpClient.sync(transport).build();
client.initialize();

ListToolsResult tools = client.listTools();
System.out.println("Available: " + tools.tools().stream().map(Tool::name).toList());

CallToolResult result = client.callTool(
    CallToolRequest.builder("get_account_balance")
        .arguments(Map.of("accountId", "ACC-100001"))
        .build());

client.closeGracefully();
```

Source for `McpClient`/`ServerParameters`/`StdioClientTransport`: [Java MCP Client docs](https://java.sdk.modelcontextprotocol.io/latest/client/). This is the same shape modelcontextprotocol.io's own [Build an MCP Server](https://modelcontextprotocol.io/docs/develop/build-server) tutorial uses to test a Spring AI weather server from a plain Java client — the client doesn't care which SDK or framework built the server on the other end of the transport.

---

## Wiring MCP Into the Agent Loop from Post 14

The agent loop itself doesn't change — only where the tool list and tool execution come from. Instead of hand-written `Tool` objects and a local `executeValidatedTool` method, list tools from the MCP client and route `tool_use` blocks through `client.callTool(...)`:

```java
import com.anthropic.core.JsonValue;

// Convert an MCP Tool's Map-shaped inputSchema into the Anthropic SDK's Tool.InputSchema
// (same InputSchema.builder() shape post 26 hand-writes for getWeatherTool/calculateTool)
@SuppressWarnings("unchecked")
private static com.anthropic.models.messages.Tool toAnthropicTool(Tool mcpTool) {
    Map<String, Object> props = (Map<String, Object>) mcpTool.inputSchema().getOrDefault("properties", Map.of());
    List<String> required = (List<String>) mcpTool.inputSchema().getOrDefault("required", List.of());
    var propsBuilder = com.anthropic.models.messages.Tool.InputSchema.Properties.builder();
    props.forEach((name, schema) -> propsBuilder.putAdditionalProperty(name, JsonValue.from(schema)));
    return com.anthropic.models.messages.Tool.builder()
        .name(mcpTool.name()).description(mcpTool.description())
        .inputSchema(com.anthropic.models.messages.Tool.InputSchema.builder()
            .properties(propsBuilder.build()).required(required).build())
        .build();
}

ListToolsResult mcpTools = client.listTools();
List<com.anthropic.models.messages.Tool> anthropicTools =
    mcpTools.tools().stream().map(ToolBridge::toAnthropicTool).toList();

// Inside the loop from post 14, in place of executeValidatedTool(toolUse.name(), toolUse.input()):
CallToolResult mcpResult = client.callTool(
    CallToolRequest.builder(toolUse.name()).arguments(toolUse.input()).build());
String textResult = mcpResult.content().stream()
    .filter(TextContent.class::isInstance).map(c -> ((TextContent) c).text())
    .findFirst().orElse("");
```

Everything else from post 14 — the `MAX_ITERATIONS` cap, `claude-opus-4-8` with `ThinkingConfigAdaptive`, the message bookkeeping — is unchanged. Only the tool's *implementation* moved to a separate, reusable process.

---

## MCP vs. the Framework Tool Abstraction (Post 26)

LangChain4j's `@Tool`/`AiServices` and Spring AI's `@Tool`/`ChatClient` (post 26) wrap **a method living in your own JVM process** — convenient, but the tool only exists inside that one application. MCP wraps **a separate process or service** behind a standard protocol, so the same accounts server above can be launched by Claude Desktop, called from Claude Code, and consumed by this post's plain-Java client — three unrelated hosts, zero rewritten integration code (the ["broad ecosystem support"](https://modelcontextprotocol.io/docs/getting-started/intro) modelcontextprotocol.io advertises).

The two aren't mutually exclusive: Spring AI ships its own MCP **client** boot starter, so a Spring Boot agent can consume this exact server as auto-configured tools instead of hand-rolling the `McpClient` above:

```xml
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-starter-mcp-client</artifactId>
</dependency>
```

with `spring.ai.mcp.client.stdio.servers-configuration` pointing at a server-launch config — confirmed in modelcontextprotocol.io's own [Build an MCP Server](https://modelcontextprotocol.io/docs/develop/build-server) Java walkthrough. Framework tool abstractions and MCP solve different layers of the same problem: one wires a method into a prompt; the other lets that method's *server* outlive any one framework.

---

## When MCP Earns Its Weight — and When It's Overkill

Reach for MCP when the tool or data source needs to be **shared across independently-built AI applications** — your accounts lookup used by Claude Desktop for support staff *and* Claude Code for engineers *and* a custom internal agent — or when you're **consuming someone else's server** (Sentry, GitHub, a filesystem) without writing integration code per host. It's the right call when the tool is a product in its own right, not a private implementation detail of one agent.

It's ceremony when the tool has exactly one caller in one codebase: a separate process, a stdio or HTTP transport, and a protocol handshake are pure overhead next to a `@Tool`-annotated method (post 26) or a hand-written `Tool` schema (post 14) that never leaves the JVM. Build the direct version first; promote it to an MCP server only once a second, independent host actually needs to call it.

---

## Practical Checklist

| Practice | Why it matters |
|----------|----------------|
| Start with a direct tool call (post 14/26); promote to MCP only when a second host needs it | MCP's cost — a process, a transport, a protocol — buys nothing for a single caller |
| Validate/whitelist `request.arguments()` inside the handler, even with schema validation on | Schema validation checks shape, not safety — `get_account_balance` still checks the regex |
| Never string-interpolate a tool argument into SQL, a shell command, or a file path | The same rule as posts 14/26 — MCP doesn't change the trust boundary |
| Never write to stdout in a stdio-transport server | Corrupts the JSON-RPC stream; log to stderr or a file instead |
| Prefer a fixed lookup or parameterized query over building a query string from model input | The account-balance tool above never builds a string query from `accountId` |
| Cite a live source for every MCP class/method before shipping | The SDK is Tier 2 and evolving; a stale snippet is worse than none |

---

## Final Thoughts

MCP doesn't replace the agentic loop from post 14 or the framework tool abstractions from post 26 — it standardizes what sits behind either one: a tool server that any compliant client can discover and call, without per-host glue code. That standardization is worth real engineering cost when a tool needs to serve more than one application; for a tool with one caller, the direct approaches this series already covered remain the simpler, and correct, default.
