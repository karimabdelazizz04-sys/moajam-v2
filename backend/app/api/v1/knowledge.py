import io
import json
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps import verify_api_key

router = APIRouter(
    prefix="/knowledge",
    tags=["knowledge"],
    dependencies=[Depends(verify_api_key)],
)

# backend/knowledge - same directory knowledge_service reads for retrieval, so
# files uploaded here feed straight into the translation grounding for their
# collection. __file__ is backend/app/api/v1/knowledge.py -> up 4 = backend.
KNOWLEDGE_DIR = Path(__file__).parent.parent.parent.parent / "knowledge"
INDEX_PATH = KNOWLEDGE_DIR / ".knowledge_index.json"


def load_index() -> list[dict]:
    try:
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - missing/corrupt index -> start empty
        return []


def save_index(entries: list[dict]) -> None:
    INDEX_PATH.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def chunk_text(text: str, size: int = 1500, overlap: int = 200) -> list[str]:
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i : i + size])
        i += size - overlap
    return [c for c in chunks if len(c.strip()) > 50]


# GET /api/v1/knowledge/files
@router.get("/files")
def list_files():
    entries = load_index()
    files: dict[str, dict] = {}
    for e in entries:
        fname = e.get("file", "")
        if fname.startswith("uploaded_"):
            if fname not in files:
                files[fname] = {
                    "file": fname,
                    # Strip the "uploaded_" prefix so the UI/DELETE call use the
                    # original filename the user sees.
                    "filename": fname[len("uploaded_"):],
                    "collection": e.get("collection"),
                    "chunks": 0,
                }
            files[fname]["chunks"] += 1
    return list(files.values())


# POST /api/v1/knowledge/upload
@router.post("/upload")
async def upload_knowledge(
    file: UploadFile = File(...),
    collection: str = Form(...),
):
    content = await file.read()
    filename = file.filename
    suffix = Path(filename).suffix.lower()

    # استخراج النص
    text = ""
    if suffix == ".txt":
        text = content.decode("utf-8", errors="ignore")
    elif suffix == ".pdf":
        import fitz

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            doc = fitz.open(tmp_path)
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
        finally:
            if tmp_path:
                os.unlink(tmp_path)
    elif suffix == ".docx":
        from docx import Document

        doc = Document(io.BytesIO(content))
        text = "\n".join(p.text for p in doc.paragraphs)
    else:
        raise HTTPException(400, f"نوع ملف غير مدعوم: {suffix or '(بدون امتداد)'}")

    if not text.strip():
        raise HTTPException(400, "تعذّر استخراج نص من الملف")

    # تقسيم chunks
    chunks = chunk_text(text)

    # إضافة للـ index
    entries = load_index()
    file_key = f"uploaded_{filename}"

    # احذف القديم لو موجود
    entries = [e for e in entries if e.get("file") != file_key]

    for chunk in chunks:
        entries.append(
            {
                "file": file_key,
                "collection": collection,
                "text": chunk,
            }
        )

    save_index(entries)
    return {"chunks_added": len(chunks), "collection": collection, "filename": filename}


# DELETE /api/v1/knowledge/files/{filename}
@router.delete("/files/{filename}")
def delete_file(filename: str):
    entries = load_index()
    file_key = f"uploaded_{filename}"
    before = len(entries)
    entries = [e for e in entries if e.get("file") != file_key]
    save_index(entries)
    deleted = before - len(entries)
    if deleted == 0:
        raise HTTPException(404, "الملف غير موجود")
    return {"deleted": deleted}
