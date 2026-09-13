"""FastAPI application factory."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from calllens.api.deps import AppState
from calllens.api.jobs import JobQueue
from calllens.api.routers import calls, coach, evals, reps, rubrics
from calllens.api.rubric_registry import RubricRegistry
from calllens.config import Settings, get_settings
from calllens.providers.llm.base import LLMProvider
from calllens.providers.speech.base import SpeechProvider
from calllens.storage.base import Repository

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    repository: Repository | None = None,
    speech: SpeechProvider | None = None,
    llm: LLMProvider | None = None,
    job_queue: JobQueue | None = None,
    rubrics_dir: str | None = None,
    organization_id: str | None = None,
) -> FastAPI:
    """Build the FastAPI application with its dependencies.

    All providers default to offline-safe implementations: the mock speech
    provider and mock LLM, so the API runs with ``docker compose up`` or
    ``calllens server`` without any paid API keys.
    """
    settings = settings or get_settings()

    from calllens.providers.llm import get_llm_provider
    from calllens.providers.speech import get_speech_provider
    from calllens.storage.memory import InMemoryRepository

    repository = repository or InMemoryRepository()
    speech = speech or get_speech_provider(settings, force_mock=not settings.speech_enabled)
    llm = llm or get_llm_provider(settings, force_mock=settings.llm_provider == "mock")
    job_queue = job_queue or _default_job_queue()
    rubric_dir = rubrics_dir or str(settings.rubrics_dir)

    app = FastAPI(
        title="CallLens API",
        version="0.1.0",
        description=(
            "Open-source conversation intelligence and behavioral evaluation "
            "powered by LangGraph. Every semantic score is evidence-backed."
        ),
        openapi_tags=[
            {"name": "calls", "description": "Upload, analyze, and inspect calls."},
            {"name": "rubrics", "description": "Declarative, versioned behavioral rubrics."},
            {"name": "reps", "description": "Representative analytics."},
            {"name": "evals", "description": "Evaluation harness."},
            {"name": "coach", "description": "Coach (Strands agent) — NO_ACTION / COACH / ESCALATE with explainable evidence and human-in-the-loop."},
        ],
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.calllens = AppState(
        settings=settings,
        repository=repository,
        speech=speech,
        llm=llm,
        rubrics=RubricRegistry(rubric_dir),
        job_queue=job_queue,
        organization_id=organization_id,
    )

    app.include_router(calls.router)
    app.include_router(rubrics.router)
    app.include_router(reps.router)
    app.include_router(evals.router)
    app.include_router(coach.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        # Expose both legacy llm_provider and coach model for hackathon checks
        coach_provider = settings.coach_model_provider or settings.model_provider or settings.llm_provider
        return {"status": "ok", "llm_provider": settings.llm_provider, "coach_provider": coach_provider, "demo_mode": settings.demo_mode}

    return app


def _default_job_queue() -> JobQueue:
    from calllens.api.jobs import LocalJobQueue

    return LocalJobQueue()
