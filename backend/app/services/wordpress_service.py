import base64

import requests

from app.core.config import get_settings

settings = get_settings()


class WordPressMediaError(Exception):
    pass


def upload_source_to_wordpress(file_bytes: bytes, filename: str, content_type: str) -> dict:
    """Push a caller-provided *source* file straight to the WordPress Media
    Library via the core `/wp-json/wp/v2/media` route, authenticated with an
    Application Password (Basic Auth).

    The credentials live only in backend settings - the browser uploads the
    file to this backend, which then relays it to WordPress, so the WordPress
    password is never exposed client-side.

    Returns {"id": <attachment id>, "url": <permanent WordPress media URL>}.
    """
    if not settings.WP_BASE_URL:
        raise WordPressMediaError("WP_BASE_URL is not configured")
    if not settings.WP_USER or not settings.WP_APP_PASSWORD:
        raise WordPressMediaError("WP_USER / WP_APP_PASSWORD are not configured")

    url = settings.WP_BASE_URL.rstrip("/") + "/wp-json/wp/v2/media"
    # Diagnostics only - never log the secret itself, only its length so we can
    # tell "empty / quoted / truncated App Password" apart from a real value.
    print(f"[WP source upload] Upload to: {url}", flush=True)
    print(f"[WP source upload] Auth user: {settings.WP_USER}", flush=True)
    print(
        "[WP source upload] Password length: "
        f"{len(settings.WP_APP_PASSWORD) if settings.WP_APP_PASSWORD else 'None'}",
        flush=True,
    )
    token = base64.b64encode(
        f"{settings.WP_USER}:{settings.WP_APP_PASSWORD}".encode()
    ).decode()
    response = requests.post(
        url,
        headers={"Authorization": f"Basic {token}"},
        files={"file": (filename, file_bytes, content_type)},
        timeout=120,
    )
    print(f"[WP source upload] Response: {response.status_code}", flush=True)
    if response.status_code >= 400:
        raise WordPressMediaError(
            f"WordPress source upload failed ({response.status_code}): {response.text}"
        )

    data = response.json()
    return {"id": data.get("id"), "url": data.get("source_url")}


def download_source_file(url: str) -> bytes:
    """Fetch a source file the translator already saved to the WordPress Media
    Library. Render never stores this file itself - it's downloaded into
    memory for the duration of one translation job and discarded.
    """
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.content


def upload_media_to_wordpress(
    file_bytes: bytes, filename: str, content_type: str, timeout: int = 300
) -> dict:
    """Push a generated file (translated DOCX, invoice PDF) to the WordPress
    Media Library via the plugin's `/wp-json/moajam/v1/media` route, which is
    protected by the same shared X-API-Key used everywhere else.

    Returns {"id": <attachment id>, "url": <permanent WordPress media URL>}.
    """
    if not settings.WP_BASE_URL:
        raise WordPressMediaError("WP_BASE_URL is not configured")

    url = settings.WP_BASE_URL.rstrip("/") + "/wp-json/moajam/v1/media"
    # NOTE: this output-file path uses the plugin route + X-API-Key, NOT the
    # core route + Basic Auth / WP_APP_PASSWORD that the source upload uses.
    print(f"[WP media upload] Upload to: {url}", flush=True)
    print(f"[WP media upload] X-API-Key set: {bool(settings.API_KEY)}", flush=True)
    response = requests.post(
        url,
        headers={"X-API-Key": settings.API_KEY},
        files={"file": (filename, file_bytes, content_type)},
        timeout=timeout,
    )
    print(f"[WP media upload] Response: {response.status_code}", flush=True)
    if response.status_code >= 400:
        raise WordPressMediaError(f"WordPress media upload failed ({response.status_code}): {response.text}")

    return response.json()
