#!/usr/bin/env bash
# Snapshot Weave data directories on the Azure VM (or any host).
# Usage: ./scripts/backup_weave_data.sh [/path/to/data] [/path/to/backups]
set -euo pipefail

DATA_DIR="${1:-${KF_DATA_DIR:-./backend/data}}"
BACKUP_ROOT="${2:-${KF_BACKUP_DIR:-./backups}}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${BACKUP_ROOT}/weave-${STAMP}"

mkdir -p "${DEST}"
echo "Backing up ${DATA_DIR} → ${DEST}"

if [[ -d "${DATA_DIR}" ]]; then
  tar -czf "${DEST}/data.tgz" -C "$(dirname "${DATA_DIR}")" "$(basename "${DATA_DIR}")"
fi

# Optional companions used by Compose on the VM.
for extra in uploads chroma_db ontology_data; do
  if [[ -d "./backend/${extra}" ]]; then
    tar -czf "${DEST}/${extra}.tgz" -C ./backend "${extra}"
  elif [[ -d "./${extra}" ]]; then
    tar -czf "${DEST}/${extra}.tgz" -C . "${extra}"
  fi
done

# Keep the last 14 backups.
ls -1dt "${BACKUP_ROOT}"/weave-* 2>/dev/null | tail -n +15 | xargs -r rm -rf

echo "Backup complete: ${DEST}"
ls -la "${DEST}"
