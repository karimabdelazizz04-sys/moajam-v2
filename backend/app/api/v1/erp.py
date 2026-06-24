from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.models.client import Client
from app.models.erp import Notification, Project, Staff
from app.models.translation_job import JobStatus, TranslationJob
from app.schemas.erp import (
    AnalyticsBreakdown,
    AnalyticsSummaryOut,
    NotificationOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    ReviewUpdate,
    StaffCreate,
    StaffOut,
    StaffStatsOut,
    StaffUpdate,
)
from app.schemas.translation import TranslationJobOut

router = APIRouter(prefix="/erp", tags=["erp"], dependencies=[Depends(verify_api_key)])


# ---------------------------------------------------------------------------
# Staff (translators / reviewers)
# ---------------------------------------------------------------------------


@router.get("/staff", response_model=list[StaffStatsOut])
def list_staff(db: Session = Depends(get_db)):
    staff_members = db.query(Staff).order_by(Staff.created_at.desc()).all()
    results = []
    for staff in staff_members:
        jobs_total = (
            db.query(func.count(TranslationJob.id))
            .filter(TranslationJob.created_by == staff.username)
            .scalar()
            or 0
        )
        jobs_done = (
            db.query(func.count(TranslationJob.id))
            .filter(TranslationJob.created_by == staff.username, TranslationJob.status == JobStatus.DONE)
            .scalar()
            or 0
        )
        revenue_total = (
            db.query(func.coalesce(func.sum(TranslationJob.price), 0.0))
            .filter(TranslationJob.created_by == staff.username, TranslationJob.status == JobStatus.DONE)
            .scalar()
            or 0.0
        )
        results.append(
            StaffStatsOut(
                **StaffOut.model_validate(staff).model_dump(),
                jobs_total=jobs_total,
                jobs_done=jobs_done,
                revenue_total=revenue_total,
            )
        )
    return results


@router.post("/staff", response_model=StaffOut, status_code=201)
def create_staff(payload: StaffCreate, db: Session = Depends(get_db)):
    if db.query(Staff).filter(Staff.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already registered as staff")
    staff = Staff(**payload.model_dump())
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


@router.patch("/staff/{staff_id}", response_model=StaffOut)
def update_staff(staff_id: int, payload: StaffUpdate, db: Session = Depends(get_db)):
    staff = db.get(Staff, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(staff, field, value)
    db.commit()
    db.refresh(staff)
    return staff


@router.delete("/staff/{staff_id}", status_code=204)
def delete_staff(staff_id: int, db: Session = Depends(get_db)):
    staff = db.get(Staff, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    db.delete(staff)
    db.commit()


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(client_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Project)
    if client_id:
        query = query.filter(Project.client_id == client_id)
    return query.order_by(Project.created_at.desc()).all()


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects/{project_id}/jobs", response_model=list[TranslationJobOut])
def list_project_jobs(project_id: int, db: Session = Depends(get_db)):
    return (
        db.query(TranslationJob)
        .filter(TranslationJob.project_id == project_id)
        .order_by(TranslationJob.created_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# Review workflow
# ---------------------------------------------------------------------------


@router.patch("/jobs/{job_id}/review", response_model=TranslationJobOut)
def review_job(job_id: str, payload: ReviewUpdate, db: Session = Depends(get_db)):
    job = db.get(TranslationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.reviewer_username = payload.reviewer_username
    job.review_status = payload.review_status
    job.review_notes = payload.review_notes
    db.commit()
    db.refresh(job)

    if payload.reviewer_username and payload.review_status == "pending":
        db.add(
            Notification(
                recipient=payload.reviewer_username,
                type="review_assigned",
                message=f"Assigned to review job: {job.source_filename}",
                related_job_id=job.id,
            )
        )
        db.commit()
    if job.created_by and payload.review_status in {"approved", "rejected"}:
        db.add(
            Notification(
                recipient=job.created_by,
                type=f"review_{payload.review_status}",
                message=f"Your job '{job.source_filename}' was {payload.review_status} by review.",
                related_job_id=job.id,
            )
        )
        db.commit()

    return job


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


@router.get("/analytics/summary", response_model=AnalyticsSummaryOut)
def analytics_summary(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(TranslationJob)
    if start_date:
        query = query.filter(TranslationJob.created_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(TranslationJob.created_at <= datetime.combine(end_date, datetime.max.time()))
    jobs = query.all()

    jobs_by_status: dict[str, int] = {}
    revenue_total = 0.0
    by_translator: dict[str, dict] = {}
    by_client: dict[str, dict] = {}

    client_names = {c.id: c.name for c in db.query(Client).all()}

    for job in jobs:
        status_key = job.status.value if hasattr(job.status, "value") else str(job.status)
        jobs_by_status[status_key] = jobs_by_status.get(status_key, 0) + 1

        amount = job.price or 0.0
        if job.status == JobStatus.DONE:
            revenue_total += amount

        translator_key = job.created_by or "unknown"
        t = by_translator.setdefault(
            translator_key, {"jobs_total": 0, "jobs_done": 0, "jobs_failed": 0, "revenue_total": 0.0}
        )
        t["jobs_total"] += 1
        if job.status == JobStatus.DONE:
            t["jobs_done"] += 1
            t["revenue_total"] += amount
        if job.status == JobStatus.FAILED:
            t["jobs_failed"] += 1

        client_key = client_names.get(job.client_id, "unknown") if job.client_id else "unknown"
        c = by_client.setdefault(
            client_key, {"jobs_total": 0, "jobs_done": 0, "jobs_failed": 0, "revenue_total": 0.0}
        )
        c["jobs_total"] += 1
        if job.status == JobStatus.DONE:
            c["jobs_done"] += 1
            c["revenue_total"] += amount
        if job.status == JobStatus.FAILED:
            c["jobs_failed"] += 1

    return AnalyticsSummaryOut(
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        jobs_total=len(jobs),
        jobs_by_status=jobs_by_status,
        revenue_total=revenue_total,
        by_translator=[AnalyticsBreakdown(key=k, **v) for k, v in by_translator.items()],
        by_client=[AnalyticsBreakdown(key=k, **v) for k, v in by_client.items()],
    )


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(recipient: str, unread_only: bool = False, db: Session = Depends(get_db)):
    query = db.query(Notification).filter(Notification.recipient == recipient)
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    return query.order_by(Notification.created_at.desc()).all()


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(notification_id: int, db: Session = Depends(get_db)):
    notification = db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification
