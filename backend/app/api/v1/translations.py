import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.core.config import get_settings
from app.models.client import Client
from app.models.translation_job import JobStatus, TranslationJob
from app.schemas.translation import TranslationJobCreateResponse, TranslationJobOut
from app.services.invoicing_service import create_invoice_for_translation_job
from app.services.openai_service import translate_text
from app.services.docx_service import build_translated_docx
from app.services.file_extract_service import UnsupportedFileType, extract_text

router = APIRouter(
    prefix="/translations",
    tags=["translations"],
    dependencies=[Depends(verify_api_key)],
)
settings = get_settings()

ALLOWED_SUFFIXES = {".docx", ".pdf", ".txt"}


def _run_translation_job(job_id: str, db: Session) -> None:
    job = db.get(TranslationJob, job_id)
    if not job:
        return

    try:
        job.status = JobStatus.PROCESSING
        db.commit()

        source_text = extract_text(job.source_path)
        translated_text = translate_text(
            source_text,
            source_language=job.source_language,
            target_language=job.target_language,
            legal_domain=job.legal_domain,
        )

        output_path = str(Path(settings.OUTPUT_DIR) / f"{job.id}.docx")
        build_translated_docx(translated_text, output_path, target_language=job.target_language)

        job.output_path = output_path
        job.status = JobStatus.DONE
        db.commit()
        create_invoice_for_translation_job(db, job)
    except Exception as exc:  # noqa: BLE001
        job.status = JobStatus.FAILED
        job.error_message = str(exc)
    finally:
        from datetime import datetime

        job.completed_at = datetime.utcnow()
        db.commit()


def _resolve_client_id(
    db: Session, client_id: int | None, client_email: str | None, client_name: str | None
) -> int | None:
    if client_id:
        return client_id
    if not client_email:
        return None
    client = db.query(Client).filter(Client.email == client_email).first()
    if not client:
        client = Client(name=client_name or client_email, email=client_email)
        db.add(client)
        db.commit()
        db.refresh(client)
    return client.id


@router.post("", response_model=TranslationJobCreateResponse, status_code=201)
def create_translation_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_language: str = Form("auto-detect"),
    target_language: str = Form("Arabic"),
    legal_domain: str | None = Form(None),
    client_id: int | None = Form(None),
    client_email: str | None = Form(None),
    client_name: str | None = Form(None),
    db: Session = Depends(get_db),
):
    client_id = _resolve_client_id(db, client_id, client_email, client_name)

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    job_id = str(uuid.uuid4())
    upload_path = Path(settings.UPLOAD_DIR) / f"{job_id}{suffix}"
    upload_path.parent.mkdir(parents=True, exist_ok=True)

    with upload_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    job = TranslationJob(
        id=job_id,
        client_id=client_id,
        source_filename=file.filename or "document",
        source_path=str(upload_path),
        source_language=source_language,
        target_language=target_language,
        legal_domain=legal_domain,
        status=JobStatus.PENDING,
    )
    db.add(job)
    db.commit()

    background_tasks.add_task(_run_translation_job, job_id, db)

    return TranslationJobCreateResponse(job_id=job.id, status=job.status)


@router.get("", response_model=list[TranslationJobOut])
def list_translation_jobs(
    client_id: int | None = None,
    client_email: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(TranslationJob)
    if client_email:
        client = db.query(Client).filter(Client.email == client_email).first()
        if not client:
            return []
        client_id = client.id
    if client_id:
        query = query.filter(TranslationJob.client_id == client_id)
    return query.order_by(TranslationJob.created_at.desc()).all()


@router.get("/{job_id}", response_model=TranslationJobOut)
def get_translation_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(TranslationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/download")
def download_translation(job_id: str, db: Session = Depends(get_db)):
    job = db.get(TranslationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.DONE or not job.output_path:
        raise HTTPException(status_code=409, detail=f"Job is not ready yet (status: {job.status.value})")

    filename = f"translated_{Path(job.source_filename).stem}.docx"
    return FileResponse(
        job.output_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
