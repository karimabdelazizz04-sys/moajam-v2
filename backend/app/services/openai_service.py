from openai import OpenAI

from app.core.config import get_settings
from app.services.translation_prompt import get_translation_prompt

settings = get_settings()

_client = OpenAI(api_key=settings.OPENAI_API_KEY)


def translate_text(
    text: str,
    source_language: str = "auto-detect",
    target_language: str = "Arabic",
    legal_domain: str | None = None,
) -> str:
    """Send extracted document text to OpenAI and return the translated text.

    Uses the file_search tool against the firm's legal vector stores (9 collections)
    so the model can ground terminology/layout in the matched knowledge collection.
    """
    task_context = f"Source language: {source_language}\nTarget language: {target_language}"
    if legal_domain:
        task_context += f"\nDeclared document/legal domain hint: {legal_domain}"

    system = get_translation_prompt(task_context)

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
