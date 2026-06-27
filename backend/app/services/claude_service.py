import base64

from anthropic import Anthropic

from app.core.config import get_settings
from app.services.knowledge_service import retrieve_context, route_collection
from app.services.translation_prompt import get_translation_prompt

settings = get_settings()

_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def translate_text(
    text: str,
    source_language: str = "auto-detect",
    target_language: str = "Arabic",
    legal_domain: str | None = None,
    timeout: int = 300,
) -> str:
    """Send extracted document text to Claude and return the translated text.

    Runs a RAG pass first: classify the document into one of the 9 knowledge
    collections, retrieve the closest-matching sample(s) from
    backend/knowledge/, and feed that as grounding context alongside the
    master system prompt.
    """
    collection = route_collection(text)
    sample_context = retrieve_context(text, collection)

    task_context = f"Source language: {source_language}\nTarget language: {target_language}"
    if legal_domain:
        task_context += f"\nDeclared document/legal domain hint: {legal_domain}"
    task_context += f"\nMatched knowledge collection: {collection}"
    if sample_context:
        task_context += f"\n\nRetrieved reference samples:\n{sample_context}"

    system = get_translation_prompt(task_context)

    response = _client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=settings.ANTHROPIC_MAX_OUTPUT_TOKENS,
        system=system,
        messages=[{"role": "user", "content": text}],
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
