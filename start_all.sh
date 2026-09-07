#!/usr/bin/env bash
# Start Docker daemon + Weave stack (EC2 or local compose).
# Usage:
#   sudo bash start_all.sh
#   sudo bash start_all.sh --build
#   bash start_all.sh --status
#   bash start_all.sh --stop
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}"

DO_BUILD=0
MODE="start"

for arg in "$@"; do
  case "${arg}" in
    --build) DO_BUILD=1 ;;
    --status|-s) MODE="status" ;;
    --stop) MODE="stop" ;;
    --help|-h)
      cat <<'EOF'
start_all.sh — start Docker + Weave

  sudo bash start_all.sh           Start containers (no rebuild)
  sudo bash start_all.sh --build   Rebuild images, then start
  bash start_all.sh --status       Show container status
  bash start_all.sh --stop         Stop the stack

Detects HTTPS domain mode when .env has WEAVE_DOMAIN (e.g. cuweave.com).
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: ${arg} (try --help)"
      exit 1
      ;;
  esac
done

log() { echo "[start_all] $*"; }

need_sudo_docker() {
  if docker info >/dev/null 2>&1; then
    echo ""
    return
  fi
  if command -v sudo >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
    echo "sudo"
    return
  fi
  echo ""
}

DOCKER_PREFIX="$(need_sudo_docker)"
compose() {
  # shellcheck disable=SC2086
  ${DOCKER_PREFIX} docker compose "$@"
}

ensure_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    log "Docker is not installed. On EC2 run: sudo bash scripts/ec2-setup.sh"
    exit 1
  fi

  if docker info >/dev/null 2>&1 || sudo docker info >/dev/null 2>&1; then
    return
  fi

  log "Starting Docker daemon..."
  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl start docker
    sudo systemctl enable docker >/dev/null 2>&1 || true
  else
    log "Could not start Docker via systemctl. Start it manually, then re-run."
    exit 1
  fi

  # refresh privilege detection after daemon start
  DOCKER_PREFIX="$(need_sudo_docker)"
  if ! docker info >/dev/null 2>&1 && ! sudo docker info >/dev/null 2>&1; then
    log "Docker daemon did not become ready."
    exit 1
  fi
  log "Docker is running."
}

compose_files=("-f" "docker-compose.ec2.yml")
DOMAIN=""
PUBLIC_HINT=""

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a
  # Prefer grep so we don't execute arbitrary .env content.
  DOMAIN="$(grep -E '^WEAVE_DOMAIN=' .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)"
  REACT_URL="$(grep -E '^REACT_APP_API_URL=' .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)"
  set +a
fi

if [[ -n "${DOMAIN}" && -f docker-compose.domain.yml ]]; then
  compose_files+=("-f" "docker-compose.domain.yml")
  PUBLIC_HINT="https://${DOMAIN}"
  log "Mode: HTTPS domain (${DOMAIN})"
elif [[ -f docker-compose.ec2.yml ]]; then
  PUBLIC_HINT="${REACT_URL:-http://<EC2_PUBLIC_IP>}"
  log "Mode: EC2 HTTP (docker-compose.ec2.yml)"
else
  log "docker-compose.ec2.yml not found in ${ROOT_DIR}"
  exit 1
fi

if [[ ! -f .env ]]; then
  log "Missing .env — copy env.ec2.example to .env or run scripts/ec2-setup.sh first."
  exit 1
fi

ensure_docker
DOCKER_PREFIX="$(need_sudo_docker)"

case "${MODE}" in
  status)
    compose "${compose_files[@]}" ps
    exit 0
    ;;
  stop)
    log "Stopping Weave..."
    compose "${compose_files[@]}" down
    log "Stopped."
    exit 0
    ;;
esac

log "Starting Weave containers..."
if [[ "${DO_BUILD}" -eq 1 ]]; then
  compose "${compose_files[@]}" up -d --build
else
  compose "${compose_files[@]}" up -d
fi

compose "${compose_files[@]}" ps

HEALTH_URL="${PUBLIC_HINT%/}/health"
log "Waiting briefly for health..."
sleep 3
if curl -fsS --max-time 5 "${HEALTH_URL}" >/dev/null 2>&1; then
  log "Healthy: ${HEALTH_URL}"
elif curl -fsS --max-time 5 "http://127.0.0.1/health" >/dev/null 2>&1; then
  log "Healthy on localhost: http://127.0.0.1/health"
else
  log "Stack started; health not ready yet. Retry: curl -fsS ${HEALTH_URL}"
  log "Logs: ${DOCKER_PREFIX:+$DOCKER_PREFIX }docker compose ${compose_files[*]} logs -f backend"
fi

cat <<EOF

Weave is starting.
  UI:     ${PUBLIC_HINT}
  Health: ${HEALTH_URL}

EOF
