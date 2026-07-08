from pathlib import Path

import pytest

from batchhelm_api.storage import UploadValidationError, save_image_upload


def test_save_image_upload_writes_safe_generated_filename(tmp_path: Path) -> None:
    metadata = save_image_upload(
        upload_dir=tmp_path,
        filename="../../shelf.png",
        media_type="image/png",
        content=b"png-bytes")

    assert metadata.original_filename == "shelf.png"
    assert metadata.stored_filename.endswith(".png")
    assert ".." not in metadata.stored_filename
    assert metadata.path == metadata.stored_filename
    assert (tmp_path / metadata.path).read_bytes() == b"png-bytes"


def test_save_image_upload_rejects_unsupported_media_type(tmp_path: Path) -> None:
    with pytest.raises(UploadValidationError):
        save_image_upload(
            upload_dir=tmp_path,
            filename="note.txt",
            media_type="text/plain",
            content=b"not-an-image")


def test_save_image_upload_rejects_empty_file(tmp_path: Path) -> None:
    with pytest.raises(UploadValidationError):
        save_image_upload(
            upload_dir=tmp_path,
            filename="shelf.png",
            media_type="image/png",
            content=b"")


def test_save_image_upload_rejects_files_over_limit(tmp_path: Path) -> None:
    with pytest.raises(UploadValidationError):
        save_image_upload(
            upload_dir=tmp_path,
            filename="huge.webp",
            media_type="image/webp",
            content=b"x" * (8 * 1024 * 1024 + 1))
