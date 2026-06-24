import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.models.client import Client
from app.models.erp import Notification
from app.models.translation_job import JobStatus, TranslationJob
from app.schemas.translation import TranslationJobCreateResponse, TranslationJobOut
from app.services.docx_service import build_translated_docx
from app.services.file_extract_service import extract_text
from app.services.invoicing_service import create_invoice_for_translation_job
from app.services.openai_service import translate_text
from app.services.wordpress_service import download_source_file, upload_media_to_wordpress

router = APIRouter(
    prefix="/translations",
    tags=["translations"],
    dependencies=[Depends(verify_api_key)],
)

ALLOWED_SUFFIXES = {".docx", ".pdf", ".txt"}


def _run_translation_job(job_id: str, db: Session) -> None:
    """Stateless pipeline: download the source from WordPress, translate it
    fully in memory/temp-files, push the result back to WordPress, and leave
    nothing behind on Render's own disk. Safe to survive a redeploy mid-flight
    only insofar as the job record itself lives in Postgres, not local files.
    """
    job = db.get(TranslationJob, job_id)
    if not job:
        return

    suffix = Path(job.source_filename).suffix.lower() or ".txt"
    source_tmp_path: str | None = None
    output_tmp_path: str | None = None

    try:
        job.status = JobStatus.PROCESSING
        db.commit()

        source_bytes = download_source_file(job.source_file_url)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as source_tmp:
            source_tmp.write(source_bytes)
            source_tmp_path = source_tmp.name

        source_text = extract_text(source_tmp_path)
        translated_text = translate_text(
            source_text,
            source_language=job.source_language,
            target_language=job.target_language,
            legal_domain=job.legal_domain,
        )

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as output_tmp:
            output_tmp_path = output_tmp.name
        build_translated_docx(translated_text, output_tmp_path, target_language=job.target_language)
        output_bytes = Path(output_tmp_path).read_bytes()

        output_filename = f"translated_{Path(job.source_filename).stem}.docx"
        media = upload_media_to_wordpress(
            output_bytes,
            output_filename,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        job.output_url = media["url"]
        job.status = JobStatus.DONE
        db.commit()
        create_invoice_for_translation_job(db, job)
        if job.created_by:
            db.add(
                Notification(
                    recipient=job.created_by,
                    type="job_done",
                    message=f"Translation finished: {job.source_filename}",
                    related_job_id=job.id,
                )
            )
            db.commit()
    except Exception as exc:  # noqa: BLE001
        job.status = JobStatus.FAILED
        job.error_message = str(exc)
        if job.created_by:
            db.add(
                Notification(
                    recipient=job.created_by,
                    type="job_failed",
                    message=f"Translation failed: {job.source_filename} ({exc})",
                    related_job_id=job.id,
                )
            )
    finally:
        job.completed_at = datetime.utcnow()
        db.commit()
        for tmp_path in (source_tmp_path, output_tmp_path):
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)


def _resolve_client_id(
    db: Session,
    client_id: int | None,
    client_email: str | None,
    client_name: str | None,
    client_phone: str | None = None,
) -> int | None:
    if client_id:
        return client_id
    if not client_email:
        return None
    client = db.query(Client).filter(Client.email == client_email).first()
    if not client:
        client = Client(name=client_name or client_email, email=client_email, phone=client_phone)
        db.add(client)
        db.commit()
        db.refresh(client)
    else:
        changed = False
        if client_name and client.name != client_name:
            client.name = client_name
            changed = True
        if client_phone and not client.phone:
            client.phone = client_phone
            changed = True
        if changed:
            db.commit()
    return client.id


@router.post("", response_model=TranslationJobCreateResponse, status_code=201)
def create_translation_job(
    background_tasks: BackgroundTasks,
    source_file_url: str = Form(...),
    source_filename: str = Form(...),
    source_language: str = Form("auto-detect"),
    target_language: str = Form("Arabic"),
    legal_domain: str | None = Form(None),
    client_id: int | None = Form(None),
    client_email: str | None = Form(None),
    client_name: str | None = Form(None),
    client_phone: str | None = Form(None),
    created_by: str | None = Form(None),
    price: float | None = Form(None),
    db: Session = Depends(get_db),
):
    """Create a translation job from a file the caller already uploaded to
    WordPress's Media Library. Render only ever receives a URL here - never
    the file bytes directly - so it never has anything of its own to lose on
    redeploy.
    """
    client_id = _resolve_client_id(db, client_id, client_email, client_name, client_phone)

    suffix = Path(source_filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    job = TranslationJob(
        id=str(uuid.uuid4()),
        client_id=client_id,
        source_filename=source_filename,
        source_file_url=source_file_url,
        source_language=source_language,
        target_language=target_language,
        legal_domain=legal_domain,
        status=JobStatus.PENDING,
        created_by=created_by,
        price=price,
    )
    db.add(job)
    db.commit()

    background_tasks.add_task(_run_translation_job, job.id, db)

    return TranslationJobCreateResponse(job_id=job.id, status=job.status)


@router.get("", response_model=list[TranslationJobOut])
def list_translation_jobs(
    client_id: int | None = None,
    client_email: str | None = None,
    created_by: str | None = None,
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
    if created_by:
        query = query.filter(TranslationJob.created_by == created_by)
    return query.order_by(TranslationJob.created_at.desc()).all()


@router.get("/{job_id}", response_model=TranslationJobOut)
def get_translation_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(TranslationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/download")
def download_translation(job_id: str, db: Session = Depends(get_db)):
    """The translated file lives on WordPress, not on Render - this just
    redirects to the permanent WordPress Media Library URL.
    """
    job = db.get(TranslationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.DONE or not job.output_url:
        raise HTTPException(status_code=409, detail=f"Job is not ready yet (status: {job.status.value})")

    return RedirectResponse(job.output_url)
