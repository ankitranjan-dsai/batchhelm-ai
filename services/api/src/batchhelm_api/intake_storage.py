from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from batchhelm_api.intake_models import IntakeArtifact, IntakeArtifactRole

NOTICE_TYPES = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
INVENTORY_TYPES = {"text/csv": ".csv"}
SHELF_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
ROLE_LIMITS = {
    IntakeArtifactRole.recall_notice: 12 * 1024 * 1024,
    IntakeArtifactRole.inventory_csv: 4 * 1024 * 1024,
    IntakeArtifactRole.shelf_photo: 8 * 1024 * 1024,
}
PACKET_LIMIT = 24 * 1024 * 1024
CHUNK_SIZE = 64 * 1024


class IntakeUploadInvalid(ValueError):
    pass


class IntakePacketTooLarge(IntakeUploadInvalid):
    pass


@dataclass(frozen=True)
class StagedIntakePacket:
    intake_id: str
    staging_dir: Path
    final_dir: Path
    packet_fingerprint: str
    artifacts: tuple[IntakeArtifact, ...]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extension(role: IntakeArtifactRole, media_type: str) -> str:
    allowed = {
        IntakeArtifactRole.recall_notice: NOTICE_TYPES,
        IntakeArtifactRole.inventory_csv: INVENTORY_TYPES,
        IntakeArtifactRole.shelf_photo: SHELF_TYPES,
    }[role]
    try:
        return allowed[media_type]
    except KeyError as exc:
        raise IntakeUploadInvalid(
            f"Unsupported media type for {role.value}."
        ) from exc


def _validate_signature(media_type: str, first_bytes: bytes) -> None:
    signatures = {
        "application/pdf": b"%PDF-",
        "image/jpeg": b"\xff\xd8\xff",
        "image/png": b"\x89PNG\r\n\x1a\n",
        "image/webp": b"RIFF",
    }
    expected = signatures.get(media_type)
    if expected is not None and not first_bytes.startswith(expected):
        raise IntakeUploadInvalid(
            "Uploaded file signature does not match its media type."
        )
    if media_type == "image/webp" and first_bytes[8:12] != b"WEBP":
        raise IntakeUploadInvalid(
            "Uploaded file signature does not match its media type."
        )


def _original_filename(filename: str) -> str:
    return Path(filename.replace("\\", "/")).name


def stage_intake_packet(
    *,
    root: Path,
    intake_id: str,
    files: dict[IntakeArtifactRole, tuple[str, str, BinaryIO]],
    packet_limit: int = PACKET_LIMIT,
) -> StagedIntakePacket:
    required = {
        IntakeArtifactRole.recall_notice,
        IntakeArtifactRole.inventory_csv,
    }
    if not required.issubset(files):
        raise IntakeUploadInvalid("Recall notice and inventory CSV are required.")

    staging_dir = root / ".staging" / uuid4().hex
    final_dir = root / "intakes" / intake_id
    staging_dir.mkdir(parents=True, exist_ok=False)
    artifacts: list[IntakeArtifact] = []
    total = 0

    try:
        for role in sorted(files, key=lambda value: value.value):
            original_name, media_type, stream = files[role]
            extension = _extension(role, media_type)
            artifact_id = uuid4().hex
            stored_filename = f"{artifact_id}{extension}"
            target = staging_dir / stored_filename
            digest = hashlib.sha256()
            size = 0
            first = b""

            with target.open("wb") as output:
                while chunk := stream.read(CHUNK_SIZE):
                    if not first:
                        first = chunk[:16]
                    size += len(chunk)
                    total += len(chunk)
                    if size > ROLE_LIMITS[role] or total > packet_limit:
                        raise IntakePacketTooLarge(
                            "Uploaded intake packet is too large."
                        )
                    digest.update(chunk)
                    output.write(chunk)

            if size == 0:
                raise IntakeUploadInvalid("Uploaded file was empty.")
            _validate_signature(media_type, first)
            if media_type in {"text/plain", "text/csv"}:
                text_content = target.read_bytes()
                text_content.decode("utf-8-sig")
                if b"\x00" in text_content:
                    raise IntakeUploadInvalid(
                        "Text uploads cannot contain NUL bytes."
                    )

            artifacts.append(
                IntakeArtifact(
                    id=artifact_id,
                    intake_id=intake_id,
                    role=role,
                    original_filename=_original_filename(original_name),
                    stored_filename=stored_filename,
                    media_type=media_type,
                    size_bytes=size,
                    sha256=digest.hexdigest(),
                    relative_path=str(
                        Path("intakes") / intake_id / stored_filename
                    ),
                    created_at=_now(),
                )
            )

        fingerprint_payload = [
            {"role": item.role.value, "sha256": item.sha256}
            for item in sorted(artifacts, key=lambda item: item.role.value)
        ]
        packet_fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return StagedIntakePacket(
            intake_id=intake_id,
            staging_dir=staging_dir,
            final_dir=final_dir,
            packet_fingerprint=packet_fingerprint,
            artifacts=tuple(artifacts),
        )
    except (UnicodeDecodeError, OSError) as exc:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise IntakeUploadInvalid(
            "Uploaded file could not be validated."
        ) from exc
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise


def finalize_staged_packet(packet: StagedIntakePacket) -> None:
    packet.final_dir.parent.mkdir(parents=True, exist_ok=True)
    if packet.final_dir.exists():
        raise IntakeUploadInvalid("Intake artifact destination already exists.")
    os.replace(packet.staging_dir, packet.final_dir)


def discard_packet(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def remove_orphaned_intake_directories(
    root: Path,
    known_intake_ids: set[str],
) -> None:
    intake_root = root / "intakes"
    if not intake_root.is_dir():
        return

    for child in intake_root.iterdir():
        if (
            child.name not in known_intake_ids
            and re.fullmatch(r"[0-9a-f]{32}", child.name)
            and not child.is_symlink()
            and child.is_dir()
        ):
            shutil.rmtree(child)
