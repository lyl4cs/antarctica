"""Run the agent once from the terminal and print its plan plus a per-step trace.

    python -m antarctica_agent.run https://shopnovus.us
    python -m antarctica_agent.run https://shopnovus.us --trace-out traces/novus.json

Needs: ANTARCTICA_API_URL (your Cloud Run API), `antarctica-mcp` on PATH (or set
ANTARCTICA_MCP_COMMAND), and Vertex AI access for Gemini:
GOOGLE_GENAI_USE_VERTEXAI=TRUE, GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from google.adk.runners import InMemoryRunner
from google.genai import types

from antarctica_agent.agent import build_agent
from antarctica_agent.tracing import Trace


async def run_once(prompt: str, agent: Any, user_id: str = "cli") -> str:
    """One conversation turn: returns the agent's final text."""
    runner = InMemoryRunner(agent=agent, app_name="antarctica")
    session = await runner.session_service.create_session(app_name="antarctica",
                                                          user_id=user_id)
    final = ""
    try:
        async for event in runner.run_async(
            user_id=user_id, session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final = "".join(p.text or "" for p in event.content.parts)
    finally:
        await runner.close()  # shuts down the MCP subprocess
    return final


def main() -> None:  # pragma: no cover - needs Gemini + the live API
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--trace-out", type=Path)
    a = ap.parse_args()

    trace = Trace()
    answer = asyncio.run(run_once(f"Make {a.url} faster.", build_agent(trace=trace)))
    print(answer)
    print("\n--- trace ---")
    print(trace.table())
    if a.trace_out:
        a.trace_out.parent.mkdir(parents=True, exist_ok=True)
        a.trace_out.write_text(json.dumps(trace.to_dict(), indent=2))


if __name__ == "__main__":
    main()
