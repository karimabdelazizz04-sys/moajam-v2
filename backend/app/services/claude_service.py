import base64

from anthropic import Anthropic

from app.core.config import get_settings
from app.services.knowledge_service import COLLECTIONS, retrieve_split, route_collection
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


def _knowledge_chunks(routing_text: str, collection: str) -> tuple[str, str]:
    """Return (layout_samples, legal_rules) for a translation, size-capped:
    the closest collection samples and the global controlling rules."""
    layout_chunks, global_chunks = retrieve_split(routing_text, collection, top_k=_KNOWLEDGE_TOP_K)
    return layout_chunks[:_MAX_KNOWLEDGE_CHARS], global_chunks[:_MAX_KNOWLEDGE_CHARS]


def translate_text(
    text: str,
    source_language: str = "auto-detect",
    target_language: str = "Arabic",
    legal_domain: str | None = None,
    timeout: int = 300,
) -> str:
    """Translate extracted document text and return a layout_plan_json STRING.

    Used for DOCX/TXT sources (clean text). Resolves the knowledge collection,
    feeds the matched samples + global rules + source text, and asks the model
    for ONLY the layout_plan_json (parsed/rendered downstream into a DOCX).
    """
    collection = _resolve_collection(legal_domain, text)
    layout_chunks, global_chunks = _knowledge_chunks(text, collection)

    user_content = (
        f"## Knowledge Collection ({collection}):\n\n"
        f"### Layout Samples:\n{layout_chunks}\n\n"
        f"### Legal Rules:\n{global_chunks}\n\n"
        f"## Source Document:\n{text}\n\n"
        f"Translate this document to {target_language} and output ONLY a valid "
        f"layout_plan_json.\nNo explanation. No markdown. Only JSON."
    )

    response = _client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=settings.ANTHROPIC_MAX_OUTPUT_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
        timeout=timeout,
    )

    return "".join(block.text for block in response.content if block.type == "text")


def translate_document_images(
    images: list[bytes],
    routing_text: str = "",
    legal_domain: str | None = None,
    target_language: str = "Arabic",
    truncated_note: str = "",
    media_type: str = "image/jpeg",
    timeout: int = 300,
) -> str:
    """Translate a document Claude sees *visually*: send the rendered page
    images as vision blocks so the model preserves the real on-page layout
    (tables, fields, stamps, signatures) instead of working from flattened text.

    `routing_text` is cheap embedded text used only to pick the knowledge
    collection and retrieve reference chunks - it is NOT the content source.
    """
    collection = _resolve_collection(legal_domain, routing_text)
    layout_chunks, global_chunks = _knowledge_chunks(routing_text, collection)

    content: list[dict] = []
    for image_bytes in images:
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.standard_b64encode(image_bytes).decode("utf-8"),
                },
            }
        )

    user_text = (
        f"## Knowledge Collection ({collection}):\n\n"
        f"### Layout Samples:\n{layout_chunks}\n\n"
        f"### Legal Rules:\n{global_chunks}\n\n"
        f"## Source Document (examine it visually in the images above):\n"
        f"{truncated_note}"
        f"Translate this document to {target_language} and output ONLY a valid "
        f"layout_plan_json.\nNo explanation. No markdown. Only JSON."
    )
    content.append({"type": "text", "text": user_text})

    response = _client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=settings.ANTHROPIC_MAX_OUTPUT_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
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
