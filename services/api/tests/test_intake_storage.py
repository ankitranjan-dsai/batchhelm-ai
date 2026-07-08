from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from batchhelm_api.intake_models import IntakeArtifactRole
from batchhelm_api.intake_storage import (
    IntakePacketTooLarge,
    IntakeUploadInvalid,
    discard_packet,
    finalize_staged_packet,
    remove_orphaned_intake_directories,
    stage_intake_packet)

PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 20
PDF = b"%PDF-1.4\n" + b"x" * 20
CSV = b"store,product,lot,on_hand\nStore A,Spinach,L1,2\n"


def packet_files(
    notice: bytes = PDF,
    notice_media_type: str = "application/pdf") -> dict[IntakeArtifactRole, tuple[str, str, BytesIO]]:
    return {
        IntakeArtifactRole.recall_notice: (
            "notice",
            notice_media_type,
            BytesIO(notice)),
        IntakeArtifactRole.inventory_csv: (
            "inventory.csv",
            "text/csv",
            BytesIO(CSV))}


def test_stages_valid_packet_with_sha256_and_generated_names(tmp_path: Path) -> None:
    files = packet_files()
    files[IntakeArtifactRole.shelf_photo] = (
        "shelf.png",
        "image/png",
        BytesIO(PNG))

    packet = stage_intake_packet(
        root=tmp_path,
        intake_id="intake-1",
        files=files)

    assert len(packet.packet_fingerprint) == 64
    assert len(packet.artifacts) == 3
    assert all(
        len(item.sha256) == 64 and "/" not in item.stored_filename
        for item in packet.artifacts
    )
    assert packet.staging_dir.is_dir()
    assert packet.final_dir == tmp_path / "intakes" / "intake-1"


def test_rejects_spoofed_image_signature_and_cleans_staging(tmp_path: Path) -> None:
    with pytest.raises(IntakeUploadInvalid, match="signature"):
        stage_intake_packet(
            root=tmp_path,
            intake_id="intake-1",
            files={
                IntakeArtifactRole.recall_notice: (
                    "notice.png",
                    "image/png",
                    BytesIO(b"not-a-png")),
                IntakeArtifactRole.inventory_csv: (
                    "inventory.csv",
                    "text/csv",
                    BytesIO(CSV))})

    staging_root = tmp_path / ".staging"
    assert not staging_root.exists() or list(staging_root.iterdir()) == []


def test_rejects_total_packet_over_limit(tmp_path: Path) -> None:
    with pytest.raises(IntakePacketTooLarge):
        stage_intake_packet(
            root=tmp_path,
            intake_id="intake-1",
            packet_limit=30,
            files=packet_files())


@pytest.mark.parametrize(
    ("media_type", "content"),
    [
        ("text/plain", b"Recall notice"),
        ("application/pdf", PDF),
        ("image/jpeg", b"\xff\xd8\xff" + b"x" * 20),
        ("image/png", PNG),
        ("image/webp", b"RIFF\x10\x00\x00\x00WEBP" + b"x" * 20),
    ])
def test_notice_media_types_are_accepted(
    tmp_path: Path,
    media_type: str,
    content: bytes) -> None:
    packet = stage_intake_packet(
        root=tmp_path,
        intake_id="intake-1",
        files=packet_files(content, media_type))

    notice = next(
        item
        for item in packet.artifacts
        if item.role == IntakeArtifactRole.recall_notice
    )
    assert notice.size_bytes == len(content)


def test_original_path_components_are_removed(tmp_path: Path) -> None:
    packet = stage_intake_packet(
        root=tmp_path,
        intake_id="intake-1",
        files={
            IntakeArtifactRole.recall_notice: (
                r"..\..\notice.pdf",
                "application/pdf",
                BytesIO(PDF)),
            IntakeArtifactRole.inventory_csv: (
                "../inventory.csv",
                "text/csv",
                BytesIO(CSV))})

    assert {item.original_filename for item in packet.artifacts} == {
        "notice.pdf",
        "inventory.csv"}


def test_finalizes_packet_atomically_and_discard_removes_staging(
    tmp_path: Path) -> None:
    packet = stage_intake_packet(
        root=tmp_path,
        intake_id="intake-1",
        files=packet_files())
    staged_names = {path.name for path in packet.staging_dir.iterdir()}

    finalize_staged_packet(packet)

    assert not packet.staging_dir.exists()
    assert {path.name for path in packet.final_dir.iterdir()} == staged_names

    another = stage_intake_packet(
        root=tmp_path,
        intake_id="intake-2",
        files=packet_files())
    discard_packet(another.staging_dir)
    assert not another.staging_dir.exists()


def test_removes_only_generated_orphan_directories(tmp_path: Path) -> None:
    intake_root = tmp_path / "intakes"
    known = intake_root / ("a" * 32)
    orphan = intake_root / ("b" * 32)
    unrelated = intake_root / "manual-files"
    known.mkdir(parents=True)
    orphan.mkdir()
    unrelated.mkdir()

    remove_orphaned_intake_directories(tmp_path, {known.name})

    assert known.is_dir()
    assert not orphan.exists()
    assert unrelated.is_dir()
