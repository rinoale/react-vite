from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.dependencies import require_role
from db.connector import SessionLocal, get_db
from db.models import JobRun
from db.schemas import JobOut, JobRunOut, PaginatedJobRunResponse
from jobs import REGISTRY

router = APIRouter(
    dependencies=[Depends(require_role("admin"))],
)


def _last_run(db: Session, job_name: str) -> JobRunOut | None:
    row = (
        db.query(JobRun)
        .filter(JobRun.job_name == job_name)
        .order_by(JobRun.id.desc())
        .first()
    )
    return JobRunOut.model_validate(row) if row else None


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db)) -> list[JobOut]:
    return [
        JobOut(name=name, description=meta["description"], last_run=_last_run(db, name))
        for name, meta in REGISTRY.items()
    ]


@router.post("/jobs/{job_name}/run")
def trigger_job(
    job_name: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> JobRunOut:
    if job_name not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_name}")

    run = JobRun(job_name=job_name, status="pending")
    db.add(run)
    db.commit()
    db.refresh(run)

    run_id = run.id
    background_tasks.add_task(_execute_job, run_id, job_name)
    return JobRunOut.model_validate(run)


@router.get("/jobs/history")
def job_history(
    job_name: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> PaginatedJobRunResponse:
    q = db.query(JobRun)
    if job_name:
        q = q.filter(JobRun.job_name == job_name)
    rows = q.order_by(JobRun.id.desc()).limit(limit).offset(offset).all()
    return PaginatedJobRunResponse(limit=limit, offset=offset, rows=rows)


def _execute_job(run_id: int, job_name: str) -> None:
    db = SessionLocal()
    try:
        run = db.query(JobRun).get(run_id)
        run.status = "running"
        db.commit()

        result = REGISTRY[job_name]["fn"](db)

        run.status = "completed"
        run.result_summary = str(result) if result else None
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        db.rollback()
        run = db.query(JobRun).get(run_id)
        if run:
            run.status = "failed"
            run.error = str(exc)[:500]
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
