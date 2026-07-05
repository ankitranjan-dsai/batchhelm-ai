#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT=${BATCHHELM_INSTALL_ROOT:-/opt/batchhelm}
ENV_FILE=${BATCHHELM_ENV_FILE:-${INSTALL_ROOT}/deploy/alibaba-ecs/.env}
COMPOSE_FILE=${INSTALL_ROOT}/deploy/alibaba-ecs/compose.yaml

if [[ ! -r ${ENV_FILE} ]]; then
  echo "Deployment environment file is not readable: ${ENV_FILE}" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

DATA_DIR=${BATCHHELM_DATA_DIR:-/srv/batchhelm/data}
BACKUP_DIR=${BATCHHELM_BACKUP_DIR:-/srv/batchhelm/backups}
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
SNAPSHOT_NAME=".backup-${TIMESTAMP}"
SNAPSHOT_DIR="${DATA_DIR}/${SNAPSHOT_NAME}"
ARCHIVE="${BACKUP_DIR}/batchhelm-${TIMESTAMP}.tar.gz"

sudo install -d -m 0750 "${BACKUP_DIR}"
sudo install -d -m 0700 "${SNAPSHOT_DIR}"

cd "${INSTALL_ROOT}"
API_STOPPED=false

restart_api() {
  sudo rm -rf "${SNAPSHOT_DIR}"
  if [[ ${API_STOPPED} == true ]]; then
    sudo docker compose \
      --env-file "${ENV_FILE}" \
      -f "${COMPOSE_FILE}" \
      up -d --no-deps api >/dev/null
  fi
}

trap restart_api EXIT

sudo docker compose \
  --env-file "${ENV_FILE}" \
  -f "${COMPOSE_FILE}" \
  stop -t 30 api
API_STOPPED=true

sudo env SNAPSHOT_NAME="${SNAPSHOT_NAME}" docker compose \
  --env-file "${ENV_FILE}" \
  -f "${COMPOSE_FILE}" \
  run --rm --no-deps -T -e SNAPSHOT_NAME="${SNAPSHOT_NAME}" api python - <<'PY'
import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

data_dir = Path("/data")
snapshot_dir = data_dir / os.environ["SNAPSHOT_NAME"]
snapshot_dir.mkdir(mode=0o700, exist_ok=True)
database_names = [
    "batchhelm.db",
    "batchhelm-memory.db",
    "orchestration.db",
    "intake.db",
    "qwen-proof.db",
]
captured = []
for name in database_names:
    source_path = data_dir / name
    if not source_path.exists():
        continue
    destination_path = snapshot_dir / name
    with sqlite3.connect(source_path) as source:
        with sqlite3.connect(destination_path) as destination:
            source.backup(destination)
    captured.append(name)

(snapshot_dir / "manifest.json").write_text(
    json.dumps(
        {
            "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "databases": captured,
            "includes_uploads": (data_dir / "uploads").exists(),
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
PY

if [[ -d ${DATA_DIR}/uploads ]]; then
  sudo cp -a "${DATA_DIR}/uploads" "${SNAPSHOT_DIR}/uploads"
fi

sudo tar -C "${DATA_DIR}" -czf "${ARCHIVE}" "${SNAPSHOT_NAME}"
sudo chmod 0600 "${ARCHIVE}"
restart_api
trap - EXIT
echo "${ARCHIVE}"
