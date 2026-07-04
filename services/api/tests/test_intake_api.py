from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from batchhelm_api.app import create_app
from batchhelm_api.intake_repository import IntakeStoreUnavailable
from tests.conftest import make_settings

NOTICE = (
    b"Spinach 10 oz\n"
    b"Central Farms supplier alert\n"
    b"Affected lot L2418\n"
    b"UPC 008500001010. Possible contamination risk.\n"
)
CSV = (
    b"store,sku,product,lot,upc,on_hand,location,supplier\n"
    b"Store A,SPN10Z,Spinach 10 oz,L2418,008500001010,6,"
    b"Cooler,Central Farms\n"
)
SAMPLE_DATA = Path(__file__).resolve().parents[3] / "sample-data"


class FailingIntakeRepository:
    def initialize(self) -> None:
        raise IntakeStoreUnavailable(
            "database unavailable at /private/secret/intake.db"
        )


def make_client(
    tmp_path: Path,
    *,
    intake_repository: object | None = None,
) -> TestClient:
    settings = make_settings(
        INTAKE_DATABASE_PATH=tmp_path / "intake.db",
        UPLOAD_DIR=tmp_path / "uploads",
    )
    return TestClient(
        create_app(
            settings=settings,
            intake_repository=intake_repository,  # type: ignore[arg-type]
        )
    )


def create_intake(
    client: TestClient,
    request_id: str = "0d05fc09-d47c-43aa-9f01-b021b26f0ac8",
):
    return client.post(
        "/api/intakes",
        data={"request_id": request_id},
        files={
            "notice": ("notice.txt", NOTICE, "text/plain"),
            "inventory": ("inventory.csv", CSV, "text/csv"),
        },
    )


def upload_sample_packet(
    client: TestClient,
    *,
    inventory_name: str = "inventory-spinach.csv",
    request_id: str = "9d05fc09-d47c-43aa-9f01-b021b26f0ac8",
):
    return client.post(
        "/api/intakes",
        data={"request_id": request_id},
        files={
            "notice": (
                "recall-notice-spinach.pdf",
                (SAMPLE_DATA / "recall-notice-spinach.pdf").read_bytes(),
                "application/pdf",
            ),
            "inventory": (
                inventory_name,
                (SAMPLE_DATA / inventory_name).read_bytes(),
                "text/csv",
            ),
            "shelf_evidence": (
                "store-b-cooler-spinach.png",
                (SAMPLE_DATA / "store-b-cooler-spinach.png").read_bytes(),
                "image/png",
            ),
        },
    )


def wait_for_intake(
    client: TestClient,
    status_url: str,
) -> dict[str, object]:
    for _attempt in range(100):
        response = client.get(status_url)
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] not in {"uploaded", "extracting"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("Intake did not finish processing.")


def wait_for_run(
    client: TestClient,
    result_url: str,
) -> dict[str, object]:
    for _attempt in range(100):
        response = client.get(result_url)
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("Orchestration run did not finish.")


def test_create_intake_returns_202_and_reviewable_status(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        response = create_intake(client)

        assert response.status_code == 202
        accepted = response.json()
        view = wait_for_intake(client, accepted["status_url"])

    assert view["status"] == "review_required"
    draft = view["draft"]
    assert isinstance(draft, dict)
    assert draft["criteria"]["affected_lots"] == ["L2418"]
    assert draft["import_summary"]["accepted_rows"] == 1


def test_identical_create_request_returns_same_intake(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        first = create_intake(client)
        replay = create_intake(client)

    assert first.status_code == 202
    assert replay.status_code == 202
    assert replay.json()["intake_id"] == first.json()["intake_id"]


def test_review_update_and_confirmation_are_versioned(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        accepted = create_intake(client).json()
        review = wait_for_intake(client, accepted["status_url"])
        draft = review["draft"]
        assert isinstance(draft, dict)
        criteria = dict(draft["criteria"])
        criteria["product_name"] = "Baby Spinach 10 oz"
        updated_response = client.patch(
            f"/api/intakes/{accepted['intake_id']}/draft",
            json={
                "request_id": "1d05fc09-d47c-43aa-9f01-b021b26f0ac8",
                "expected_version": review["version"],
                "criteria": criteria,
                "inventory": draft["inventory"],
            },
        )
        assert updated_response.status_code == 200
        updated = updated_response.json()

        confirmed_response = client.post(
            f"/api/intakes/{accepted['intake_id']}/confirm",
            json={
                "request_id": "2d05fc09-d47c-43aa-9f01-b021b26f0ac8",
                "expected_version": updated["version"],
            },
        )

    assert updated["version"] == review["version"] + 1
    assert updated["evidence"][-1]["source"] == "reviewer"
    assert confirmed_response.status_code == 200
    assert confirmed_response.json()["status"] == "ready"
    assert confirmed_response.json()["incident_id"]


def test_missing_intake_returns_structured_404(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/intakes/missing/confirm",
            json={
                "request_id": "3d05fc09-d47c-43aa-9f01-b021b26f0ac8",
                "expected_version": 0,
            },
        )

    assert response.status_code == 404
    assert response.json()["code"] == "intake_not_found"


def test_packet_over_limit_returns_413_without_paths(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/intakes",
            data={
                "request_id": "4d05fc09-d47c-43aa-9f01-b021b26f0ac8"
            },
            files={
                "notice": (
                    "notice.txt",
                    b"x" * (12 * 1024 * 1024 + 1),
                    "text/plain",
                ),
                "inventory": ("inventory.csv", CSV, "text/csv"),
            },
        )

    assert response.status_code == 413
    assert response.json()["code"] == "upload_too_large"
    assert "/tmp/" not in response.text
    assert "/private/" not in response.text


def test_intake_store_failure_does_not_break_health(tmp_path: Path) -> None:
    with make_client(
        tmp_path,
        intake_repository=FailingIntakeRepository(),
    ) as client:
        health = client.get("/health")
        response = create_intake(
            client,
            request_id="5d05fc09-d47c-43aa-9f01-b021b26f0ac8",
        )

    assert health.status_code == 200
    assert response.status_code == 503
    assert response.json() == {
        "code": "intake_store_unavailable",
        "message": "Incident intake is temporarily unavailable.",
        "details": None,
    }
    assert "/private/secret" not in response.text


def test_confirmed_intake_launches_one_durable_run(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        accepted = create_intake(client).json()
        review = wait_for_intake(client, accepted["status_url"])
        confirmed = client.post(
            f"/api/intakes/{accepted['intake_id']}/confirm",
            json={
                "request_id": "6d05fc09-d47c-43aa-9f01-b021b26f0ac8",
                "expected_version": review["version"],
            },
        ).json()
        launch_payload = {
            "request_id": "7d05fc09-d47c-43aa-9f01-b021b26f0ac8"
        }
        first = client.post(
            f"/api/intakes/{accepted['intake_id']}/runs",
            json=launch_payload,
        )
        replay = client.post(
            f"/api/intakes/{accepted['intake_id']}/runs",
            json=launch_payload,
        )
        run_view = wait_for_run(client, first.json()["run"]["result_url"])

    assert confirmed["status"] == "ready"
    assert first.status_code == 202
    assert replay.status_code == 202
    assert replay.json()["run"]["run_id"] == first.json()["run"]["run_id"]
    assert first.json()["intake"]["status"] == "run_started"
    assert run_view["incident_id"] == confirmed["incident_id"]
    assert run_view["result"]["analysis"]["product"] == "Spinach 10 oz"


def test_unconfirmed_intake_cannot_launch(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        accepted = create_intake(client).json()
        wait_for_intake(client, accepted["status_url"])
        response = client.post(
            f"/api/intakes/{accepted['intake_id']}/runs",
            json={
                "request_id": "8d05fc09-d47c-43aa-9f01-b021b26f0ac8"
            },
        )

    assert response.status_code == 409
    assert response.json()["code"] == "intake_state_conflict"


def test_sample_packet_reaches_review_and_matches_demo_totals(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        response = upload_sample_packet(client)
        assert response.status_code == 202
        view = wait_for_intake(client, response.json()["status_url"])

    assert view["status"] == "review_required"
    assert view["draft"]["import_summary"]["accepted_rows"] == 6
    assert sum(
        row["on_hand"] for row in view["draft"]["inventory"]
    ) == 23
    assert view["draft"]["criteria"]["affected_lots"] == [
        "L2418",
        "L2419",
        "L2420",
        "L2421",
        "L2422",
    ]


def test_sample_invalid_inventory_surfaces_two_review_warnings(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        response = upload_sample_packet(
            client,
            inventory_name="inventory-spinach-invalid.csv",
            request_id="ad05fc09-d47c-43aa-9f01-b021b26f0ac8",
        )
        assert response.status_code == 202
        view = wait_for_intake(client, response.json()["status_url"])

    summary = view["draft"]["import_summary"]
    assert summary["accepted_rows"] == 6
    assert summary["rejected_rows"] == 2
    assert len(summary["warnings"]) == 2
    assert "non-negative integer" in summary["warnings"][0]
    assert "duplicate inventory record" in summary["warnings"][1]
