# Antarctica ADK agent

A Gemini agent (Google Agent Development Kit) that turns "make this site faster" into a prioritized, evidence-backed fix plan.

```
you: "Make https://shopnovus.us faster."
 └─ Gemini (ADK LlmAgent, ReAct loop)
     ├─ run_audit(url)            ┐
     ├─ suggest_fixes(id, limit)  ├─ tools from McpToolset → launches `antarctica-mcp` (stdio)
     └─ self-check, then answer   ┘                          → your Cloud Run API
```

- **ReAct:** Gemini reasons, calls a tool, reads the result, repeats, then answers.
- **Tools come from the MCP server** (`mcp_server/`), the same ones Claude Desktop uses. Nothing is duplicated.
- **Self-check:** before answering, every recommendation must map to a measured finding, be ordered by savings, and name the metric it moves.
- **Tracing:** each model and tool call is recorded with latency and tokens (`antarctica_agent/tracing.py`).

## Setup (separate environment, see ADR 016)
```bash
cd ~/antarctica
python3 -m venv .venv-agent && source .venv-agent/bin/activate
pip install -e "./agent[dev]"
```
The agent launches the MCP server from your **main** venv, so point it there:
```bash
export ANTARCTICA_MCP_COMMAND=~/antarctica/.venv/bin/antarctica-mcp
export ANTARCTICA_API_URL=https://<your-api>.run.app
export GOOGLE_GENAI_USE_VERTEXAI=TRUE GOOGLE_CLOUD_PROJECT=antarctica-ls GOOGLE_CLOUD_LOCATION=us-central1
```

## Run
```bash
cd agent
python -m antarctica_agent.run https://shopnovus.us --trace-out traces/novus.json
```
Prints the plan, then a trace table like:
```
 #  kind   name                  ms      in    out  detail
 1  model  gemini-2.5-flash     900    1200     40  calls run_audit
 2  tool   run_audit          41000       0      0  url=https://shopnovus.us
 ...
```
Or the ADK dev UI (chat + event inspector): `adk web` from the `agent/` folder.

## Tests (offline)
```bash
cd agent && pip install --no-deps -e .. && python -m pytest -q
```
A scripted model plays Gemini; ADK, McpToolset and our real MCP server (over stdio, backed by a fake API) all run for real.
