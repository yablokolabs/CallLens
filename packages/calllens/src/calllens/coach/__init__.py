"""CallLens Coach — autonomous conversation coach (Strands Agents SDK).

This package is the agentic-ai add-on: it reuses CallLens as the
conversation-intelligence tool layer and adds autonomous decision-making
(NO_ACTION / COACH / ESCALATE) with explainable-ai, sales-coaching,
human-in-the-loop, and MCP integration.

Public surface:
  - coach.decisions  — decision schema and deterministic policy
  - coach.history    — lightweight rep history store
  - coach.mcp_tools  — Strands @tool adapters over CallLens capabilities
  - coach.agent      — Strands Agent that orchestrates the decision loop
  - coach.demo       — synthetic demo calls (3 scenarios) + seeding
  - coach.service    — high-level service wiring FastAPI + history + agent
"""

from calllens.coach.decisions import CoachDecision, DecisionType

__all__ = ["CoachDecision", "DecisionType"]
