import json
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import requests
from anthropic import APITimeoutError
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.client import Client
from app.models.erp import Notification
from app.models.translation_job import JobStatus, TranslationJob
from app.schemas.translation import TranslationJobCreateResponse, TranslationJobOut
from app.services.docx_service import (
    build_docx_from_layout_plan,
    build_translated_docx,
    parse_layout_plan,
)
from app.services.file_extract_service import extract_text, render_pdf_to_images
from app.services.invoicing_service import create_invoice_for_translation_job
from app.services.claude_service import translate_document_images, translate_text
from app.services.wordpress_service import (
    WordPressMediaError,
    download_source_file,
    upload_media_to_wordpress,
    upload_source_to_wordpress,
)

settings = get_settings()

router = APIRouter(
    prefix="/translations",
    tags=["translations"],
    dependencies=[Depends(verify_api_key)],
)

ALLOWED_SUFFIXES = {".docx", ".pdf", ".txt"}


def _run_translation_job(job_id: str) -> None:
    """Stateless pipeline: download the source from WordPress, translate it
    fully in memory/temp-files, push the result back to WordPress, and leave
    nothing behind on Render's own disk. Safe to survive a redeploy mid-flight
    only insofar as the job record itself lives in Postgres, not local files.

    Opens its OWN database session (via SessionLocal) instead of reusing the
    request-scoped one: a background task runs after the request returns, by
    which point the request's session has already been closed - reusing it left
    jobs stuck on PROCESSING because the final commit silently failed.
    """
    db = SessionLocal()
    job = db.get(TranslationJob, job_id)
    if not job:
        db.close()
        return

    suffix = Path(job.source_filename).suffix.lower() or ".txt"
    source_tmp_path: str | None = None
    output_tmp_path: str | None = None

    try:
        print(f"[job {job_id}] start", flush=True)
        job.status = JobStatus.PROCESSING
        db.commit()

        source_bytes = download_source_file(job.source_file_url)
        print(f"[job {job_id}] downloaded {len(source_bytes)} bytes", flush=True)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as source_tmp:
            source_tmp.write(source_bytes)
            source_tmp_path = source_tmp.name

        if suffix == ".pdf":
            # Vision path: Claude sees the actual pages so it preserves on-page
            # layout. Cheap embedded text (no OCR) is used ONLY to route the
            # collection and retrieve reference chunks - not as the content.
            try:
                routing_text = extract_text(source_tmp_path, ocr_fallback=False)
            except Exception:  # noqa: BLE001
                routing_text = ""
            images, total_pages = render_pdf_to_images(source_tmp_path)
            if not images:
                raise ValueError("تعذّر تحويل صفحات الملف لصور للترجمة البصرية.")
            note = ""
            if total_pages > len(images):
                note = (
                    f"ملاحظة: المستند يحتوي {total_pages} صفحة؛ "
                    f"تُرجمت أول {len(images)} صفحات فقط.\n\n"
                )
            print(
                f"[job {job_id}] vision translate {len(images)}/{total_pages} page(s)",
                flush=True,
            )
            layout_plan_json = translate_document_images(
                images,
                routing_text=routing_text,
                legal_domain=job.legal_domain,
                target_language=job.target_language,
                truncated_note=note,
                timeout=300,
            )
        else:
            source_text = extract_text(source_tmp_path)
            print(
                f"[job {job_id}] extracted text length={len(source_text) if source_text else 0}",
                flush=True,
            )
            if not source_text or not source_text.strip():
                raise ValueError(
                    "تعذّر استخراج نص من الملف. قد يكون مصوّراً (scanned) أو محمياً."
                )
            print(f"[job {job_id}] translating...", flush=True)
            layout_plan_json = translate_text(
                source_text,
                source_language=job.source_language,
                target_language=job.target_language,
                legal_domain=job.legal_domain,
                timeout=300,
            )
        print(f"[job {job_id}] layout_plan length={len(layout_plan_json)}", flush=True)

        # Translation now returns a layout_plan_json string -> parse it and
        # build a professional RTL DOCX. If the JSON can't be parsed, fall back
        # to rendering the raw model output as plain text so the job still
        # delivers a file instead of failing outright.
        try:
            layout_plan = parse_layout_plan(layout_plan_json)
            output_bytes = build_docx_from_layout_plan(layout_plan)
            print(
                f"[job {job_id}] built docx from {len(layout_plan.get('blocks', []))} block(s)",
                flush=True,
            )
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"[job {job_id}] layout_plan parse failed ({exc}); using plain-text fallback", flush=True)
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as output_tmp:
                output_tmp_path = output_tmp.name
            build_translated_docx(
                layout_plan_json, output_tmp_path, target_language=job.target_language
            )
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
        print(f"[job {job_id}] done", flush=True)
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
    except (APITimeoutError, requests.exceptions.Timeout) as exc:
        # Claude or WordPress network call blew past its per-request timeout
        # (5 min). Surface a friendly reason instead of a raw stack message.
        job.status = JobStatus.FAILED
        job.error_message = f"Timeout: Translation took too long (5 minutes). {exc}"
        if job.created_by:
            db.add(
                Notification(
                    recipient=job.created_by,
                    type="job_failed",
                    message=f"Translation timed out: {job.source_filename}",
                    related_job_id=job.id,
                )
            )
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
        db.close()
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


@router.post("/upload", status_code=201)
def upload_source_file(file: UploadFile = File(...)):
    """Accept a file from the dashboard/portal, relay it to the WordPress Media
    Library using backend-only credentials, and return its permanent URL. The
    browser never sees the WordPress Application Password.

    The returned `url` is what you then pass as `source_file_url` to
    POST /api/v1/translations.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix or '(none)'}")

    content = file.file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413, detail=f"File too large (max {settings.MAX_UPLOAD_SIZE_MB} MB)"
        )

    try:
        media = upload_source_to_wordpress(
            content,
            file.filename,
            file.content_type or "application/octet-stream",
        )
    except WordPressMediaError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {"url": media["url"], "filename": file.filename, "id": media["id"]}


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

    background_tasks.add_task(_run_translation_job, job.id)

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


@router.post("/{job_id}/retry")
def retry_translation_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Re-queue a job that got stuck (e.g. left in PROCESSING after a crash or a
    redeploy mid-flight) or that previously FAILED. Resets it to PENDING and
    runs the pipeline again."""
    job = db.get(TranslationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = JobStatus.PENDING
    job.error_message = None
    db.commit()
    background_tasks.add_task(_run_translation_job, job.id)
    return {"job_id": job.id, "status": job.status}


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
