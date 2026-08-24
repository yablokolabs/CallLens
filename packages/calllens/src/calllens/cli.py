"""CallLens CLI.

```bash
calllens analyze call.mp3
calllens analyze call.mp3 --rubric consultative_sales
calllens rubric list
calllens rubric validate ./rubric.yaml
calllens eval run
calllens server
```
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer

from calllens.config import get_settings
from calllens.domain.transcript import Transcript

app = typer.Typer(help="CallLens — conversation intelligence, evidence-backed.")
rubric_app = typer.Typer(help="Manage rubrics.")
eval_app = typer.Typer(help="Run evaluations.")
app.add_typer(rubric_app, name="rubric")
app.add_typer(eval_app, name="eval")


def _resolve_input(path: Path) -> tuple[Transcript | None, bytes | None]:
    suffix = path.suffix.lower()
    if suffix in {".json"}:
        from calllens.ingest.parsers import parse_transcript_json

        return parse_transcript_json(path.read_text(encoding="utf-8")), None
    if suffix in {".txt"}:
        from calllens.ingest.parsers import parse_transcript_text

        return parse_transcript_text(path.read_text(encoding="utf-8")), None
    return None, path.read_bytes()


@app.command()
def analyze(
    path: Path = typer.Argument(..., help="Audio file or transcript (.json/.txt)"),
    rubric: str = typer.Option("consultative_sales", "--rubric", "-r", help="Rubric name"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write the report JSON here"),
    sync: bool = typer.Option(
        False, "--sync", help="Run analysis synchronously (no server needed)"
    ),
) -> None:
    """Analyze a call and print the evidence-backed report."""
    settings = get_settings()
    if not path.exists():
        raise typer.BadParameter(f"file not found: {path}")

    transcript, audio = _resolve_input(path)

    from calllens.api.service import AnalysisService
    from calllens.providers.llm import get_llm_provider
    from calllens.providers.speech import get_speech_provider
    from calllens.rubrics.loader import load_rubric
    from calllens.storage.memory import InMemoryRepository

    rubric_model = (
        load_rubric(Path(settings.rubrics_dir) / f"{rubric}.yaml")
        if (Path(settings.rubrics_dir) / f"{rubric}.yaml").exists()
        else None
    )
    if rubric_model is None:
        raise typer.BadParameter(f"rubric '{rubric}' not found in {settings.rubrics_dir}")

    speech = get_speech_provider(settings, force_mock=not settings.speech_enabled)
    llm = get_llm_provider(settings, force_mock=settings.llm_provider == "mock")

    if sync:
        service = AnalysisService(InMemoryRepository(), speech, llm, settings)

        async def _run() -> None:
            await service.analyze(
                "cli-call", transcript or _empty_transcript(), rubric_model, audio=audio
            )

        asyncio.run(_run())
        return

    repo = InMemoryRepository()

    async def _run_report() -> None:
        call_id = "cli-call"
        await repo.create_call(call_id)
        if transcript is not None:
            await repo.save_transcript(call_id, transcript)
        service = AnalysisService(repo, speech, llm, settings)
        await service.analyze(call_id, transcript or _empty_transcript(), rubric_model, audio=audio)
        report = await repo.get_report(call_id)
        payload = report.model_dump(mode="json")
        text = json.dumps(payload, indent=2, default=str)
        if output:
            output.write_text(text, encoding="utf-8")
            typer.echo(f"Report written to {output}")
        else:
            typer.echo(text)

    asyncio.run(_run_report())


def _empty_transcript() -> Transcript:
    return Transcript(utterances=[], source="empty")


@rubric_app.command("list")
def rubric_list() -> None:
    """List bundled rubrics."""
    from calllens.rubrics.loader import load_rubrics_from_dir

    settings = get_settings()
    rubrics = load_rubrics_from_dir(settings.rubrics_dir)
    for r in rubrics:
        dims = ", ".join(f"{d.label}({d.weight})" for d in r.dimensions)
        typer.echo(f"{r.name} v{r.version} — {len(r.dimensions)} dimensions")
        typer.echo(f"    {dims}")


@rubric_app.command("validate")
def rubric_validate(path: Path = typer.Argument(..., help="Path to a rubric YAML file")) -> None:
    """Validate a rubric document."""
    from calllens.rubrics.loader import RubricParseError, load_rubric
    from calllens.rubrics.validator import validate_rubric

    try:
        rubric = load_rubric(path)
    except RubricParseError as exc:
        raise typer.BadParameter(str(exc)) from exc
    issues = validate_rubric(rubric)
    if issues:
        for issue in issues:
            typer.echo(f"✗ {issue}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"✓ {rubric.name} v{rubric.version} is valid ({len(rubric.dimensions)} dimensions)")


@eval_app.command("run")
def eval_run(
    scenarios: str | None = typer.Option(
        None, "--scenarios", help="Comma-separated scenario subset"
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write the markdown report here"
    ),
) -> None:
    """Run the evaluation harness over the synthetic dataset."""
    from calllens.config import get_settings
    from calllens.evals.harness import EvaluationHarness
    from calllens.evals.synthetic import generate_synthetic_dataset
    from calllens.rubrics.loader import load_rubric

    settings = get_settings()
    rubric = load_rubric(Path(settings.rubrics_dir) / "consultative_sales.yaml")
    names = [s.strip() for s in scenarios.split(",")] if scenarios else None
    calls = generate_synthetic_dataset(scenarios=names)
    harness = EvaluationHarness(rubric)

    async def _run() -> None:
        result = await harness.evaluate(calls)
        markdown = result.to_markdown()
        if output:
            output.write_text(markdown, encoding="utf-8")
        typer.echo(markdown)

    asyncio.run(_run())


@app.command("server")
def server(
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8000, "--port", "-p"),
) -> None:
    """Run the FastAPI server."""
    import uvicorn

    from calllens.api import create_app

    app = create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    app()
