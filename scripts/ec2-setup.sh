#!/usr/bin/env bash
# Bootstrap Weave on a fresh EC2 instance (Amazon Linux 2023 / Ubuntu).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

log() { echo "[ec2-setup] $*"; }

if [[ "${EUID}" -ne 0 ]]; then
  log "Re-run with sudo: sudo bash scripts/ec2-setup.sh"
  exit 1
fi

install_docker() {
  if command -v docker >/dev/null 2>&1; then
    log "Docker already installed"
    return
  fi

  if [[ -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
  fi

  if [[ "${ID:-}" == "amzn" ]]; then
    log "Installing Docker on Amazon Linux..."
    dnf update -y
    dnf install -y docker git
    systemctl enable docker
    systemctl start docker
  elif [[ "${ID:-}" == "ubuntu" ]]; then
    log "Installing Docker on Ubuntu..."
    apt-get update -y
    apt-get install -y ca-certificates curl git
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" \
      > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable docker
    systemctl start docker
  else
    log "Unsupported OS. Install Docker manually, then run: docker compose -f docker-compose.ec2.yml up -d --build"
    exit 1
  fi
}

resolve_public_url() {
  local ip=""
  ip="$(curl -fsS --max-time 2 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)"
  if [[ -z "${ip}" ]]; then
    ip="$(curl -fsS --max-time 5 https://checkip.amazonaws.com 2>/dev/null | tr -d '[:space:]' || true)"
  fi
  if [[ -z "${ip}" ]]; then
    read -r -p "Enter EC2 public IP or domain: " ip
  fi
  echo "http://${ip}"
}

install_docker

if ! docker compose version >/dev/null 2>&1; then
  log "Installing docker compose plugin..."
  if [[ -f /etc/os-release ]] && grep -q amzn /etc/os-release; then
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  fi
fi

PUBLIC_URL="${PUBLIC_URL:-$(resolve_public_url)}"
log "Public URL: ${PUBLIC_URL}"

if [[ ! -f .env ]]; then
  cp env.ec2.example .env
fi

SECRET_KEY="${SECRET_KEY:-$(openssl rand -hex 32)}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(openssl rand -hex 16)}"

# Update or append keys in .env
update_env() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" .env; then
    sed -i.bak "s|^${key}=.*|${key}=${value}|" .env
  else
    echo "${key}=${value}" >> .env
  fi
}

update_env "REACT_APP_API_URL" "${PUBLIC_URL}"
update_env "KF_CORS_ORIGINS" "${PUBLIC_URL}"
update_env "SECRET_KEY" "${SECRET_KEY}"
update_env "POSTGRES_PASSWORD" "${POSTGRES_PASSWORD}"
rm -f .env.bak

log "Building and starting Weave (first run may take 10–15 minutes)..."
docker compose -f docker-compose.ec2.yml up -d --build

log ""
log "Done. Open in your browser:"
log "  ${PUBLIC_URL}"
log ""
log "Default login: Saurabh / admin123"
log "Health check:  ${PUBLIC_URL%/}/health"
log ""
log "Useful commands:"
log "  docker compose -f docker-compose.ec2.yml logs -f"
log "  docker compose -f docker-compose.ec2.yml ps"
