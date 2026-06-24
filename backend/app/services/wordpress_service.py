import requests

from app.core.config import get_settings

settings = get_settings()


class WordPressMediaError(Exception):
    pass


def download_source_file(url: str) -> bytes:
    """Fetch a source file the translator already saved to the WordPress Media
    Library. Render never stores this file itself - it's downloaded into
    memory for the duration of one translation job and discarded.
    """
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.content


def upload_media_to_wordpress(file_bytes: bytes, filename: str, content_type: str) -> dict:
    """Push a generated file (translated DOCX, invoice PDF) to the WordPress
    Media Library via the plugin's `/wp-json/moajam/v1/media` route, which is
    protected by the same shared X-API-Key used everywhere else.

    Returns {"id": <attachment id>, "url": <permanent WordPress media URL>}.
    """
    if not settings.WP_BASE_URL:
        raise WordPressMediaError("WP_BASE_URL is not configured")

    url = settings.WP_BASE_URL.rstrip("/") + "/wp-json/moajam/v1/media"
    response = requests.post(
        url,
        headers={"X-API-Key": settings.API_KEY},
        files={"file": (filename, file_bytes, content_type)},
        timeout=60,
    )
    if response.status_code >= 400:
        raise WordPressMediaError(f"WordPress media upload failed ({response.status_code}): {response.text}")

    return response.json()
