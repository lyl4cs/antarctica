"""Agent tests: real ADK loop + real MCP server over stdio, with a scripted model.

The scripted model plays Gemini: it asks for run_audit, then suggest_fixes, then
answers. Everything else is real: ADK's runner executes the tool calls through
McpToolset, which launches our MCP server as a subprocess. So these tests prove
the wiring (tool discovery, argument passing, results flowing back into the next
model turn) and the tracing, without a network or Vertex AI.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

from antarctica_agent.agent import INSTRUCTION, build_agent, mcp_toolset
from antarctica_agent.run import run_once
from antarctica_agent.tracing import Trace
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import Field

FAKE_SERVER = Path(__file__).with_name("fake_mcp_server.py")


def _call(name: str, args: dict) -> types.Content:
    return types.Content(role="model", parts=[
        types.Part(function_call=types.FunctionCall(name=name, args=args))])


class ScriptedLlm(BaseLlm):
    """Returns pre-written turns in order and records every request it receives."""

    turns: list
    requests: list = Field(default_factory=list)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self.requests.append(llm_request)
        content = self.turns[len(self.requests) - 1]
        yield LlmResponse(
            content=content, model_version="scripted",
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=100 * len(self.requests), candidates_token_count=10),
        )


def _tool_results(req: LlmRequest) -> dict:
    out = {}
    for c in req.contents:
        for p in c.parts or []:
            if p.function_response:
                out[p.function_response.name] = p.function_response.response
    return out


def _run(llm: ScriptedLlm, trace: Trace) -> str:
    toolset = mcp_toolset(command=f"{sys.executable} {FAKE_SERVER}")
    agent = build_agent(model=llm, tools=[toolset], trace=trace)
    return asyncio.run(run_once("Make https://shop.test faster.", agent))


def test_agent_audits_then_fixes_then_answers():
    llm = ScriptedLlm(model="scripted", turns=[
        _call("run_audit", {"url": "https://shop.test"}),
        _call("suggest_fixes", {"scan_id": "s1", "limit": 2}),
        types.Content(role="model", parts=[types.Part(text="1. Convert images to WebP")]),
    ])
    trace = Trace()
    answer = _run(llm, trace)

    assert answer == "1. Convert images to WebP"
    assert len(llm.requests) == 3
    # the MCP tools were discovered and offered to the model
    offered = {t.name for t in llm.requests[0].config.tools[0].function_declarations}
    assert {"run_audit", "suggest_fixes", "get_report", "site_history"} <= offered
    # each tool result flowed back into the next model turn
    audit = json.dumps(_tool_results(llm.requests[1])["run_audit"])
    assert "71" in audit and "modern-image-formats" in audit
    fixes = json.dumps(_tool_results(llm.requests[2])["suggest_fixes"])
    assert "fix for render-blocking-resources" in fixes


def test_trace_records_every_step_with_tokens():
    llm = ScriptedLlm(model="scripted", turns=[
        _call("run_audit", {"url": "https://shop.test"}),
        types.Content(role="model", parts=[types.Part(text="done")]),
    ])
    trace = Trace()
    _run(llm, trace)

    kinds = [(s.kind, s.name) for s in trace.steps]
    assert kinds == [("model", "scripted"), ("tool", "run_audit"), ("model", "scripted")]
    assert trace.steps[0].detail == "calls run_audit"
    t = trace.totals()
    assert (t["model_calls"], t["tool_calls"]) == (2, 1)
    assert (t["tokens_in"], t["tokens_out"]) == (300, 20)
    assert "run_audit" in trace.table()


def test_instruction_forbids_invented_numbers():
    assert "never invent" in INSTRUCTION and "suggest_fixes" in INSTRUCTION
