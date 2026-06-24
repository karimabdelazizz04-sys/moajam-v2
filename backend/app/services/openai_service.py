from openai import OpenAI

from app.core.config import get_settings
from app.services.knowledge_service import retrieve_context, route_collection
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

    Runs a RAG pass first: classify the document into one of the 9 knowledge
    collections, retrieve the closest-matching sample(s) from
    backend/knowledge/, and feed that as grounding context alongside the
    master system prompt. Also uses the file_search tool against the firm's
    OpenAI vector stores for additional terminology/layout grounding.
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
