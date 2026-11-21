#!/usr/bin/env bash
# One command on the Azure VM, after this repo is cloned or pulled.
#   sudo bash scripts/azure-setup.sh
#
# GoDaddy must already point cuweave.com at this VM, and ports 80 and 443
# must be open. Those two live outside the VM, so this script checks them
# and then does the rest.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ "${EUID}" -ne 0 ]]; then
  exec sudo bash "$0" "$@"
fi

log() { echo "[azure-setup] $*"; }

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  log "Docker Compose is not available. Install Docker, then run this again."
  exit 1
fi

public_ip() {
  curl -fsS -H Metadata:true --max-time 3 \
    "http://169.254.169.254/metadata/instance/network/interface/0/ipv4/ipAddress/0/publicIpAddress?api-version=2021-02-01&format=text" \
    2>/dev/null || true
}

update_env() {
  local key="$1"
  local value="$2"
  local tmp
  tmp="$(mktemp)"
  grep -v "^${key}=" .env > "${tmp}" || true
  printf '%s=%s\n' "${key}" "${value}" >> "${tmp}"
  mv "${tmp}" .env
}

env_value() {
  local key="$1"
  grep "^${key}=" .env | cut -d= -f2- || true
}

if [[ ! -f .env ]]; then
  cp env.azure.example .env
  log "Created .env from env.azure.example"
fi

if [[ -z "$(env_value SECRET_KEY)" || "$(env_value SECRET_KEY)" == "change-me-to-a-long-random-string" ]]; then
  update_env "SECRET_KEY" "$(openssl rand -hex 32)"
  log "Generated SECRET_KEY"
fi

if [[ -z "$(env_value POSTGRES_PASSWORD)" || "$(env_value POSTGRES_PASSWORD)" == "change-me-strong-db-password" ]]; then
  update_env "POSTGRES_PASSWORD" "$(openssl rand -hex 16)"
  log "Generated POSTGRES_PASSWORD"
fi

DEFAULT_ENDPOINT="https://exxondemofdr.cognitiveservices.azure.com/openai/v1"
KEY="${OPENAI_API_KEY:-$(env_value OPENAI_API_KEY)}"
ENDPOINT="${OPENAI_BASE_URL:-$(env_value OPENAI_BASE_URL)}"
if [[ -z "${KEY}" ]]; then
  read -r -p "Paste the Azure OpenAI endpoint [${DEFAULT_ENDPOINT}]: " ENDPOINT
  echo
  read -r -s -p "Paste the Azure OpenAI key: " KEY
  echo
fi
ENDPOINT="${ENDPOINT:-${DEFAULT_ENDPOINT}}"
ENDPOINT="${ENDPOINT#"${ENDPOINT%%[![:space:]]*}"}"
ENDPOINT="${ENDPOINT%"${ENDPOINT##*[![:space:]]}"}"
ENDPOINT="${ENDPOINT%/}"
if [[ "${ENDPOINT}" != */openai/v1 ]]; then
  ENDPOINT="${ENDPOINT}/openai/v1"
fi
if [[ -z "${KEY}" ]]; then
  log "OPENAI_API_KEY is required. Paste the key from the Azure OpenAI resource."
  exit 1
fi

update_env "OPENAI_API_KEY" "${KEY}"
update_env "OPENAI_BASE_URL" "${ENDPOINT}"
log "Chat endpoint: ${ENDPOINT}"
update_env "OPENAI_QUERY_MODEL" "gpt-5-mini"
update_env "ONTOLOGY_LLM_MODEL" "gpt-5-mini"
update_env "DEFAULT_LLM_PROVIDER" "openai"
update_env "ONTOLOGY_LLM_PROVIDER" "openai"
update_env "BEDROCK_ENABLED" "false"
update_env "ENABLED_LLM_PROVIDERS" "openai"
update_env "WEAVE_DOMAIN" "cuweave.com"
update_env "REACT_APP_API_URL" "https://cuweave.com"
update_env "KF_CORS_ORIGINS" "https://cuweave.com,https://www.cuweave.com"
unset KEY

VM_IP="$(public_ip)"
if [[ -z "${VM_IP}" ]]; then
  VM_IP="20.127.186.132"
fi
log "This VM address: ${VM_IP}"

for name in cuweave.com www.cuweave.com; do
  resolved="$(getent ahostsv4 "${name}" 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ' ' || true)"
  if [[ "${resolved}" != *"${VM_IP}"* ]]; then
    log "${name} resolves to '${resolved:-nothing}', not ${VM_IP}."
    log "In GoDaddy, set an A record for ${name} to ${VM_IP}, wait, then run this again."
    exit 1
  fi
done
log "DNS for cuweave.com points here"

if ss -ltn | awk '{print $4}' | grep -Eq '(^|:)80$|(:443)$'; then
  ours="$(docker ps --filter name=weave-azure-caddy --format '{{.Names}}' || true)"
  if [[ -z "${ours}" ]]; then
    log "Port 80 or 443 is already in use by another process. Free it, then run this again."
    ss -ltnp | grep -E ':80 |:443 ' || true
    exit 1
  fi
fi

log "Building and starting Weave. The first build takes several minutes."
docker compose -f docker-compose.azure.yml up -d --build

log "Waiting for https://cuweave.com/health"
ready=0
for _ in $(seq 1 36); do
  if curl -fsS --max-time 10 https://cuweave.com/health >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 5
done

if [[ "${ready}" -ne 1 ]]; then
  log "The site did not answer yet. Certificate issuance can take a minute."
  log "Check: docker compose -f docker-compose.azure.yml logs --tail=40 caddy"
  exit 1
fi

log "Weave is up."
log "  https://cuweave.com"
log "  Login: Saurabh / admin123"
log "Change that password after the first sign-in."
