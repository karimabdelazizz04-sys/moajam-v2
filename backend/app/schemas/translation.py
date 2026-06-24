from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.translation_job import JobStatus


class TranslationJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_id: int | None = None
    client_name: str | None = None
    source_filename: str
    source_file_url: str
    output_url: str | None = None
    source_language: str
    target_language: str
    legal_domain: str | None = None
    status: JobStatus
    error_message: str | None = None
    created_by: str | None = None
    price: float | None = None
    project_id: int | None = None
    reviewer_username: str | None = None
    review_status: str = "not_required"
    review_notes: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class TranslationJobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus
