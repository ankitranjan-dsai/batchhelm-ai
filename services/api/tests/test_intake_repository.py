from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from batchhelm_api.intake_models import (
    IntakeArtifact,
    IntakeArtifactRole,
    IntakeFieldEvidence,
    IntakeStatus,
    RecallCriteriaDraft,
    RecallIncidentDraft)
from batchhelm_api.intake_repository import (
    IntakeIdempotencyConflict,
    IntakeStateConflict,
    IntakeStoreUnavailable,
    IntakeVersionConflict,
    SQLiteIntakeRepository,
    UnavailableIntakeRepository)
from batchhelm_api.models import (
    IncidentStatus,
    InventoryItem,
    OutputSource,
    RecallCriteria,
    RecallIncidentInput,
    Severity)


def make_repository(path: Path) -> SQLiteIntakeRepository:
    repository = SQLiteIntakeRepository(path)
    repository.initialize()
    return repository


def artifacts(intake_id: str) -> list[IntakeArtifact]:
    return [
        IntakeArtifact(
            id=f"{intake_id}-notice",
            intake_id=intake_id,
            role=IntakeArtifactRole.recall_notice,
            original_filename="notice.txt",
            stored_filename="notice.txt",
            media_type="text/plain",
            size_bytes=42,
            sha256="a" * 64,
            relative_path=f"intakes/{intake_id}/notice.txt",
            created_at="2026-07-04T08:00:00+00:00"),
        IntakeArtifact(
            id=f"{intake_id}-inventory",
            intake_id=intake_id,
            role=IntakeArtifactRole.inventory_csv,
            original_filename="inventory.csv",
            stored_filename="inventory.csv",
            media_type="text/csv",
            size_bytes=84,
            sha256="b" * 64,
            relative_path=f"intakes/{intake_id}/inventory.csv",
            created_at="2026-07-04T08:00:00+00:00"),
    ]


def review_draft(product: str = "Spinach") -> RecallIncidentDraft:
    return RecallIncidentDraft(
        criteria=RecallCriteriaDraft(
            product_name=product,
            affected_lots=["L2418"],
            upcs=["008500001010"],
            risk_level=Severity.high,
            reason="Possible contamination",
            source="Central Farms"),
        notice_text="Spinach L2418 UPC 008500001010 contamination",
        inventory=[
            InventoryItem(
                id="inventory-row-2",
                store="Store A",
                sku="SPN10Z",
                product="Spinach",
                lot="L2418",
                upc="008500001010",
                on_hand=6,
                location="Cooler",
                supplier_alias="Central Farms")
        ],
        stores=["Store A"],
        review_required=True)


def evidence(
    intake_id: str,
    *,
    source: OutputSource = OutputSource.deterministic,
    value: str = "Spinach",
    supersedes_id: str | None = None) -> list[IntakeFieldEvidence]:
    return [
        IntakeFieldEvidence(
            id=f"{intake_id}-{source.value}-{value.lower().replace(' ', '-')}",
            intake_id=intake_id,
            field_path="criteria.product_name",
            value=value,
            artifact_id=f"{intake_id}-notice",
            locator="line 1",
            source=source,
            confidence=100 if source == OutputSource.reviewer else 65,
            requires_review=source != OutputSource.reviewer,
            supersedes_id=supersedes_id,
            created_at="2026-07-04T08:05:00+00:00")
    ]


def confirmed_snapshot(incident_id: str = "incident-1") -> RecallIncidentInput:
    return RecallIncidentInput(
        id=incident_id,
        product="Spinach",
        lot_range="L2418",
        status=IncidentStatus.active,
        opened_at="2026-07-04T08:10:00+00:00",
        stores=["Store A"],
        criteria=RecallCriteria(
            product_name="Spinach",
            affected_lots=["L2418"],
            upcs=["008500001010"],
            risk_level=Severity.high,
            reason="Possible contamination",
            source="Central Farms"),
        notice_text="Spinach L2418 UPC 008500001010 contamination",
        inventory=review_draft().inventory)


def reviewable_repository(tmp_path: Path) -> SQLiteIntakeRepository:
    repository = make_repository(tmp_path / "intake.db")
    repository.create_intake(
        intake_id="intake-1",
        request_id="create-1",
        packet_fingerprint="a" * 64,
        provider_mode="demo-fallback",
        artifacts=artifacts("intake-1"))
    repository.claim_extraction("intake-1")
    repository.save_extraction(
        "intake-1",
        draft=review_draft(),
        evidence=evidence("intake-1"))
    return repository


def test_intake_artifacts_and_evidence_survive_restart(tmp_path: Path) -> None:
    path = tmp_path / "intake.db"
    repository = make_repository(path)
    record = repository.create_intake(
        intake_id="intake-1",
        request_id="request-1",
        packet_fingerprint="a" * 64,
        provider_mode="demo-fallback",
        artifacts=artifacts("intake-1"))
    repository.claim_extraction(record.id)
    repository.save_extraction(
        record.id,
        draft=review_draft(),
        evidence=evidence("intake-1"))

    restarted = make_repository(path)
    view = restarted.get_intake(record.id).to_view()

    assert view.status == IntakeStatus.review_required
    assert view.version == 1
    assert view.artifacts[0].original_filename == "notice.txt"
    assert view.evidence[0].field_path == "criteria.product_name"
    assert view.draft is not None
    assert view.draft.inventory[0].on_hand == 6


def test_identical_create_request_reuses_intake(tmp_path: Path) -> None:
    repository = make_repository(tmp_path / "intake.db")
    first = repository.create_intake(
        intake_id="intake-1",
        request_id="request-1",
        packet_fingerprint="a" * 64,
        provider_mode="demo-fallback",
        artifacts=artifacts("intake-1"))
    replay = repository.create_intake(
        intake_id="intake-2",
        request_id="request-1",
        packet_fingerprint="a" * 64,
        provider_mode="demo-fallback",
        artifacts=artifacts("intake-2"))

    assert replay.id == first.id
    assert repository.list_intake_ids() == {"intake-1"}


def test_create_request_cannot_be_reused_for_different_packet(
    tmp_path: Path) -> None:
    repository = make_repository(tmp_path / "intake.db")
    repository.create_intake(
        intake_id="intake-1",
        request_id="request-1",
        packet_fingerprint="a" * 64,
        provider_mode="demo-fallback",
        artifacts=artifacts("intake-1"))

    with pytest.raises(IntakeIdempotencyConflict):
        repository.create_intake(
            intake_id="intake-2",
            request_id="request-1",
            packet_fingerprint="b" * 64,
            provider_mode="demo-fallback",
            artifacts=artifacts("intake-2"))


def test_stale_reviewer_version_is_rejected(tmp_path: Path) -> None:
    repository = reviewable_repository(tmp_path)
    first_evidence_id = repository.get_intake("intake-1").evidence[0].id
    first = repository.update_draft(
        "intake-1",
        request_id="update-1",
        expected_version=1,
        draft=review_draft(product="Baby Spinach"),
        evidence=evidence(
            "intake-1",
            source=OutputSource.reviewer,
            value="Baby Spinach",
            supersedes_id=first_evidence_id))

    assert first.version == 2
    assert len(first.evidence) == 2
    with pytest.raises(IntakeVersionConflict):
        repository.update_draft(
            "intake-1",
            request_id="update-2",
            expected_version=1,
            draft=review_draft(product="Wrong"),
            evidence=evidence(
                "intake-1",
                source=OutputSource.reviewer,
                value="Wrong"))


def test_identical_update_request_is_idempotent(tmp_path: Path) -> None:
    repository = reviewable_repository(tmp_path)
    reviewer_evidence = evidence(
        "intake-1",
        source=OutputSource.reviewer,
        value="Baby Spinach")
    first = repository.update_draft(
        "intake-1",
        request_id="update-1",
        expected_version=1,
        draft=review_draft(product="Baby Spinach"),
        evidence=reviewer_evidence)
    replay = repository.update_draft(
        "intake-1",
        request_id="update-1",
        expected_version=1,
        draft=review_draft(product="Baby Spinach"),
        evidence=reviewer_evidence)

    assert replay.version == first.version
    assert len(replay.evidence) == 2


def test_confirmation_snapshot_is_immutable(tmp_path: Path) -> None:
    repository = reviewable_repository(tmp_path)
    snapshot = confirmed_snapshot()
    ready = repository.confirm_intake(
        "intake-1",
        request_id="confirm-1",
        expected_version=1,
        snapshot=snapshot)

    assert ready.status == IntakeStatus.ready
    assert repository.resolve_incident(snapshot.id) == snapshot
    with pytest.raises(IntakeStateConflict):
        repository.update_draft(
            "intake-1",
            request_id="update-late",
            expected_version=ready.version,
            draft=review_draft(),
            evidence=[])


def test_linked_run_and_artifact_are_resolvable_after_restart(
    tmp_path: Path) -> None:
    path = tmp_path / "intake.db"
    repository = reviewable_repository(tmp_path)
    ready = repository.confirm_intake(
        "intake-1",
        request_id="confirm-1",
        expected_version=1,
        snapshot=confirmed_snapshot())
    linked = repository.link_run(
        "intake-1",
        request_id="run-1",
        run_id="orchestration-1")

    restarted = make_repository(path)
    assert linked.version == ready.version + 1
    assert linked.status == IntakeStatus.run_started
    assert restarted.get_intake("intake-1").run_id == "orchestration-1"
    artifact = restarted.find_artifact(
        "intake-1",
        IntakeArtifactRole.recall_notice)
    assert artifact is not None
    assert artifact.original_filename == "notice.txt"


def test_recoverable_query_only_returns_unfinished_extraction(
    tmp_path: Path) -> None:
    repository = make_repository(tmp_path / "intake.db")
    for intake_id in ("intake-1", "intake-2"):
        repository.create_intake(
            intake_id=intake_id,
            request_id=f"create-{intake_id}",
            packet_fingerprint=intake_id[-1] * 64,
            provider_mode="demo-fallback",
            artifacts=artifacts(intake_id))
    repository.claim_extraction("intake-2")

    assert {
        record.status for record in repository.list_recoverable()
    } == {IntakeStatus.uploaded, IntakeStatus.extracting}


def test_corrupt_persisted_json_becomes_store_unavailable(
    tmp_path: Path) -> None:
    path = tmp_path / "intake.db"
    repository = reviewable_repository(tmp_path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE intakes SET draft_json = 'not-json' WHERE id = 'intake-1'"
        )

    with pytest.raises(IntakeStoreUnavailable):
        repository.get_intake("intake-1")


def test_unavailable_repository_degrades_predictably() -> None:
    repository = UnavailableIntakeRepository(
        IntakeStoreUnavailable("initialization failed")
    )

    repository.initialize()
    assert repository.list_recoverable() == []
    with pytest.raises(
        IntakeStoreUnavailable,
        match="Intake storage is unavailable"):
        repository.get_intake("intake-1")
