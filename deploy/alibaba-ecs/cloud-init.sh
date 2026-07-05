#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this command as root: sudo bash deploy/alibaba-ecs/cloud-init.sh" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl git jq

install -m 0755 -d /etc/apt/keyrings
if [[ ! -s /etc/apt/keyrings/docker.asc ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    -o /etc/apt/keyrings/docker.asc
  chmod 0644 /etc/apt/keyrings/docker.asc
fi

# shellcheck disable=SC1091
source /etc/os-release
cat >/etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

apt-get update
apt-get install -y \
  containerd.io \
  docker-buildx-plugin \
  docker-ce \
  docker-ce-cli \
  docker-compose-plugin

systemctl enable --now docker
install -d -m 0750 /opt/batchhelm
install -d -m 0750 /srv/batchhelm/data
install -d -m 0750 /srv/batchhelm/backups

if [[ -n ${SUDO_USER:-} && ${SUDO_USER} != root ]]; then
  usermod -aG docker "${SUDO_USER}"
  chown -R "${SUDO_USER}:${SUDO_USER}" /opt/batchhelm /srv/batchhelm
fi

echo "BatchHelm ECS host bootstrap complete."
echo "Open TCP 22 only to the operator IP and TCP 80 to judges."
