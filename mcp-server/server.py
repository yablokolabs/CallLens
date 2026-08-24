"""CallLens MCP Server — conversation intelligence over the Model Context Protocol.

Exposes CallLens analysis tools for agents: analyze transcripts, inspect
rubrics, and get evidence-backed behavioral scores. Uses SSE transport for
MCPize deployment and stdio for local execution.

Tools:
  analyze_transcript — Full pipeline over a transcript string (mock providers by default)
  list_rubrics      — List available declarative rubrics
  score_dimension   — Evidence-backed score for a single rubric dimension
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

# Ensure mcp-server/ and the package are importable both locally and in
# MCPize Cloud Run (where cwd is /app).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "packages", "calllens", "src")
)

from fastmcp import FastMCP  # noqa: E402

mcp = FastMCP(
    "calllens-mcp",
    instructions=(
        "CallLens conversation intelligence: transcribe, diarize, measure "
        "deterministic metrics, and score behavior against declarative rubrics "
        "with timestamped evidence. Every semantic score cites evidence."
    ),
)


def _ok(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


@mcp.tool()
def list_rubrics() -> str:
    """List the available behavioral rubrics and their dimensions."""
    from calllens.config import get_settings
    from calllens.rubrics.loader import load_rubrics_from_dir

    rubrics = load_rubrics_from_dir(get_settings().rubrics_dir)
    return _ok(
        [
            {
                "name": r.name,
                "version": r.version,
                "dimensions": [
                    {"key": d.key, "label": d.label, "weight": d.weight} for d in r.dimensions
                ],
            }
            for r in rubrics
        ]
    )


@mcp.tool()
def score_dimension(transcript: str, dimension: str, rubric: str = "consultative_sales") -> str:
    """Score a single rubric dimension against a transcript with evidence."""
    from calllens.config import get_settings
    from calllens.domain.transcript import Speaker, SpeakerRole, Transcript, Utterance
    from calllens.ingest.parsers import TranscriptParseError, parse_transcript_text
    from calllens.rubrics.loader import load_rubric
    from calllens.scoring.pipeline import RubricScoringPipeline
    from calllens.testing import build_mock_llm

    settings = get_settings()
    rubric_model = load_rubric(f"{settings.rubrics_dir}/{rubric}.yaml")
    dim_model = rubric_model.dimension(dimension)
    if dim_model is None:
        return _ok({"error": f"dimension '{dimension}' not in rubric '{rubric}'"})

    try:
        parsed = parse_transcript_text(transcript)
    except TranscriptParseError:
        # Fall back to a single-utterance transcript so the tool still works
        # on arbitrary agent-provided text.
        parsed = Transcript(
            utterances=[
                Utterance(speaker_id="rep", text=transcript, start_time=0.0, end_time=10.0)
            ],
            speakers=[
                Speaker(id="rep", role=SpeakerRole.REPRESENTATIVE),
                Speaker(id="customer", role=SpeakerRole.CUSTOMER),
            ],
            source="mcp",
        )

    llm = build_mock_llm(parsed)

    async def _score() -> dict:
        pipeline = RubricScoringPipeline(llm, settings)
        result = await pipeline._score_dimension(dim_model, parsed)  # noqa: SLF001
        return result.model_dump(mode="json")

    try:
        return _ok(asyncio.run(_score()))
    except RuntimeError:
        return _ok({"error": "no running event loop available for analysis"})


@mcp.tool()
def analyze_transcript(transcript: str, rubric: str = "consultative_sales") -> str:
    """Run the full CallLens pipeline over a transcript and return the report."""
    from calllens.config import get_settings
    from calllens.graphs import AnalysisGraph
    from calllens.ingest.parsers import parse_transcript_text
    from calllens.rubrics.loader import load_rubric
    from calllens.testing import build_mock_llm

    settings = get_settings()
    parsed = parse_transcript_text(transcript)
    rubric_model = load_rubric(f"{settings.rubrics_dir}/{rubric}.yaml")
    llm = build_mock_llm(parsed)
    graph = AnalysisGraph(llm=llm, settings=settings, rubric=rubric_model)

    async def _run() -> dict:
        state = await graph.run(
            {
                "call_id": "mcp-call",
                "transcript": parsed,
                "rubric": rubric_model,
                "rubric_name": rubric,
            }
        )
        report = state["final_report"]
        return report.model_dump(mode="json")

    try:
        return _ok(asyncio.run(_run()))
    except RuntimeError:
        return _ok({"error": "no running event loop available for analysis"})


if __name__ == "__main__":
    mcp.run()
