from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.erp import ProjectStatus, StaffRole


class StaffCreate(BaseModel):
    username: str
    name: str
    email: str | None = None
    phone: str | None = None
    role: StaffRole = StaffRole.TRANSLATOR
    commission_rate: float = 0.0
    is_active: bool = True


class StaffUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    role: StaffRole | None = None
    commission_rate: float | None = None
    is_active: bool | None = None


class StaffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    name: str
    email: str | None
    phone: str | None
    role: StaffRole
    commission_rate: float
    is_active: bool
    created_at: datetime


class StaffStatsOut(StaffOut):
    jobs_total: int
    jobs_done: int
    revenue_total: float


class ProjectCreate(BaseModel):
    name: str
    client_id: int | None = None
    status: ProjectStatus = ProjectStatus.OPEN
    notes: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    client_id: int | None = None
    status: ProjectStatus | None = None
    notes: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    client_id: int | None
    status: ProjectStatus
    notes: str | None
    created_at: datetime


class ReviewUpdate(BaseModel):
    reviewer_username: str | None = None
    review_status: str  # pending | approved | rejected | not_required
    review_notes: str | None = None


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipient: str
    type: str
    message: str
    related_job_id: str | None
    related_invoice_id: int | None
    is_read: bool
    created_at: datetime


class AnalyticsBreakdown(BaseModel):
    key: str
    jobs_total: int
    jobs_done: int
    jobs_failed: int
    revenue_total: float


class AnalyticsSummaryOut(BaseModel):
    start_date: str | None
    end_date: str | None
    jobs_total: int
    jobs_by_status: dict[str, int]
    revenue_total: float
    by_translator: list[AnalyticsBreakdown]
    by_client: list[AnalyticsBreakdown]
