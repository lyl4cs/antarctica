"""ADK multi-agent pipeline. OWNER ONLY.

Planned agents:
  planner   -> reads a ParsedReport and decides which findings are worth fixing
  diagnoser -> for each finding, calls core.rag.retrieve and explains the root cause
  fixer     -> writes a concrete code patch, critiques its own patch (self-reflection),
               and revises it at most N times

Interview questions to be able to answer:
  - What is a ReAct loop? Where exactly does it happen in your code?
  - How does self-reflection stop? (max iterations? critic confidence?)
  - What state passes between agents, and where is it stored?
  - How do you trace one request end to end (tokens, latency, cost per step)?
"""

from __future__ import annotations

from dataclasses import dataclass

from services.scanner.parse import ParsedReport


@dataclass
class FixProposal:
    audit_id: str
    diagnosis: str
    patch: str  # unified diff or code snippet
    confidence: float
    iterations: int
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float


def run_pipeline(report: ParsedReport) -> list[FixProposal]:
    raise NotImplementedError
