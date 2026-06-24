from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.translation_job import JobStatus


class TranslationJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_filename: str
    source_language: str
    target_language: str
    legal_domain: str | None = None
    status: JobStatus
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class TranslationJobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus
