from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from src.api.jobs import PipelineJob, get_job, list_jobs, start_job
from src.api.schemas import PipelineJobDetail, PipelineJobOut, PredictRequest
from src.ml.predict import run_inference
from src.ml.train import train_model

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


def _job_to_detail(job: PipelineJob) -> PipelineJobDetail:
    return PipelineJobDetail(
        job_id=job.job_id,
        job_type=job.job_type,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        result=job.result,
        error=job.error,
    )


@router.post(
    "/train",
    response_model=PipelineJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_train() -> PipelineJobOut:
    def _work() -> dict:
        run_id, path, metrics = train_model()
        return {
            "model_run_id": run_id,
            "checkpoint_path": str(path),
            "macro_f1": metrics.get("macro_f1"),
            "accuracy": metrics.get("accuracy"),
        }

    job = start_job("train", _work)
    return PipelineJobOut(job_id=job.job_id, job_type=job.job_type, status=job.status)


@router.post(
    "/predict",
    response_model=PipelineJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_predict(body: PredictRequest = PredictRequest()) -> PipelineJobOut:
    model_run_id = body.model_run_id

    def _work() -> dict:
        count = run_inference(model_run_id=model_run_id)
        return {"signals_written": count}

    job = start_job("predict", _work)
    return PipelineJobOut(job_id=job.job_id, job_type=job.job_type, status=job.status)


@router.get("/jobs", response_model=list[PipelineJobDetail])
def list_pipeline_jobs(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[PipelineJobDetail]:
    return [_job_to_detail(j) for j in list_jobs(limit)]


@router.get("/jobs/{job_id}", response_model=PipelineJobDetail)
def get_pipeline_job(job_id: str) -> PipelineJobDetail:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return _job_to_detail(job)
