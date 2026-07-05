"""Storage and validation for Intelligence Brief featured images.

Isolates all file IO for featured images: validating an upload, writing it under
the upload root with a safe generated name, and deleting stored files. The
database side (updating ``featured_image_url`` / ``featured_image_path``) lives
in ``intelligence_brief_service``.

Files are served publicly at ``/uploads/intelligence-briefs/<filename>`` via the
``/uploads`` StaticFiles mount in ``app.main``.
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import settings

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

# Only raster formats we can serve safely. SVG is excluded on purpose (it can
# carry script); GIF and everything else are simply not on the allowlist. Each
# extension is pinned to the exact content type the client must send, so a file
# cannot claim one format via its name and another via its content type.
_EXTENSION_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
ALLOWED_EXTENSIONS = frozenset(_EXTENSION_CONTENT_TYPES)
ALLOWED_CONTENT_TYPES = frozenset(_EXTENSION_CONTENT_TYPES.values())

_IMAGE_SUBDIR = "intelligence-briefs"
_URL_PREFIX = "/uploads"


class ImageValidationError(Exception):
    """Raised when an uploaded featured image fails validation."""


def _image_dir() -> Path:
    """Directory that holds featured images, resolved from current settings."""
    return Path(settings.upload_dir) / _IMAGE_SUBDIR


async def read_validated_upload(upload: UploadFile | None) -> tuple[bytes, str]:
    """Validate an uploaded image and return ``(content, extension)``.

    Enforces the content-type allowlist, the extension allowlist, that the two
    agree, a non-empty body and the 5 MB size cap. At most ``MAX_UPLOAD_BYTES + 1``
    bytes are read so an oversized upload cannot exhaust memory. The original
    filename is only inspected for its extension and is never used for storage.
    """
    if upload is None or not upload.filename:
        raise ImageValidationError("no file provided")

    content_type = (upload.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ImageValidationError(
            f"unsupported content type: {content_type or 'unknown'}"
        )

    extension = os.path.splitext(upload.filename)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ImageValidationError(
            f"unsupported file extension: {extension or 'none'}"
        )

    if _EXTENSION_CONTENT_TYPES[extension] != content_type:
        raise ImageValidationError(
            f"file extension {extension} does not match content type {content_type}"
        )

    content = await upload.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise ImageValidationError("file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ImageValidationError("file exceeds the 5 MB size limit")

    return content, extension


def save_image(content: bytes, extension: str) -> tuple[str, str]:
    """Write image bytes under the upload root and return ``(path, url)``.

    The filename is a random UUID plus the validated extension, so the untrusted
    original name is never used and path traversal is impossible — the file can
    only ever land inside the configured upload directory. ``path`` is the local
    filesystem path (used later for cleanup); ``url`` is the public URL the
    frontend renders.
    """
    directory = _image_dir()
    directory.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{extension}"
    path = directory / filename
    path.write_bytes(content)

    stored_path = str(path)
    public_url = f"{_URL_PREFIX}/{_IMAGE_SUBDIR}/{filename}"
    return stored_path, public_url


def delete_image(stored_path: str | None) -> None:
    """Best-effort deletion of a stored image. Never raises.

    As a safety guard the resolved target must live inside the featured-image
    directory — a path pointing anywhere else (a stale/absolute value, an attempt
    to escape the upload root) is logged and left untouched. Used for cleanup
    when replacing or removing an image; a failure here must not fail the
    request, so it is logged and swallowed.
    """
    if not stored_path:
        return
    try:
        image_dir = _image_dir().resolve()
        target = Path(stored_path).resolve()
    except OSError as exc:
        logger.warning("could not resolve featured image %s: %s", stored_path, exc)
        return

    if not target.is_relative_to(image_dir):
        logger.warning(
            "refusing to delete featured image outside upload dir: %s", stored_path
        )
        return

    try:
        target.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("could not delete featured image %s: %s", stored_path, exc)
