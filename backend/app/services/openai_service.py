from openai import OpenAI

from app.core.config import get_settings

settings = get_settings()

_client = OpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """\
You are a professional legal translator working for Moajam Almaani, a legal translation \
agency. Translate the legal document the user provides from {source_language} into \
{target_language}, preserving legal meaning, register, and formatting precisely.

You have access to a legal terminology and precedent search tool covering the firm's \
reference collections. Use it whenever a term, clause type, or phrasing has a specialized \
legal equivalent, to keep terminology consistent with prior translations.

Rules:
- Preserve numbering, clause structure, and paragraph breaks.
- Use formal legal terminology appropriate for {target_language} legal documents.
- Do not omit, summarize, or add content. Translate completely and literally where legal \
  meaning requires it, and idiomatically where natural language requires it.
- If a term has no direct equivalent, keep the original term in parentheses after your \
  translation.
- Output ONLY the translated document text. Do not add commentary, notes, or explanations \
  before or after the translation.
"""


def translate_text(
    text: str,
    source_language: str = "auto-detect",
    target_language: str = "Arabic",
    legal_domain: str | None = None,
) -> str:
    """Send extracted document text to OpenAI and return the translated text.

    Uses the file_search tool against the firm's legal vector stores (9 collections)
    so the model can ground terminology in prior translations and reference material.
    """
    system = SYSTEM_PROMPT.format(source_language=source_language, target_language=target_language)
    if legal_domain:
        system += f"\nThis document belongs to the legal domain: {legal_domain}."

    tools = []
    vector_store_ids = settings.openai_vector_store_id_list
    if vector_store_ids:
        tools.append({"type": "file_search", "vector_store_ids": vector_store_ids})

    response = _client.responses.create(
        model=settings.OPENAI_MODEL,
        instructions=system,
        input=text,
        tools=tools or None,
        max_output_tokens=settings.OPENAI_MAX_OUTPUT_TOKENS,
    )

    return response.output_text
