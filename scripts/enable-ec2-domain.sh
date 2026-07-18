#!/usr/bin/env bash
# Enable HTTPS for an existing single-EC2 Weave deployment using Caddy.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

DOMAIN="${1:-${WEAVE_DOMAIN:-}}"
if [[ -z "${DOMAIN}" ]]; then
  echo "Usage: sudo bash scripts/enable-ec2-domain.sh cuweave.com"
  exit 1
fi
DOMAIN="${DOMAIN#http://}"
DOMAIN="${DOMAIN#https://}"
DOMAIN="${DOMAIN%%/*}"
if [[ ! "${DOMAIN}" =~ ^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
  echo "Invalid domain: ${DOMAIN}"
  exit 1
fi

if [[ ! -f .env ]]; then
  echo ".env not found. Run scripts/ec2-setup.sh first."
  exit 1
fi

update_env() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" .env; then
    sed -i.bak "s|^${key}=.*|${key}=${value}|" .env
  else
    echo "${key}=${value}" >> .env
  fi
}

echo "[weave-domain] Configuring https://${DOMAIN}"
update_env "WEAVE_DOMAIN" "${DOMAIN}"
update_env "REACT_APP_API_URL" "https://${DOMAIN}"
update_env "KF_CORS_ORIGINS" "https://${DOMAIN},https://www.${DOMAIN}"
# Free host ports 80/443 for Caddy; nginx remains reachable only on localhost
# and through the internal Docker network.
update_env "WEB_BIND_ADDRESS" "127.0.0.1"
update_env "WEB_HOST_PORT" "8080"
rm -f .env.bak

echo "[weave-domain] Rebuilding frontend and starting HTTPS gateway..."
docker compose \
  -f docker-compose.ec2.yml \
  -f docker-compose.domain.yml \
  up -d --build

echo "[weave-domain] Waiting for certificate provisioning..."
sleep 8
docker compose \
  -f docker-compose.ec2.yml \
  -f docker-compose.domain.yml \
  ps
docker compose \
  -f docker-compose.ec2.yml \
  -f docker-compose.domain.yml \
  logs --tail=40 caddy

cat <<EOF

HTTPS setup started.
Open:   https://${DOMAIN}
Health: https://${DOMAIN}/health

If the certificate is still being issued, wait one minute and retry.
EOF
