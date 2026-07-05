from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_PATH = REPOSITORY_ROOT / "deploy" / "alibaba-ecs" / "compose.yaml"
BACKUP_PATH = REPOSITORY_ROOT / "deploy" / "alibaba-ecs" / "backup.sh"
CI_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"


def test_ecs_compose_enforces_the_single_replica_storage_contract() -> None:
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))

    assert set(compose["services"]) == {"api", "web"}

    api = compose["services"]["api"]
    web = compose["services"]["web"]
    environment = api["environment"]

    assert "ports" not in api
    assert web["ports"] == ["80:80"]
    assert any(volume.endswith(":/data") for volume in api["volumes"])
    assert api["restart"] == "unless-stopped"
    assert web["restart"] == "unless-stopped"
    assert api["deploy"]["replicas"] == 1
    assert "healthcheck" in api

    assert environment["QWEN_API_KEY"].startswith("${QWEN_API_KEY:")
    assert environment["QWEN_PROOF_TOKEN"].startswith("${QWEN_PROOF_TOKEN:")
    assert environment["DATABASE_PATH"] == "/data/batchhelm.db"
    assert environment["MEMORY_PATH"] == "/data/batchhelm-memory.db"
    assert environment["ORCHESTRATION_DATABASE_PATH"] == (
        "/data/orchestration.db"
    )
    assert environment["INTAKE_DATABASE_PATH"] == "/data/intake.db"
    assert environment["QWEN_PROOF_DATABASE_PATH"] == "/data/qwen-proof.db"


def test_backup_quiesces_api_before_capturing_the_recovery_unit() -> None:
    script = BACKUP_PATH.read_text(encoding="utf-8")

    stop_index = script.index("stop -t 30 api")
    snapshot_index = script.index("run --rm --no-deps -T")
    upload_index = script.index('if [[ -d ${DATA_DIR}/uploads ]]')

    assert stop_index < snapshot_index < upload_index
    assert "restart_api" in script


def test_ci_builds_both_images_and_validates_production_compose() -> None:
    workflow = CI_PATH.read_text(encoding="utf-8")

    assert "docker build -t batchhelm-api:ci ." in workflow
    assert "docker build -t batchhelm-web:ci apps/web" in workflow
    assert (
        "docker compose -f deploy/alibaba-ecs/compose.yaml config --quiet"
        in workflow
    )
