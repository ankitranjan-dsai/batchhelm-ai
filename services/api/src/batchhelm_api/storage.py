from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from batchhelm_api.models import UploadMetadata

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


class UploadValidationError(ValueError):
    pass


def validate_image_upload(
    filename: str,
    media_type: str | None,
    content: bytes,
    max_size: int = MAX_UPLOAD_BYTES,
) -> None:
    if media_type not in ALLOWED_IMAGE_TYPES:
        raise UploadValidationError("Only JPEG, PNG, and WebP shelf images are supported.")

    if not content:
        raise UploadValidationError("Uploaded image was empty.")

    if len(content) > max_size:
        raise UploadValidationError("Uploaded image exceeds the 8 MB limit.")

    if not filename.strip():
        raise UploadValidationError("Uploaded image filename is required.")


def save_image_upload(
    upload_dir: Path,
    filename: str,
    media_type: str,
    content: bytes,
) -> UploadMetadata:
    validate_image_upload(filename=filename, media_type=media_type, content=content)
    upload_dir.mkdir(parents=True, exist_ok=True)

    upload_id = uuid4().hex
    extension = ALLOWED_IMAGE_TYPES[media_type]
    stored_filename = f"{upload_id}{extension}"
    destination = upload_dir / stored_filename
    destination.write_bytes(content)

    return UploadMetadata(
        id=upload_id,
        original_filename=Path(filename).name,
        stored_filename=stored_filename,
        media_type=media_type,
        size_bytes=len(content),
        path=stored_filename,
    )
