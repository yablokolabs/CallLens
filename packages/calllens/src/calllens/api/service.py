"""Analysis orchestration shared by the API and CLI."""

from __future__ import annotations

import logging
import uuid

from calllens.config import Settings
from calllens.domain.report import AnalysisRun, AnalysisStatus
from calllens.domain.rubric import Rubric
from calllens.domain.transcript import Transcript
from calllens.graphs import AnalysisGraph
from calllens.providers.llm.base import LLMProvider
from calllens.providers.speech.base import SpeechProvider
from calllens.storage.base import Repository

logger = logging.getLogger(__name__)


class AnalysisService:
    """Coordinates transcript → graph → persistence."""

    def __init__(
        self,
        repository: Repository,
        speech: SpeechProvider,
        llm: LLMProvider,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.speech = speech
        self.llm = llm
        self.settings = settings

    def _graph(self, rubric: Rubric | None) -> AnalysisGraph:
        return AnalysisGraph(
            speech=self.speech,
            llm=self.llm,
            settings=self.settings,
            rubric=rubric,
        )

    async def analyze(
        self,
        call_id: str,
        transcript: Transcript,
        rubric: Rubric | None,
        *,
        organization_id: str | None = None,
        audio: bytes | None = None,
    ) -> str:
        """Run the pipeline and persist the report. Returns the run id."""
        run_id = str(uuid.uuid4())
        await self.repository.save_analysis_run(
            AnalysisRun(
                id=run_id,
                call_id=call_id,
                organization_id=organization_id,
                status=AnalysisStatus.ANALYZING,
                rubric_name=rubric.name if rubric else None,
                rubric_version=rubric.version if rubric else None,
            )
        )
        await self.repository.update_call_status(call_id, AnalysisStatus.ANALYZING.value)

        try:
            graph = self._graph(rubric)
            state = await graph.run(
                {
                    "call_id": call_id,
                    "organization_id": organization_id,
                    "analysis_run_id": run_id,
                    "transcript": transcript,
                    "audio": audio,
                    "rubric": rubric,
                    "rubric_name": rubric.name if rubric else None,
                }
            )
            report = state["final_report"]
            if report is None:
                raise RuntimeError("pipeline completed without a final report")
            if state.get("transcript") is not None:
                await self.repository.save_transcript(call_id, state["transcript"])
            await self.repository.save_report(call_id, report)
            await self.repository.update_call_status(call_id, AnalysisStatus.COMPLETED.value)
            await self.repository.save_analysis_run(
                AnalysisRun(
                    id=run_id,
                    call_id=call_id,
                    organization_id=organization_id,
                    status=AnalysisStatus.COMPLETED,
                    rubric_name=rubric.name if rubric else None,
                    rubric_version=rubric.version if rubric else None,
                )
            )
        except Exception as exc:  # noqa: BLE001 - failure must be persisted, not lost
            logger.exception("analysis failed for call %s", call_id)
            await self.repository.update_call_status(call_id, AnalysisStatus.FAILED.value)
            await self.repository.save_analysis_run(
                AnalysisRun(
                    id=run_id,
                    call_id=call_id,
                    organization_id=organization_id,
                    status=AnalysisStatus.FAILED,
                    rubric_name=rubric.name if rubric else None,
                    error=str(exc),
                )
            )
            raise
        return run_id
