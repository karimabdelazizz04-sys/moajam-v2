import base64

from anthropic import Anthropic

from app.core.config import get_settings
from app.services.knowledge_service import COLLECTIONS, retrieve_context, route_collection
from app.services.translation_prompt import SYSTEM_PROMPT

settings = get_settings()

_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

# The raw per-collection knowledge PDFs are 7-100MB each, so we never inline a
# whole file. We pull the most relevant pre-indexed chunks for the matched
# collection and hard-cap their combined size to stay well inside the context
# window. See knowledge_service.build_index / retrieve_context.
_KNOWLEDGE_TOP_K = 6
_MAX_KNOWLEDGE_CHARS = 60000


def _resolve_collection(legal_domain: str | None, source_text: str) -> str:
    """Pick the knowledge collection. An explicit, valid `legal_domain` (a
    collection code like ``F_Tenancy_Real_Estate``) wins; otherwise classify
    the document from its own text.
    """
    if legal_domain:
        ld = legal_domain.strip()
        for code in COLLECTIONS:
            if ld.lower() == code.lower() or ld.upper().startswith(code.upper()):
                return code
    return route_collection(source_text)


def translate_text(
    text: str,
    source_language: str = "auto-detect",
    target_language: str = "Arabic",
    legal_domain: str | None = None,
    timeout: int = 300,
) -> str:
    """Send extracted document text to Claude and return the translated text.

    Grounds the translation in the matched knowledge collection: resolve the
    collection (preferring an explicit legal_domain), pull the most relevant
    pre-indexed chunks from backend/knowledge/ as the knowledge context, and
    feed them alongside the full master SYSTEM_PROMPT.
    """
    collection = _resolve_collection(legal_domain, text)
    knowledge_context = retrieve_context(text, collection, top_k=_KNOWLEDGE_TOP_K)
    if len(knowledge_context) > _MAX_KNOWLEDGE_CHARS:
        knowledge_context = knowledge_context[:_MAX_KNOWLEDGE_CHARS]

    user_content = (
        f"KNOWLEDGE COLLECTION ({collection}):\n"
        f"{knowledge_context}\n\n"
        f"SOURCE DOCUMENT TO TRANSLATE "
        f"(source language: {source_language}, target language: {target_language}):\n"
        f"{text}\n\n"
        f"Translate the above document to {target_language} following all rules in your "
        f"system prompt.\n"
        f"First identify the document type, then find the closest matching layout/sample in "
        f"the KNOWLEDGE COLLECTION above and use it as the formatting and layout reference. "
        f"If the KNOWLEDGE COLLECTION has no matching layout/sample for this document type, "
        f"do NOT impose a generic layout - preserve the original source document's structure, "
        f"field order, layout and formatting as closely as possible (still applying Arabic "
        f"RTL and the letterhead/frame rules)."
    )

    response = _client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=settings.ANTHROPIC_MAX_OUTPUT_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
        timeout=timeout,
    )

    return "".join(block.text for block in response.content if block.type == "text")


def ocr_image(image_bytes: bytes, media_type: str = "image/png", timeout: int = 300) -> str:
    """Extract text verbatim from a single page image using Claude Vision.

    Used as a fallback for scanned/image-only PDFs whose embedded text layer is
    empty. Returns the raw text only - no commentary, no translation.
    """
    encoded = base64.standard_b64encode(image_bytes).decode("utf-8")
    response = _client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=settings.ANTHROPIC_MAX_OUTPUT_TOKENS,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": encoded,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "استخرج كل النص الموجود في هذه الصورة حرفياً كما هو، "
                            "دون أي تعليق أو ترجمة أو تنسيق إضافي. "
                            "إن لم يوجد نص، فلا تُرجع شيئاً."
                        ),
                    },
                ],
            }
        ],
        timeout=timeout,
    )
    return "".join(block.text for block in response.content if block.type == "text")
