#!/usr/bin/env bash
set -Eeuo pipefail

readonly SERVICE_USER="faztestbot"
readonly SERVICE_GROUP="faztestbot"
readonly APP_ROOT="/opt/faztestbot"
readonly RELEASES_ROOT="${APP_ROOT}/releases"
readonly CURRENT_LINK="${APP_ROOT}/current"
readonly DATA_ROOT="/var/lib/faztestbot"
readonly ENV_FILE="/etc/faztestbot/faztestbot.env"
readonly REPOSITORY="FazbearYT/FazTestBot"
readonly LOCK_FILE="/run/lock/faztestbot-deploy.lock"

if [[ "${EUID}" -ne 0 ]]; then
  echo "faztestbot-deploy must be run as root" >&2
  exit 1
fi
if [[ "$#" -ne 1 || ! "$1" =~ ^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
  echo "usage: faztestbot-deploy vX.Y.Z" >&2
  exit 2
fi

readonly TAG="$1"
readonly ARCHIVE="FazTestBot-${TAG}.zip"
readonly CHECKSUM="${ARCHIVE}.sha256"
readonly RELEASE_DIR="${RELEASES_ROOT}/${TAG}"
readonly RELEASE_URL="https://github.com/${REPOSITORY}/releases/download/${TAG}"

exec 9>"${LOCK_FILE}"
if ! flock --nonblock 9; then
  echo "another FazTestBot deployment is already running" >&2
  exit 1
fi

if [[ ! -r "${ENV_FILE}" ]]; then
  echo "missing readable environment file: ${ENV_FILE}" >&2
  exit 1
fi
if ! grep -Eq '^BOT_TOKEN=.+$' "${ENV_FILE}"; then
  echo "BOT_TOKEN is missing from ${ENV_FILE}" >&2
  exit 1
fi
if ! grep -Fxq 'FAZTESTBOT_DATA_DIR=/var/lib/faztestbot' "${ENV_FILE}"; then
  echo "FAZTESTBOT_DATA_DIR must be /var/lib/faztestbot for this deployment" >&2
  exit 1
fi
if [[ -e "${RELEASE_DIR}" ]]; then
  echo "release is already installed: ${RELEASE_DIR}" >&2
  exit 1
fi

work_dir="$(mktemp -d)"
candidate_dir=""
cleanup() {
  rm -rf -- "${work_dir}"
  if [[ -n "${candidate_dir}" && -d "${candidate_dir}" ]]; then
    rm -rf -- "${candidate_dir}"
  fi
}
trap cleanup EXIT

curl --fail --location --proto '=https' --tlsv1.2 \
  --retry 3 --retry-all-errors --connect-timeout 10 --max-time 300 \
  --output "${work_dir}/${ARCHIVE}" "${RELEASE_URL}/${ARCHIVE}"
curl --fail --location --proto '=https' --tlsv1.2 \
  --retry 3 --retry-all-errors --connect-timeout 10 --max-time 60 \
  --output "${work_dir}/${CHECKSUM}" "${RELEASE_URL}/${CHECKSUM}"

(
  cd "${work_dir}"
  sha256sum --check --strict "${CHECKSUM}"
)

unzip -q "${work_dir}/${ARCHIVE}" -d "${work_dir}/source"
source_dir="${work_dir}/source/FazTestBot-${TAG}"
if [[ ! -f "${source_dir}/bot.py" || ! -f "${source_dir}/requirements.txt" ]]; then
  echo "release archive has an unexpected layout" >&2
  exit 1
fi

candidate_dir="$(mktemp -d --tmpdir="${RELEASES_ROOT}" ".${TAG}.candidate.XXXXXX")"
cp -a -- "${source_dir}/." "${candidate_dir}/"
ln -s "${ENV_FILE}" "${candidate_dir}/.env"
chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${candidate_dir}"

runuser -u "${SERVICE_USER}" -- python3 -m venv "${candidate_dir}/.venv"
runuser -u "${SERVICE_USER}" -- \
  "${candidate_dir}/.venv/bin/python" -m pip install \
  --disable-pip-version-check --retries 3 --timeout 30 \
  --requirement "${candidate_dir}/requirements.txt"
(
  cd "${candidate_dir}"
  runuser -u "${SERVICE_USER}" -- \
    .venv/bin/python -m scripts.release verify --tag "${TAG}"
  runuser -u "${SERVICE_USER}" -- \
    .venv/bin/python -m scripts.doctor --json
)

# The runtime must not be able to replace its own source or dependencies.
chown -R root:root "${candidate_dir}"
mv -- "${candidate_dir}" "${RELEASE_DIR}"
candidate_dir=""

previous_release=""
if [[ -L "${CURRENT_LINK}" ]]; then
  previous_release="$(readlink -f -- "${CURRENT_LINK}")"
fi

systemctl stop faztestbot.service || true
if [[ -n "${previous_release}" && -f "${DATA_ROOT}/database/users.db" ]]; then
  (
    cd "${previous_release}"
    runuser -u "${SERVICE_USER}" -- .venv/bin/python -m scripts.database backup
  )
fi

new_link="${APP_ROOT}/.current.${TAG}.$$"
ln -s "${RELEASE_DIR}" "${new_link}"
mv -Tf -- "${new_link}" "${CURRENT_LINK}"

rollback() {
  echo "candidate failed liveness; attempting code rollback" >&2
  systemctl stop faztestbot.service || true
  if [[ -n "${previous_release}" && -d "${previous_release}" ]]; then
    rollback_link="${APP_ROOT}/.current.rollback.$$"
    ln -s "${previous_release}" "${rollback_link}"
    mv -Tf -- "${rollback_link}" "${CURRENT_LINK}"
    systemctl start faztestbot.service || true
  fi
  echo "Inspect: journalctl -u faztestbot.service --since '-10 minutes'" >&2
  echo "Database backups were not restored automatically to avoid discarding new data." >&2
}

if ! systemctl start faztestbot.service; then
  rollback
  exit 1
fi

for _ in $(seq 1 30); do
  if (
    cd "${RELEASE_DIR}"
    runuser -u "${SERVICE_USER}" -- \
      .venv/bin/python -m scripts.liveness --json >/dev/null 2>&1
  ); then
    echo "FazTestBot ${TAG} is live."
    exit 0
  fi
  sleep 1
done

rollback
exit 1
