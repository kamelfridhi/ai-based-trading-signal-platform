"""In-memory background job tracking for pipeline endpoints."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal

JobStatus = Literal["queued", "running", "completed", "failed"]
JobType = Literal["train", "predict"]

_executor = ThreadPoolExecutor(max_workers=1)
_lock = threading.Lock()
_jobs: dict[str, "PipelineJob"] = {}


@dataclass
class PipelineJob:
    job_id: str
    job_type: JobType
    status: JobStatus = "queued"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


def start_job(job_type: JobType, fn: Callable[[], dict[str, Any]]) -> PipelineJob:
    job_id = str(uuid.uuid4())
    job = PipelineJob(job_id=job_id, job_type=job_type)

    with _lock:
        _jobs[job_id] = job

    def _run() -> None:
        with _lock:
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
        try:
            result = fn()
            with _lock:
                job.status = "completed"
                job.result = result
                job.finished_at = datetime.now(timezone.utc)
        except Exception as exc:
            with _lock:
                job.status = "failed"
                job.error = str(exc)
                job.finished_at = datetime.now(timezone.utc)

    _executor.submit(_run)
    return job


def get_job(job_id: str) -> PipelineJob | None:
    with _lock:
        return _jobs.get(job_id)


def list_jobs(limit: int = 20) -> list[PipelineJob]:
    with _lock:
        jobs = sorted(_jobs.values(), key=lambda j: j.created_at, reverse=True)
    return jobs[:limit]
