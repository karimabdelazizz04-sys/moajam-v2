import base64
import json
import re

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
_ANALYSIS_MAX_TOKENS = 2048


def _match_collection(value: str | None) -> str | None:
    """Map a free-form collection label onto a known collection code, tolerating
    the shorthand the model sometimes returns (e.g. ``B_Shipping`` for
    ``B_Shipping_Customs_Logistics``). Returns None when nothing matches."""
    if not value:
        return None
    v = value.strip()
    for code in COLLECTIONS:
        if v.lower() == code.lower():
            return code
    for code in COLLECTIONS:
        cu, vu = code.upper(), v.upper()
        if vu.startswith(cu) or cu.startswith(vu):
            return code
    # Last resort: the unique leading letter (A_ ... I_).
    letter = v[:1].upper()
    for code in COLLECTIONS:
        if code.upper().startswith(f"{letter}_"):
            return code
    return None


def _resolve_collection(
    legal_domain: str | None,
    source_text: str,
    visual_analysis: dict | None = None,
) -> str:
    """Pick the knowledge collection. An explicit, valid `legal_domain` (a
    collection code like ``F_Tenancy_Real_Estate``) wins; then the collection
    detected by the visual analysis step; otherwise classify from the text.
    """
    matched = _match_collection(legal_domain)
    if matched:
        return matched
    if visual_analysis:
        matched = _match_collection(visual_analysis.get("collection"))
        if matched:
            return matched
    return route_collection(source_text)


def _image_blocks(images: list[bytes], media_type: str) -> list[dict]:
    """Wrap raw page-image bytes as Anthropic vision content blocks."""
    return [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.standard_b64encode(img).decode("utf-8"),
            },
        }
        for img in images
    ]


def _extract_json_object(raw: str) -> dict:
    """Parse a JSON object from a model reply, tolerating ```json fences or
    surrounding prose. Returns {} when nothing parseable is found."""
    if not raw:
        return {}
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return {}


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


_ANALYSIS_PROMPT = """أنت مترجم قانوني معتمد من وزارة العدل الإماراتية.
افحص هذا المستند بصرياً بدقة وأجب بـ JSON فقط، دون أي شرح أو markdown:

{
  "document_type": "نوع المستند بالتفصيل",
  "collection": "A_Banking_Financial أو B_Shipping_Customs_Logistics أو C_Corporate_Commercial أو D_POA_Legal_Instruments أو E_Government_Personal أو F_Tenancy_Real_Estate أو G_Correspondence_Evidence أو H_Medical أو I_Translator_Affairs_Internal",
  "layout_features": {
    "has_tables": true,
    "has_signature": true,
    "has_stamp": true,
    "has_letterhead": true,
    "is_field_value_format": true,
    "total_pages": 0
  },
  "all_fields_detected": ["كل الحقول المرئية في المستند"],
  "parties": ["أسماء الأطراف"],
  "key_values": {"التاريخ": "", "المبلغ": "", "الرقم": ""},
  "layout_description": "وصف دقيق لهيكل وتنسيق المستند",
  "translation_notes": "أي ملاحظات مهمة للمترجم"
}"""


def analyze_document_visually(
    images: list[bytes],
    media_type: str = "image/jpeg",
    timeout: int = 300,
) -> dict:
    """Step 1 of the two-step pipeline: Claude examines the rendered page images
    and returns a structured visual analysis (document type, collection, layout
    features, detected fields/parties/key values, layout description, notes).

    Returns {} on any failure so the downstream translation step can still
    proceed without it - the analysis is enriching context, never a hard gate.
    """
    if not images:
        return {}
    content = _image_blocks(images, media_type)
    content.append({"type": "text", "text": _ANALYSIS_PROMPT})
    try:
        response = _client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=_ANALYSIS_MAX_TOKENS,
            messages=[{"role": "user", "content": content}],
            timeout=timeout,
        )
        raw = "".join(block.text for block in response.content if block.type == "text")
        return _extract_json_object(raw)
    except Exception:  # noqa: BLE001 - analysis is best-effort enrichment
        return {}


def translate_document_images(
    images: list[bytes],
    routing_text: str = "",
    legal_domain: str | None = None,
    target_language: str = "Arabic",
    truncated_note: str = "",
    media_type: str = "image/jpeg",
    visual_analysis: dict | None = None,
    timeout: int = 300,
) -> str:
    """Step 2 of the two-step pipeline: translate a document Claude sees
    *visually*. Send the rendered page images as vision blocks so the model
    preserves the real on-page layout (tables, fields, stamps, signatures)
    instead of working from flattened text, optionally primed with the Step 1
    `visual_analysis` so it already knows the document type, fields and layout.

    `routing_text` is cheap embedded text used only to pick the knowledge
    collection and retrieve reference chunks - it is NOT the content source.
    """
    collection = _resolve_collection(legal_domain, routing_text, visual_analysis)
    layout_chunks, global_chunks = _knowledge_chunks(routing_text, collection)

    content = _image_blocks(images, media_type)

    analysis_context = ""
    if visual_analysis:
        fields = "، ".join(visual_analysis.get("all_fields_detected", []) or [])
        analysis_context = (
            "\n## نتيجة التحليل البصري (الخطوة 1):\n"
            f"نوع المستند: {visual_analysis.get('document_type', '')}\n"
            f"الحقول المكتشفة: {fields}\n"
            f"هيكل المستند: {visual_analysis.get('layout_description', '')}\n"
            f"ملاحظات للمترجم: {visual_analysis.get('translation_notes', '')}\n"
        )

    user_text = (
        f"## Knowledge Collection ({collection}):\n\n"
        f"### Layout Samples:\n{layout_chunks}\n\n"
        f"### Legal Rules:\n{global_chunks}\n"
        f"{analysis_context}\n"
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
