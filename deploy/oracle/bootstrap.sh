#!/usr/bin/env bash
set -Eeuo pipefail

readonly SERVICE_USER="faztestbot"
readonly SERVICE_GROUP="faztestbot"
readonly APP_ROOT="/opt/faztestbot"
readonly DATA_ROOT="/var/lib/faztestbot"
readonly CONFIG_ROOT="/etc/faztestbot"
readonly ENV_FILE="${CONFIG_ROOT}/faztestbot.env"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

if [[ "${EUID}" -ne 0 ]]; then
  echo "bootstrap.sh must be run as root" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install --yes --no-install-recommends \
  ca-certificates curl python3 python3-venv unzip util-linux

if ! getent group "${SERVICE_GROUP}" >/dev/null; then
  groupadd --system "${SERVICE_GROUP}"
fi
if ! id --user "${SERVICE_USER}" >/dev/null 2>&1; then
  useradd \
    --system \
    --gid "${SERVICE_GROUP}" \
    --home-dir "${DATA_ROOT}" \
    --shell /usr/sbin/nologin \
    "${SERVICE_USER}"
else
  actual_group="$(id --group --name "${SERVICE_USER}")"
  actual_home="$(getent passwd "${SERVICE_USER}" | cut -d: -f6)"
  if [[ "${actual_group}" != "${SERVICE_GROUP}" || "${actual_home}" != "${DATA_ROOT}" ]]; then
    echo "existing ${SERVICE_USER} account does not match the deployment contract" >&2
    exit 1
  fi
fi

install -d -o root -g root -m 0755 "${APP_ROOT}" "${APP_ROOT}/releases"
install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0700 "${DATA_ROOT}"
install -d -o root -g "${SERVICE_GROUP}" -m 0750 "${CONFIG_ROOT}"

if [[ ! -e "${ENV_FILE}" ]]; then
  install -o root -g "${SERVICE_GROUP}" -m 0640 \
    "${SCRIPT_DIR}/faztestbot.env.example" "${ENV_FILE}"
  echo "Created ${ENV_FILE}; populate BOT_TOKEN before deploying a release."
else
  echo "Preserved existing ${ENV_FILE}."
fi
chown root:"${SERVICE_GROUP}" "${ENV_FILE}"
chmod 0640 "${ENV_FILE}"

install -o root -g root -m 0755 \
  "${SCRIPT_DIR}/deploy-release.sh" /usr/local/sbin/faztestbot-deploy
install -o root -g root -m 0644 \
  "${SCRIPT_DIR}/faztestbot.service" /etc/systemd/system/faztestbot.service

systemctl daemon-reload
systemctl enable faztestbot.service

echo "Oracle host bootstrap complete."
echo "Next: edit ${ENV_FILE}, then run: sudo faztestbot-deploy vX.Y.Z"
