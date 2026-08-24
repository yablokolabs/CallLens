"""Application state and dependency wiring."""

from __future__ import annotations

from dataclasses import dataclass, field

from calllens.api.jobs import JobQueue, LocalJobQueue
from calllens.api.rubric_registry import RubricRegistry
from calllens.api.service import AnalysisService
from calllens.config import Settings
from calllens.providers.llm.base import LLMProvider
from calllens.providers.speech.base import SpeechProvider
from calllens.storage.base import Repository


@dataclass
class AppState:
    """Everything routers need, wired once at app creation."""

    settings: Settings
    repository: Repository
    speech: SpeechProvider
    llm: LLMProvider
    rubrics: RubricRegistry
    job_queue: JobQueue = field(default_factory=LocalJobQueue)
    organization_id: str | None = None

    @property
    def service(self) -> AnalysisService:
        return AnalysisService(self.repository, self.speech, self.llm, self.settings)
