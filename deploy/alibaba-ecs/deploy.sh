#!/usr/bin/env bash
set -euo pipefail

require_variable() {
  local name=$1
  if [[ -z ${!name:-} ]]; then
    echo "${name} is required." >&2
    exit 1
  fi
}

require_safe_secret() {
  local name=$1
  local value=${!name}
  if [[ ! ${value} =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "${name} must contain only letters, numbers, dots, underscores, or hyphens." >&2
    exit 1
  fi
}

require_variable BATCHHELM_HOST
require_variable QWEN_API_KEY
require_variable QWEN_PROOF_TOKEN
require_safe_secret QWEN_API_KEY
require_safe_secret QWEN_PROOF_TOKEN

REPOSITORY_URL=${BATCHHELM_REPOSITORY_URL:-https://github.com/ankitranjan-dsai/batchhelm-ai.git}
BATCHHELM_REVISION=${BATCHHELM_REVISION:-$(git rev-parse HEAD)}
if [[ ! ${BATCHHELM_REVISION} =~ ^[0-9a-f]{40}$ ]]; then
  echo "BATCHHELM_REVISION must be a full 40-character Git commit SHA." >&2
  exit 1
fi

PUBLIC_ADDRESS=${BATCHHELM_HOST#*@}
PUBLIC_ORIGIN=${PUBLIC_ORIGIN:-http://${PUBLIC_ADDRESS}}
REMOTE_ENV="/tmp/batchhelm-${BATCHHELM_REVISION:0:12}.env"
LOCAL_ENV=$(mktemp)
trap 'rm -f "${LOCAL_ENV}"' EXIT
chmod 0600 "${LOCAL_ENV}"

{
  printf 'QWEN_API_KEY=%s\n' "${QWEN_API_KEY}"
  printf 'QWEN_PROOF_TOKEN=%s\n' "${QWEN_PROOF_TOKEN}"
  printf 'PUBLIC_ORIGIN=%s\n' "${PUBLIC_ORIGIN}"
  printf 'BATCHHELM_DATA_DIR=/srv/batchhelm/data\n'
  printf 'QWEN_BASE_URL=%s\n' \
    "${QWEN_BASE_URL:-https://dashscope-intl.aliyuncs.com/compatible-mode/v1}"
  printf 'QWEN_TEXT_MODEL=%s\n' "${QWEN_TEXT_MODEL:-qwen3.7-plus}"
  printf 'QWEN_VISION_MODEL=%s\n' "${QWEN_VISION_MODEL:-qwen3-vl-plus}"
  printf 'QWEN_TIMEOUT_SECONDS=%s\n' "${QWEN_TIMEOUT_SECONDS:-30}"
  printf 'QWEN_MAX_RETRIES=%s\n' "${QWEN_MAX_RETRIES:-2}"
  printf 'LOG_LEVEL=%s\n' "${LOG_LEVEL:-info}"
  printf 'RATE_LIMIT_PER_MINUTE=%s\n' "${RATE_LIMIT_PER_MINUTE:-120}"
  printf "REVIEWER_ROLE='%s'\n" "${REVIEWER_ROLE:-Operations Manager}"
} >"${LOCAL_ENV}"

SSH_OPTIONS=(-o BatchMode=yes -o StrictHostKeyChecking=accept-new)
if [[ -n ${BATCHHELM_SSH_KEY:-} ]]; then
  SSH_OPTIONS+=(-i "${BATCHHELM_SSH_KEY}")
fi

ssh "${SSH_OPTIONS[@]}" "${BATCHHELM_HOST}" \
  bash -s -- "${REPOSITORY_URL}" "${BATCHHELM_REVISION}" <<'REMOTE_SETUP'
set -euo pipefail
repository_url=$1
revision=$2

sudo install -d -m 0750 -o "$(id -u)" -g "$(id -g)" /opt/batchhelm
sudo install -d -m 0750 -o "$(id -u)" -g "$(id -g)" /srv/batchhelm/data
sudo install -d -m 0750 -o "$(id -u)" -g "$(id -g)" /srv/batchhelm/backups

if [[ ! -d /opt/batchhelm/.git ]]; then
  git clone --filter=blob:none "${repository_url}" /opt/batchhelm
fi

git -C /opt/batchhelm remote set-url origin "${repository_url}"
git -C /opt/batchhelm fetch --depth=1 origin "${revision}"
git -C /opt/batchhelm checkout --detach --force FETCH_HEAD
REMOTE_SETUP

scp "${SSH_OPTIONS[@]}" "${LOCAL_ENV}" "${BATCHHELM_HOST}:${REMOTE_ENV}"

ssh "${SSH_OPTIONS[@]}" "${BATCHHELM_HOST}" \
  bash -s -- "${REMOTE_ENV}" "${BATCHHELM_REVISION}" <<'REMOTE_DEPLOY'
set -euo pipefail
remote_env=$1
revision=$2

sudo install -m 0600 "${remote_env}" /opt/batchhelm/deploy/alibaba-ecs/.env
rm -f "${remote_env}"

cd /opt/batchhelm
sudo env BATCHHELM_REVISION="${revision}" docker compose \
  --env-file deploy/alibaba-ecs/.env \
  -f deploy/alibaba-ecs/compose.yaml \
  up -d --build --remove-orphans

for attempt in $(seq 1 60); do
  if curl -fsS http://127.0.0.1/health >/dev/null; then
    break
  fi
  if [[ ${attempt} -eq 60 ]]; then
    sudo docker compose \
      --env-file deploy/alibaba-ecs/.env \
      -f deploy/alibaba-ecs/compose.yaml \
      ps
    exit 1
  fi
  sleep 2
done

set -a
# shellcheck disable=SC1091
source deploy/alibaba-ecs/.env
set +a

curl -fsS -X POST \
  -H "X-BatchHelm-Proof-Token: ${QWEN_PROOF_TOKEN}" \
  http://127.0.0.1/api/qwen/verify |
  jq .
REMOTE_DEPLOY

echo "Public health check:"
curl -fsS "${PUBLIC_ORIGIN}/health" | jq .
echo "Public redacted Qwen proof:"
curl -fsS "${PUBLIC_ORIGIN}/api/qwen/proof" | jq .
echo "BatchHelm deployed at ${PUBLIC_ORIGIN}"
