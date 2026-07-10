#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"

if [[ ! -d "${BACKEND_DIR}" ]]; then
  echo "Backend directory not found at ${BACKEND_DIR}"
  exit 1
fi

cd "${BACKEND_DIR}"

VENV_DIR=""
if [[ -d "venv" ]]; then
  VENV_DIR="venv"
elif [[ -d ".venv" ]]; then
  VENV_DIR=".venv"
else
  echo "Python virtual environment not found at backend/venv or backend/.venv"
  echo "Create it first: cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

source "${VENV_DIR}/bin/activate"

if ! command -v uvicorn >/dev/null 2>&1; then
  echo "uvicorn is not installed in backend/${VENV_DIR}."
  echo "Run: cd backend && source ${VENV_DIR}/bin/activate && pip install -r requirements.txt"
  exit 1
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload \
  --reload-exclude 'uploads/*' \
  --reload-exclude 'uploads/**' \
  --reload-exclude 'data/*' \
  --reload-exclude 'data/**' \
  --reload-exclude 'chroma_db/*' \
  --reload-exclude 'chroma_db/**' \
  --reload-exclude '*.pyc' \
  --reload-exclude '__pycache__/*'
