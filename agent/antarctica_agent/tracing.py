"""Per-step tracing for the agent: what it called, how long it took, how many tokens.

WHY
An agent is a loop: model -> tool -> model -> tool -> answer. When it is slow or
expensive you need to know WHICH step. "The request took 40 s" is useless;
"run_audit took 31 s, the model spent 2.1k tokens deciding to call suggest_fixes
twice" is actionable. This is the "granular tracing" LLM teams ask for.

HOW
ADK lets you register callbacks that run before/after every model call and every
tool call. We time each pair with time.perf_counter() (milliseconds, like the rest
of the codebase) and read token counts from the model's usage metadata. The
callbacks return None, which tells ADK "don't change anything, just observe".
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Step:
    kind: str                 # "model" or "tool"
    name: str                 # model name or tool name
    latency_ms: float
    tokens_in: int = 0
    tokens_out: int = 0
    detail: str = ""          # tool args, or which tools the model chose to call


@dataclass
class Trace:
    steps: list[Step] = field(default_factory=list)
    _t0: dict[str, float] = field(default_factory=dict)

    # --- ADK callbacks -------------------------------------------------------
    def before_model(self, callback_context: Any, llm_request: Any) -> None:
        self._t0["model"] = time.perf_counter()

    def after_model(self, callback_context: Any, llm_response: Any) -> None:
        start = self._t0.pop("model", time.perf_counter())
        usage = getattr(llm_response, "usage_metadata", None)
        calls = []
        content = getattr(llm_response, "content", None)
        for part in (getattr(content, "parts", None) or []):
            if getattr(part, "function_call", None):
                calls.append(part.function_call.name)
        self.steps.append(Step(
            kind="model",
            name=getattr(llm_response, "model_version", None) or "model",
            latency_ms=(time.perf_counter() - start) * 1000,
            tokens_in=(getattr(usage, "prompt_token_count", None) or 0),
            tokens_out=(getattr(usage, "candidates_token_count", None) or 0),
            detail=("calls " + ", ".join(calls)) if calls else "answer",
        ))

    def before_tool(self, tool: Any, args: dict, tool_context: Any) -> None:
        self._t0[f"tool:{tool.name}"] = time.perf_counter()

    def after_tool(self, tool: Any, args: dict, tool_context: Any, tool_response: Any) -> None:
        start = self._t0.pop(f"tool:{tool.name}", time.perf_counter())
        self.steps.append(Step(
            kind="tool", name=tool.name,
            latency_ms=(time.perf_counter() - start) * 1000,
            detail=", ".join(f"{k}={v}" for k, v in args.items()),
        ))

    # --- reporting -----------------------------------------------------------
    def totals(self) -> dict:
        model = [s for s in self.steps if s.kind == "model"]
        return {
            "steps": len(self.steps),
            "model_calls": len(model),
            "tool_calls": len(self.steps) - len(model),
            "tokens_in": sum(s.tokens_in for s in model),
            "tokens_out": sum(s.tokens_out for s in model),
            "total_ms": round(sum(s.latency_ms for s in self.steps), 1),
        }

    def to_dict(self) -> dict:
        return {"totals": self.totals(), "steps": [asdict(s) for s in self.steps]}

    def table(self) -> str:
        rows = [f"{'#':>2}  {'kind':5}  {'name':22}  {'ms':>8}  {'in':>6}  {'out':>5}  detail"]
        for i, s in enumerate(self.steps, 1):
            rows.append(f"{i:>2}  {s.kind:5}  {s.name[:22]:22}  {s.latency_ms:>8.0f}  "
                        f"{s.tokens_in:>6}  {s.tokens_out:>5}  {s.detail[:60]}")
        t = self.totals()
        rows.append(f"total: {t['model_calls']} model + {t['tool_calls']} tool calls, "
                    f"{t['tokens_in']}/{t['tokens_out']} tokens in/out, {t['total_ms']:.0f} ms")
        return "\n".join(rows)
