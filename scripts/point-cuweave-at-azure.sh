#!/usr/bin/env bash
# Run on the EC2 host that already terminates HTTPS for cuweave.com.
# Caddy keeps the certificate and forwards the site to the Azure VM.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

UPSTREAM="${1:-20.127.186.132:8080}"

if [[ ! -f .env ]]; then
  echo ".env not found. Run scripts/enable-ec2-domain.sh cuweave.com first."
  exit 1
fi

if grep -q "^WEAVE_UPSTREAM=" .env; then
  sed -i.bak "s|^WEAVE_UPSTREAM=.*|WEAVE_UPSTREAM=${UPSTREAM}|" .env
else
  echo "WEAVE_UPSTREAM=${UPSTREAM}" >> .env
fi
rm -f .env.bak

echo "[cuweave] Forwarding cuweave.com to ${UPSTREAM}"
docker compose \
  -f docker-compose.ec2.yml \
  -f docker-compose.domain.yml \
  up -d caddy

docker compose \
  -f docker-compose.ec2.yml \
  -f docker-compose.domain.yml \
  ps caddy
