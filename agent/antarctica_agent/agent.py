"""The Antarctica performance agent: Gemini (via Google ADK) + our MCP tools.

WHAT IT DOES
Given a URL, it produces a prioritized speed-fix plan: audit the page, pick the
findings worth fixing, get grounded fixes for them, check its own plan, answer.

HOW IT WORKS (ReAct)
ADK runs the classic "reason -> act -> observe" loop: Gemini reads the goal and
the tool descriptions, decides to call a tool, ADK executes it and feeds the
result back, and the loop repeats until the model writes a final answer.

WHERE THE TOOLS COME FROM
The agent does NOT reimplement the tools. ADK's McpToolset launches our own MCP
server (`antarctica-mcp`, see mcp_server/server.py) as a subprocess and exposes
its tools to Gemini. One tool layer, two consumers: Claude Desktop uses it
directly, and this Gemini agent uses it too.

SELF-REFLECTION
The instruction makes the model check its draft before answering: every recommended
change must map to a measured finding, be ordered by estimated savings, and say
which metric it should move. Cheap (no extra tool calls) and it stops the classic
failure of confident advice that isn't backed by the audit.

Why a separate environment: google-adk pins an older OpenTelemetry than the
Pub/Sub client in the main package allows, so the agent installs on its own
(agent/pyproject.toml) and talks to the system only through the MCP server.
"""

from __future__ import annotations

import os
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from antarctica_agent.tracing import Trace

MODEL = os.environ.get("AGENT_MODEL", "gemini-2.5-flash")

INSTRUCTION = """You are a web performance engineer. Goal: a short, prioritized plan
that makes the user's page measurably faster.

Process:
1. Call run_audit(url) once. Note the score and the top findings by estimated savings.
2. Pick at most 3 findings worth fixing: biggest estimated savings first; skip ones
   saving under 0.1 s unless nothing else is left.
3. Call suggest_fixes(scan_id, limit=N) ONCE with N = the rank of the last finding
   you picked (fixes come back for the top N findings in order).
4. Before answering, check your draft: every change maps to a finding from the
   audit, items are ordered by estimated savings, each says which metric it should
   move (LCP, FCP, TBT, CLS), and the code fits the site. Fix the draft if not.
5. Answer in markdown: the score and LCP, then a numbered plan (what to change,
   why, expected impact, code), then the sources you used.

If a tool returns an error, say what failed in one line and stop; never invent
numbers that did not come from a tool."""


def mcp_toolset(api_url: str | None = None, command: str | None = None) -> McpToolset:
    """Launch `antarctica-mcp` over stdio. Its command can be overridden for tests."""
    cmd = (command or os.environ.get("ANTARCTICA_MCP_COMMAND", "antarctica-mcp")).split()
    env = {"PATH": os.environ.get("PATH", "")}
    if api_url or os.environ.get("ANTARCTICA_API_URL"):
        env["ANTARCTICA_API_URL"] = api_url or os.environ["ANTARCTICA_API_URL"]
    return McpToolset(connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(command=cmd[0], args=cmd[1:], env=env),
        timeout=30,
    ))


def build_agent(model: Any = MODEL, tools: list | None = None,
                trace: Trace | None = None) -> LlmAgent:
    trace = trace or Trace()
    return LlmAgent(
        name="perf_auditor",
        model=model,
        description="Audits a website's speed and returns a prioritized fix plan.",
        instruction=INSTRUCTION,
        tools=tools if tools is not None else [mcp_toolset()],
        before_model_callback=trace.before_model,
        after_model_callback=trace.after_model,
        before_tool_callback=trace.before_tool,
        after_tool_callback=trace.after_tool,
    )


# `adk web` / `adk run` look for a module-level `root_agent`.
root_agent = build_agent()
