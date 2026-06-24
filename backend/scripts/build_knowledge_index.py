"""Build/refresh the RAG knowledge index from backend/knowledge/.

Run this once after deploying, and again any time files under knowledge/
change. It is NOT run automatically on every app startup, since embedding the
whole knowledge base costs OpenAI API calls and would slow down every cold
start on a free/auto-sleeping Render instance.

Usage (from the backend/ directory, inside the running container or venv):
    python -m scripts.build_knowledge_index
"""
from app.services.knowledge_service import build_index


def main() -> None:
    result = build_index()
    print(f"Indexed {result['chunks_indexed']} chunks.")


if __name__ == "__main__":
    main()
