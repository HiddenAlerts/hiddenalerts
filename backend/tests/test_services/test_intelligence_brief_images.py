"""Tests for featured-image storage and the brief image service actions."""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from starlette.datastructures import Headers, UploadFile

from app.config import settings
from app.schemas.intelligence_brief import IntelligenceBriefCreate
from app.services import intelligence_brief_service as service
from app.services.intelligence_brief_images import (
    ImageValidationError,
    MAX_UPLOAD_BYTES,
    delete_image,
)


def _upload(content: bytes, filename: str, content_type: str) -> UploadFile:
    headers = Headers(raw=[(b"content-type", content_type.encode())])
    return UploadFile(file=io.BytesIO(content), filename=filename, headers=headers)


async def _make_brief(db_session):
    return await service.create_brief(
        db_session, IntelligenceBriefCreate(title="Image brief"), user_id=None
    )


@pytest.fixture
def upload_root(monkeypatch, tmp_path):
    """Redirect the upload directory to a throwaway tmp path for each test."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize(
    "filename, content_type, expected_ext",
    [
        ("photo.jpg", "image/jpeg", ".jpg"),
        ("photo.jpeg", "image/jpeg", ".jpeg"),
        ("photo.png", "image/png", ".png"),
        ("photo.webp", "image/webp", ".webp"),
    ],
)
@pytest.mark.asyncio
async def test_valid_uploads_store_file_and_update_fields(
    db_session, upload_root, filename, content_type, expected_ext
):
    brief = await _make_brief(db_session)
    result = await service.set_featured_image(
        db_session, brief.id, _upload(b"binary-image-bytes", filename, content_type),
        user_id=None,
    )
    assert result.featured_image_url.startswith("/uploads/intelligence-briefs/")
    assert result.featured_image_url.endswith(expected_ext)
    # The stored file lives under the configured upload root and exists on disk.
    assert result.featured_image_path.startswith(str(upload_root))
    assert Path(result.featured_image_path).is_file()


@pytest.mark.asyncio
async def test_original_filename_not_used_for_storage(db_session, upload_root):
    brief = await _make_brief(db_session)
    result = await service.set_featured_image(
        db_session, brief.id, _upload(b"data", "../../evil.png", "image/png"),
        user_id=None,
    )
    stored_name = Path(result.featured_image_path).name
    assert "evil" not in stored_name
    assert ".." not in result.featured_image_path
    # File is confined to the upload root.
    assert Path(result.featured_image_path).resolve().parent == (
        upload_root / "intelligence-briefs"
    ).resolve()


@pytest.mark.asyncio
async def test_unsupported_extension_rejected(db_session, upload_root):
    brief = await _make_brief(db_session)
    with pytest.raises(ImageValidationError):
        await service.set_featured_image(
            db_session, brief.id, _upload(b"data", "x.gif", "image/jpeg"), user_id=None
        )


@pytest.mark.asyncio
async def test_unsupported_content_type_rejected(db_session, upload_root):
    brief = await _make_brief(db_session)
    with pytest.raises(ImageValidationError):
        await service.set_featured_image(
            db_session, brief.id, _upload(b"data", "x.jpg", "image/gif"), user_id=None
        )


@pytest.mark.parametrize(
    "filename, content_type",
    [
        ("photo.jpg", "image/png"),
        ("photo.jpeg", "image/webp"),
        ("photo.png", "image/jpeg"),
        ("photo.webp", "image/jpeg"),
    ],
)
@pytest.mark.asyncio
async def test_extension_content_type_mismatch_rejected(
    db_session, upload_root, filename, content_type
):
    brief = await _make_brief(db_session)
    with pytest.raises(ImageValidationError):
        await service.set_featured_image(
            db_session, brief.id, _upload(b"data", filename, content_type), user_id=None
        )


@pytest.mark.asyncio
async def test_svg_rejected(db_session, upload_root):
    brief = await _make_brief(db_session)
    with pytest.raises(ImageValidationError):
        await service.set_featured_image(
            db_session, brief.id, _upload(b"<svg/>", "x.svg", "image/svg+xml"),
            user_id=None,
        )


@pytest.mark.asyncio
async def test_oversized_file_rejected(db_session, upload_root):
    brief = await _make_brief(db_session)
    too_big = b"\x00" * (MAX_UPLOAD_BYTES + 1)
    with pytest.raises(ImageValidationError):
        await service.set_featured_image(
            db_session, brief.id, _upload(too_big, "big.jpg", "image/jpeg"), user_id=None
        )


@pytest.mark.asyncio
async def test_empty_file_rejected(db_session, upload_root):
    brief = await _make_brief(db_session)
    with pytest.raises(ImageValidationError):
        await service.set_featured_image(
            db_session, brief.id, _upload(b"", "empty.jpg", "image/jpeg"), user_id=None
        )


@pytest.mark.asyncio
async def test_replace_updates_fields_and_removes_old_file(db_session, upload_root):
    brief = await _make_brief(db_session)
    first = await service.set_featured_image(
        db_session, brief.id, _upload(b"one", "a.jpg", "image/jpeg"), user_id=None
    )
    old_path = first.featured_image_path
    assert Path(old_path).is_file()

    second = await service.set_featured_image(
        db_session, brief.id, _upload(b"two", "b.png", "image/png"), user_id=None
    )
    assert second.featured_image_path != old_path
    assert second.featured_image_url.endswith(".png")
    assert Path(second.featured_image_path).is_file()
    # The previous file is cleaned up after the replacement is persisted.
    assert not Path(old_path).exists()


@pytest.mark.asyncio
async def test_remove_clears_fields_and_deletes_file(db_session, upload_root):
    brief = await _make_brief(db_session)
    stored = await service.set_featured_image(
        db_session, brief.id, _upload(b"data", "a.jpg", "image/jpeg"), user_id=None
    )
    path = stored.featured_image_path

    removed = await service.remove_featured_image(db_session, brief.id, user_id=None)
    assert removed.featured_image_url is None
    assert removed.featured_image_path is None
    assert not Path(path).exists()


@pytest.mark.asyncio
async def test_remove_is_idempotent_without_image(db_session, upload_root):
    brief = await _make_brief(db_session)
    removed = await service.remove_featured_image(db_session, brief.id, user_id=None)
    assert removed.featured_image_url is None
    assert removed.featured_image_path is None


@pytest.mark.asyncio
async def test_set_image_missing_brief_raises(db_session, upload_root):
    with pytest.raises(service.BriefNotFoundError):
        await service.set_featured_image(
            db_session, 999999, _upload(b"d", "a.jpg", "image/jpeg"), user_id=None
        )


@pytest.mark.asyncio
async def test_remove_image_missing_brief_raises(db_session, upload_root):
    with pytest.raises(service.BriefNotFoundError):
        await service.remove_featured_image(db_session, 999999, user_id=None)


# ---------------------------------------------------------------------------
# delete_image path safety
# ---------------------------------------------------------------------------


def test_delete_image_removes_file_inside_dir(upload_root):
    image_dir = upload_root / "intelligence-briefs"
    image_dir.mkdir(parents=True)
    target = image_dir / "keep.jpg"
    target.write_bytes(b"data")

    delete_image(str(target))
    assert not target.exists()


def test_delete_image_refuses_path_outside_dir(upload_root):
    # A path that resolves outside the featured-image directory must be left alone.
    outside = upload_root / "outside.jpg"
    outside.write_bytes(b"data")

    delete_image(str(outside))
    assert outside.exists()


def test_delete_image_refuses_traversal_escape(upload_root):
    image_dir = upload_root / "intelligence-briefs"
    image_dir.mkdir(parents=True)
    outside = upload_root / "secret.jpg"
    outside.write_bytes(b"data")

    delete_image(str(image_dir / ".." / "secret.jpg"))
    assert outside.exists()


def test_delete_image_none_is_noop():
    delete_image(None)
