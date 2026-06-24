import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class TranslationJob(Base):
    __tablename__ = "translation_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)

    source_filename: Mapped[str] = mapped_column(String(255))
    # Permanent WordPress Media Library URL of the original upload - Render never stores this file.
    source_file_url: Mapped[str] = mapped_column(String(1000))
    # Permanent WordPress Media Library URL of the finished translated DOCX.
    output_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    source_language: Mapped[str] = mapped_column(String(32), default="auto")
    target_language: Mapped[str] = mapped_column(String(32), default="ar")
    legal_domain: Mapped[str | None] = mapped_column(String(128), nullable=True)

    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The translator (WordPress username/email) who submitted this job on the client's behalf.
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Price the translator set for this job; used as the auto-generated invoice's unit price.
    price: Mapped[float | None] = mapped_column(Float, nullable=True)

    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    reviewer_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="not_required")
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    client = relationship("Client", back_populates="translation_jobs")
    invoice = relationship("Invoice", back_populates="translation_job", uselist=False)
    project = relationship("Project", back_populates="jobs")

    @property
    def client_name(self) -> str | None:
        return self.client.name if self.client else None
