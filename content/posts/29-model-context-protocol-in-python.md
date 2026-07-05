---
title: "The Model Context Protocol in Python"
date: 2026-07-04
description: "What MCP is, why it exists, and how to build a minimal tool server and a client that consumes it in Python — with an honest look at when the protocol earns its weight."
tags:
  - Python
  - AI
  - LLM
  - MCP
  - Anthropic
categories:
  - Python
draft: false
---

## Introduction

Every agent needs tools, and every tool needs a way to reach the model. [Building Agentic Workflows in Python]({{< ref "15-building-agentic-workflows-in-python.md" >}}) built that connection by hand — a hand-written JSON schema, a loop that dispatches on `block.name`. [LLM Frameworks vs. the Raw SDK in Python]({{< ref "27-llm-frameworks-vs-the-raw-sdk-in-python.md" >}}) showed LangChain's `@tool` turning a plain function into that same schema via `bind_tools`. Both are still *bespoke*: the tool lives inside one process, wired to one agent, in one language.

The [Model Context Protocol](https://modelcontextprotocol.io) (MCP) solves a different problem: it standardizes the *wire format* between an AI application and a tool server, so the server doesn't have to be rewritten per agent, per framework, or per language. This post covers what that buys you, builds a minimal MCP server and a client that consumes it — both on the official Python SDK — and gives an honest answer to when reaching for a protocol is worth it over a direct tool call.

---

## The Problem MCP Solves

Without a shared protocol, every pairing of *agent framework* and *tool* needs its own glue code: a LangChain `@tool` wrapper, a hand-rolled schema for the raw SDK, a different wrapper again for whatever framework a teammate picks next — an integration per framework, per tool. That's an M×N problem.

MCP flattens it to M+N. A **server** exposes tools, resources, and prompts once, over a standard JSON-RPC protocol. Any **host** application — Claude Code, Claude Desktop, VS Code, or your own agent — creates an MCP **client** that speaks that same protocol, regardless of which framework built the host. Write the server once; every MCP-aware host can use it without new integration code.

The protocol itself is intentionally boring: [JSON-RPC 2.0](https://www.jsonrpc.org/) messages for lifecycle negotiation, tool discovery, and tool execution. Discovery (`tools/list`) and execution (`tools/call`) are the two calls that matter for this post:

```json
// tools/list response (abbreviated)
{
  "jsonrpc": "2.0", "id": 2,
  "result": { "tools": [
    { "name": "get_account_balance",
      "description": "Look up the balance for an account by ID",
      "inputSchema": { "type": "object",
        "properties": { "account_id": { "type": "string" } },
        "required": ["account_id"] } }
  ]}
}
```

Two transports cover most cases: **stdio** (a local subprocess, one client per server — what this post uses) and **Streamable HTTP** (a remote server, many clients, standard bearer-token auth). Source: [MCP architecture overview](https://modelcontextprotocol.io/docs/learn/architecture).

---

## Building a Minimal MCP Server

The official Python SDK's stable line is **v1.x** — v2 is alpha and explicitly not recommended for production ([python-sdk README](https://github.com/modelcontextprotocol/python-sdk/blob/v1.x/README.md)), so this post pins to it:

```bash
uv add "mcp[cli]"
```

`FastMCP` turns a type-hinted, docstring-described function into a tool — no hand-written JSON Schema, matching the "two type-hinted functions" pitch of the SDK's own [quickstart](https://github.com/modelcontextprotocol/python-sdk/blob/v1.x/README.md). The tool is a read-only account-balance lookup, deliberately keyed by ID rather than a free-text query, for reasons the next section makes concrete:

```python
import re
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("accounts-server")

# A fixed, in-memory dataset — stands in for a real accounts service
ACCOUNTS = {"ACC-100001": 542.10, "ACC-100002": 12.50}
ACCOUNT_ID = re.compile(r"^ACC-\d{6}$")

@mcp.tool()
def get_account_balance(account_id: str) -> str:
    """Look up the balance for an account by ID.

    Args:
        account_id: Account ID, e.g. ACC-100001.
    """
    # Validate/whitelist BEFORE using — account_id is model-provided, untrusted data
    if not ACCOUNT_ID.match(account_id):
        raise ValueError("Invalid account ID format")
    balance = ACCOUNTS.get(account_id)
    return f"Balance for {account_id}: ${balance}" if balance is not None \
        else f"No account found for {account_id}"
```

A read-only **resource** — MCP's second primitive, for data the model can load into context without an action attached — is one more decorator:

```python
@mcp.resource("docs://refund-policy")
def refund_policy() -> str:
    """Current refund policy text."""
    return "Refunds are issued within 5 business days."


if __name__ == "__main__":
    mcp.run(transport="stdio")  # never print() here — it corrupts the JSON-RPC stream on stdio
```

Source for `FastMCP`, `@mcp.tool()`, and `@mcp.resource()`: [python-sdk v1.x README](https://github.com/modelcontextprotocol/python-sdk/blob/v1.x/README.md) and the official [Build an MCP Server](https://modelcontextprotocol.io/docs/develop/build-server) tutorial. The stdio logging warning is language-agnostic: `print()` writes to stdout by default, which is the same stream the protocol uses — log to `sys.stderr` or a logging library instead.

---

## The Trust Boundary Doesn't Move

The `account_id` argument a tool function receives is **the same untrusted, model-provided data** as `block.input` in the raw SDK loop (post 15) or the arguments a `@tool`-decorated function receives from `bind_tools`/`create_agent` (post 27) — MCP standardizes the wire format, not the trust model. FastMCP does validate the *shape* of arguments against the schema it derives from your type hints before your function ever runs — but shape validation only confirms `account_id` is a string, not that it's a *safe* string. The regex check above still has to happen inside the function body.

Never skip that second check by trusting the type hint alone:

```python
# UNSAFE — never do this: string-interpolating a tool argument into a query
sql = f"SELECT balance FROM accounts WHERE id = '{account_id}'"  # SQL injection

# SAFE — validate/whitelist first (as get_account_balance does above), then use a fixed
# lookup or a parameterized query — never a query string built from model input
```

The lesson from post 15's `execute_validated_tool` carries over unchanged: whitelist the shape you expect, reject anything else, and never let a tool argument reach a shell command, file path, or SQL string by concatenation.

---

## Building a Client That Consumes the Server

A client connects over the same stdio transport, discovers the tool, and calls it — no knowledge of how the server was implemented:

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(command="python", args=["accounts_server.py"])

async def main():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Available:", [t.name for t in tools.tools])

            result = await session.call_tool(
                "get_account_balance", arguments={"account_id": "ACC-100001"})
            print(result.content[0].text)

asyncio.run(main())
```

Source for `ClientSession`, `StdioServerParameters`, `stdio_client`, and `session.call_tool`: [python-sdk v1.x `docs/client.md`](https://github.com/modelcontextprotocol/python-sdk/blob/v1.x/docs/client.md). This is the same pattern modelcontextprotocol.io's own [Build an MCP Client](https://modelcontextprotocol.io/docs/develop/build-client) tutorial uses — the client doesn't care which SDK or language built the server on the other end of the transport.

---

## Wiring MCP Into the Agent Loop from Post 15

The agent loop itself doesn't change — only where the tool list and tool execution come from. Instead of a hand-written `TOOLS` list and a local `execute_validated_tool` function, list tools from the MCP session and route `tool_use` blocks through `session.call_tool(...)`:

```python
tools_response = await session.list_tools()
anthropic_tools = [{
    "name": t.name,
    "description": t.description,
    "input_schema": t.inputSchema,   # already the JSON-Schema shape the Messages API expects
} for t in tools_response.tools]

# Inside the loop from post 15, in place of execute_validated_tool(block.name, block.input):
mcp_result = await session.call_tool(block.name, block.input)
text_result = mcp_result.content[0].text
```

Everything else from post 15 — the `MAX_ITERATIONS` cap, `claude-opus-4-8` with `thinking={"type": "adaptive"}`, the message bookkeeping — is unchanged. Only the tool's *implementation* moved to a separate, reusable process, and `t.inputSchema` needs no manual conversion — MCP tool schemas are already the same JSON Schema shape `tools=` expects.

---

## MCP vs. the Framework Tool Abstraction (Post 27)

LangChain's `@tool`/`bind_tools`/`create_agent` (post 27) wrap **a function living in your own Python process** — convenient, but the tool only exists inside that one application. MCP wraps **a separate process or service** behind a standard protocol, so the same accounts server above can be launched by Claude Desktop, called from Claude Code, and consumed by this post's plain client — three unrelated hosts, zero rewritten integration code (the ["broad ecosystem support"](https://modelcontextprotocol.io/docs/getting-started/intro) modelcontextprotocol.io advertises).

The two aren't mutually exclusive: LangChain ships `langchain-mcp-adapters`, which converts an MCP session's tools directly into LangChain tools, so `create_agent` can drive them without a manual `session.call_tool` loop:

```python
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain.agents import create_agent

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await load_mcp_tools(session)          # MCP tools -> LangChain tools
        agent = create_agent(model, tools)              # same create_agent as post 27
```

Source: [`langchain-mcp-adapters` README](https://github.com/langchain-ai/langchain-mcp-adapters). Framework tool abstractions and MCP solve different layers of the same problem: one wires a function into a prompt; the other lets that function's *server* outlive any one framework.

---

## When MCP Earns Its Weight — and When It's Overkill

Reach for MCP when the tool or data source needs to be **shared across independently-built AI applications** — your accounts lookup used by Claude Desktop for support staff *and* Claude Code for engineers *and* a custom internal agent — or when you're **consuming someone else's server** (Sentry, GitHub, a filesystem) without writing integration code per host. It's the right call when the tool is a product in its own right, not a private implementation detail of one agent.

It's ceremony when the tool has exactly one caller in one codebase: a separate process, a stdio or HTTP transport, and a protocol handshake are pure overhead next to a `@tool`-decorated function (post 27) or a hand-written JSON schema (post 15) that never leaves the interpreter. Build the direct version first; promote it to an MCP server only once a second, independent host actually needs to call it.

---

## Practical Checklist

| Practice | Why it matters |
|----------|----------------|
| Start with a direct tool call (post 15/27); promote to MCP only when a second host needs it | MCP's cost — a process, a transport, a protocol — buys nothing for a single caller |
| Validate/whitelist tool arguments inside the function body, even with type hints in place | Type hints check shape, not safety — `get_account_balance` still checks the regex |
| Never f-string a tool argument into SQL, a shell command, or a file path | The same rule as posts 15/27 — MCP doesn't change the trust boundary |
| Never `print()` in a stdio-transport server | Corrupts the JSON-RPC stream; log to `sys.stderr` or a logging library instead |
| Pin `mcp<2` (or an explicit `2.0.0bN`) rather than an unpinned install | v2 is alpha; an unpinned upgrade could land breaking changes mid-project |
| Cite a live source for every MCP class/function before shipping | The SDK is under active development; a stale snippet is worse than none |

---

## Final Thoughts

MCP doesn't replace the agentic loop from post 15 or the framework tool abstractions from post 27 — it standardizes what sits behind either one: a tool server that any compliant client can discover and call, without per-host glue code. That standardization is worth real engineering cost when a tool needs to serve more than one application; for a tool with one caller, the direct approaches this series already covered remain the simpler, and correct, default.
