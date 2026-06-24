import json
import re
from pathlib import Path

from openai import OpenAI

from app.core.config import get_settings
from app.services.file_extract_service import extract_text

settings = get_settings()

_client = OpenAI(api_key=settings.OPENAI_API_KEY)

COLLECTIONS = {
    "A_Banking_Financial": "cheques, returned cheque memos, returned cheque e-advice, bank return "
    "notices, cheque dishonour evidence, cheque-related bank/financial evidence",
    "B_Shipping_Customs_Logistics": "logistics, customs, shipping, freight, container documents, "
    "shipping invoices, tax/proforma invoices, port/terminal charges, bills of lading, customs "
    "declarations, packing lists, delivery orders",
    "C_Corporate_Commercial": "company documents, commercial/trade licenses, corporate certificates, "
    "board/shareholder resolutions, quotations, business/legal commercial documents",
    "D_POA_Legal_Instruments": "POA/legal agency, MOJ attestation, authorizations, declarations, "
    "undertakings, notarial/legal instruments",
    "E_Government_Personal": "passports, Emirates IDs, IDs, birth/marriage/death certificates, "
    "immigration/civil/government documents",
    "F_Tenancy_Real_Estate": "tenancy contracts, Ejari, tenancy addenda, real estate notices, property "
    "documents, landlord/tenant legal evidence",
    "G_Correspondence_Evidence": "emails, WhatsApp evidence, notices, letters, formal notices, demand "
    "letters, correspondence screenshots, communication evidence",
    "H_Medical": "medical reports, hospital reports, lab reports, radiology, CT, ultrasound, operative "
    "reports, prescriptions, medical certificates, medical liability decisions/grievances",
    "I_Translator_Affairs_Internal": "UAE legal translation requirements, final review rules, glossary, "
    "legal dictionary and official UAE terminology",
}

# Files that apply to every document regardless of matched collection (letterhead/frame rules,
# master formatting rules, override instructions) - always included in retrieved context.
GLOBAL_FILENAME_MARKERS = ("MASTER_RULES", "LETTERHEAD_MASTER", "OVERRIDE")
GLOBAL_COLLECTION = "GLOBAL"

INDEX_PATH = Path(settings.KNOWLEDGE_DIR) / ".knowledge_index.json"
CHUNK_SIZE = 1500  # characters per chunk
EMBEDDING_MODEL = "text-embedding-3-small"


def _chunk_text(text: str, size: int = CHUNK_SIZE) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    return [text[i : i + size] for i in range(0, len(text), size) if text[i : i + size].strip()]


def _guess_collection_for_file(filename: str, text: str) -> str:
    """Classify a knowledge file into one of the 9 collections (or GLOBAL).

    Prefers an exact match between the filename and a collection code (the
    knowledge folder already ships several files named e.g.
    `C_Corporate_Commercial.pdf`), then falls back to keyword overlap with
    each collection's description, defaulting to the internal/translator
    -affairs collection when nothing scores above zero.
    """
    upper_name = filename.upper()
    if any(marker in upper_name for marker in GLOBAL_FILENAME_MARKERS):
        return GLOBAL_COLLECTION
    for code in COLLECTIONS:
        if upper_name.startswith(code.upper()):
            return code

    haystack = f"{filename}\n{text[:2000]}".lower()
    best_collection = "I_Translator_Affairs_Internal"
    best_score = 0
    for code, description in COLLECTIONS.items():
        keywords = [k.strip().lower() for k in re.split(r"[,/]", description) if k.strip()]
        score = sum(1 for kw in keywords if kw in haystack)
        if score > best_score:
            best_score = score
            best_collection = code
    return best_collection


def build_index() -> dict:
    """Extract every file under KNOWLEDGE_DIR, chunk it, embed every chunk
    with OpenAI, classify it into a collection, and persist the result so
    requests don't need to re-embed the knowledge base every time.
    """
    knowledge_dir = Path(settings.KNOWLEDGE_DIR)
    entries = []
    if knowledge_dir.exists():
        for path in sorted(knowledge_dir.rglob("*")):
            if path.is_dir() or path.name.startswith("."):
                continue
            if path.suffix.lower() not in {".pdf", ".docx", ".txt"}:
                continue
            try:
                text = extract_text(str(path))
            except Exception:
                continue
            if not text.strip():
                continue
            collection = _guess_collection_for_file(path.name, text)
            for chunk in _chunk_text(text):
                entries.append({"file": path.name, "collection": collection, "text": chunk})

    if entries:
        embeddings = _client.embeddings.create(model=EMBEDDING_MODEL, input=[e["text"] for e in entries])
        for entry, emb in zip(entries, embeddings.data):
            entry["embedding"] = emb.embedding

    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return {"chunks_indexed": len(entries)}


def _load_index() -> list[dict]:
    if not INDEX_PATH.exists():
        return []
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def route_collection(source_text: str) -> str:
    """Classify the document into one of the 9 knowledge collections.

    Uses a lightweight OpenAI classification call grounded in the same
    COLLECTION ROUTING rules as the master translation prompt; falls back to
    keyword matching if the call fails (e.g. no key configured yet).
    """
    excerpt = source_text[:3000]
    try:
        listing = "\n".join(f"- {code}: {desc}" for code, desc in COLLECTIONS.items())
        response = _client.responses.create(
            model=settings.OPENAI_MODEL,
            instructions=(
                "Classify the legal document excerpt into exactly one of these collection codes. "
                "Reply with ONLY the collection code, nothing else.\n" + listing
            ),
            input=excerpt,
            max_output_tokens=20,
        )
        code = response.output_text.strip()
        if code in COLLECTIONS:
            return code
    except Exception:
        pass
    return _guess_collection_for_file("", excerpt)


def retrieve_context(source_text: str, collection: str | None = None, top_k: int = 2) -> str:
    """Return the top-k most relevant knowledge chunks as plain text, scoped
    to the matched collection plus anything tagged GLOBAL (letterhead/frame
    and master formatting rules, which apply to every document type).
    """
    entries = _load_index()
    if not entries:
        return ""

    global_entries = [e for e in entries if e["collection"] == GLOBAL_COLLECTION]
    candidates = [e for e in entries if not collection or e["collection"] == collection]
    if not candidates:
        candidates = [e for e in entries if e["collection"] != GLOBAL_COLLECTION]

    try:
        query_embedding = (
            _client.embeddings.create(model=EMBEDDING_MODEL, input=source_text[:3000]).data[0].embedding
        )
    except Exception:
        return ""

    scored = sorted(
        candidates, key=lambda e: _cosine_similarity(e["embedding"], query_embedding), reverse=True
    )
    top = scored[:top_k] + global_entries
    return "\n\n---\n\n".join(f"[Sample from {e['file']} - {e['collection']}]\n{e['text']}" for e in top)
