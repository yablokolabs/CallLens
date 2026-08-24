"""SQLAlchemy async repository.

Works with SQLite (local, tests) and PostgreSQL (docker compose, Supabase,
RDS) via the ``DATABASE_URL`` setting. Reports are stored as JSON documents
alongside a light relational core for querying.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from calllens.domain.report import AnalysisRun, AnalysisStatus, CallReport
from calllens.domain.transcript import Transcript
from calllens.storage.base import RecordNotFound


class Base(DeclarativeBase):
    pass


def _json_type():
    return JSON().with_variant(JSONB, "postgresql")


class CallRow(Base):
    __tablename__ = "calls"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    filename: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="UPLOADED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class AnalysisRunRow(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    call_id: Mapped[str] = mapped_column(String, index=True)
    organization_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    status: Mapped[str] = mapped_column(String, default="UPLOADED")
    rubric_name: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class TranscriptRow(Base):
    __tablename__ = "transcripts"

    call_id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    transcript_json: Mapped[dict] = mapped_column(_json_type())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ReportRow(Base):
    __tablename__ = "reports"

    call_id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    report_json: Mapped[dict] = mapped_column(_json_type())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class SQLRepository:
    """Async SQLAlchemy repository."""

    def __init__(self, database_url: str) -> None:
        self.engine = create_async_engine(database_url)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_all(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    async def create_call(
        self,
        call_id: str,
        *,
        organization_id: str | None = None,
        filename: str | None = None,
        status: str = "UPLOADED",
        metadata: dict | None = None,
    ) -> dict:
        async with self.session_factory() as session:
            row = CallRow(
                id=call_id, organization_id=organization_id, filename=filename, status=status
            )
            session.add(row)
            await session.commit()
        return {
            "id": call_id,
            "organization_id": organization_id,
            "filename": filename,
            "status": status,
            "metadata": metadata or {},
        }

    async def get_call(self, call_id: str, *, organization_id: str | None = None) -> dict:
        async with self.session_factory() as session:
            row = await session.get(CallRow, call_id)
            if row is None:
                raise RecordNotFound(f"call {call_id} not found")
            return {
                "id": row.id,
                "organization_id": row.organization_id,
                "filename": row.filename,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }

    async def list_calls(self, *, organization_id: str | None = None) -> list[dict]:
        async with self.session_factory() as session:
            stmt = select(CallRow).order_by(CallRow.created_at.desc())
            rows = (await session.execute(stmt)).scalars().all()
            calls = [
                {
                    "id": r.id,
                    "organization_id": r.organization_id,
                    "filename": r.filename,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
            if organization_id is not None:
                calls = [c for c in calls if c.get("organization_id") == organization_id]
            return calls

    async def update_call_status(self, call_id: str, status: str) -> None:
        async with self.session_factory() as session:
            row = await session.get(CallRow, call_id)
            if row is None:
                raise RecordNotFound(f"call {call_id} not found")
            row.status = status
            await session.commit()

    async def save_report(
        self,
        call_id: str,
        report: CallReport,
        *,
        organization_id: str | None = None,
    ) -> None:
        async with self.session_factory() as session:
            row = await session.get(ReportRow, call_id)
            payload = report.model_dump(mode="json")
            if row is None:
                session.add(
                    ReportRow(call_id=call_id, organization_id=organization_id, report_json=payload)
                )
            else:
                row.report_json = payload
            await session.commit()

    async def get_report(self, call_id: str, *, organization_id: str | None = None) -> CallReport:
        async with self.session_factory() as session:
            row = await session.get(ReportRow, call_id)
            if row is None:
                raise RecordNotFound(f"report for call {call_id} not found")
            return CallReport.model_validate(row.report_json)

    async def save_transcript(self, call_id: str, transcript: Transcript) -> None:
        async with self.session_factory() as session:
            row = await session.get(TranscriptRow, call_id)
            payload = transcript.model_dump(mode="json")
            if row is None:
                session.add(TranscriptRow(call_id=call_id, transcript_json=payload))
            else:
                row.transcript_json = payload
            await session.commit()

    async def get_transcript(
        self, call_id: str, *, organization_id: str | None = None
    ) -> Transcript:
        async with self.session_factory() as session:
            row = await session.get(TranscriptRow, call_id)
            if row is None:
                raise RecordNotFound(f"transcript for call {call_id} not found")
            return Transcript.model_validate(row.transcript_json)

    async def delete_call(self, call_id: str, *, organization_id: str | None = None) -> None:
        async with self.session_factory() as session:
            for model in (CallRow, ReportRow, TranscriptRow, AnalysisRunRow):
                row = await session.get(model, call_id)
                if row is not None:
                    await session.delete(row)
            await session.commit()

    async def save_analysis_run(self, run: AnalysisRun) -> None:
        async with self.session_factory() as session:
            row = await session.get(AnalysisRunRow, run.id)
            if row is None:
                session.add(
                    AnalysisRunRow(
                        id=run.id,
                        call_id=run.call_id,
                        organization_id=run.organization_id,
                        status=run.status.value,
                        rubric_name=run.rubric_name,
                        error=run.error,
                    )
                )
            else:
                row.status = run.status.value
                row.error = run.error
            await session.commit()

    async def get_analysis_run(self, run_id: str) -> AnalysisRun:
        async with self.session_factory() as session:
            row = await session.get(AnalysisRunRow, run_id)
            if row is None:
                raise RecordNotFound(f"analysis run {run_id} not found")
            return AnalysisRun(
                id=row.id,
                call_id=row.call_id,
                organization_id=row.organization_id,
                status=AnalysisStatus(row.status),
                rubric_name=row.rubric_name,
                error=row.error,
            )
