import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class IngestionJob:
    job_id: str
    source: str
    phase: str = "queued"
    progress: float = 0.0
    message: str = "Queued for indexing"
    chunks_total: int = 0
    chunks_done: int = 0
    error: str | None = None
    result: dict[str, Any] | None = None


class IngestionJobManager:
    def __init__(self):
        self._jobs: dict[str, IngestionJob] = {}
        self._by_source: dict[str, str] = {}

    def create(self, source: str) -> IngestionJob:
        existing_id = self._by_source.get(source)
        if existing_id:
            existing = self._jobs.get(existing_id)
            if existing and existing.phase not in {"complete", "failed"}:
                return existing

        job = IngestionJob(job_id=str(uuid.uuid4()), source=source)
        self._jobs[job.job_id] = job
        self._by_source[source] = job.job_id
        return job

    def update(self, job_id: str, **fields) -> IngestionJob | None:
        job = self._jobs.get(job_id)
        if not job:
            return None
        for key, value in fields.items():
            if hasattr(job, key):
                setattr(job, key, value)
        return job

    def complete(self, job_id: str, result: dict[str, Any]) -> IngestionJob | None:
        return self.update(
            job_id,
            phase="complete",
            progress=100.0,
            message="Document indexed and ready for Q&A",
            result=result,
            error=None,
        )

    def fail(self, job_id: str, error: str) -> IngestionJob | None:
        return self.update(
            job_id,
            phase="failed",
            message="Indexing failed",
            error=error,
        )

    def get(self, job_id: str) -> IngestionJob | None:
        return self._jobs.get(job_id)

    def get_by_source(self, source: str) -> IngestionJob | None:
        job_id = self._by_source.get(source)
        if not job_id:
            return None
        return self._jobs.get(job_id)

    def list_active(self) -> list[IngestionJob]:
        return [
            job
            for job in self._jobs.values()
            if job.phase not in {"complete", "failed"}
        ]

    def to_dict(self, job: IngestionJob) -> dict[str, Any]:
        return {
            "job_id": job.job_id,
            "source": job.source,
            "phase": job.phase,
            "progress": round(job.progress, 1),
            "message": job.message,
            "chunks_total": job.chunks_total,
            "chunks_done": job.chunks_done,
            "error": job.error,
            "result": job.result,
        }


jobs = IngestionJobManager()
