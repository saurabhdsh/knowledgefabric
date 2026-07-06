#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Migrate Knowledge Fabric state from docker-compose named volumes into the
# local repo directories used by the native (uvicorn) runtime.
#
# Copies:
#   <project>_knowledge_data    -> backend/data
#   <project>_knowledge_uploads -> backend/uploads
#   <project>_knowledge_chroma  -> backend/chroma_db
#   <project>_knowledge_models  -> backend/models
#
# Source volumes are NOT deleted — you can still run Docker afterwards.
# Files that already exist locally are NOT overwritten unless --force is set.
#
# Usage:
#   bash scripts/migrate_from_docker_volumes.sh             # auto-detect project
#   bash scripts/migrate_from_docker_volumes.sh my-project  # explicit project name
#   bash scripts/migrate_from_docker_volumes.sh --force     # overwrite local files
# ---------------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$REPO_ROOT/backend"
FORCE=0
PROJECT=""

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) PROJECT="$arg" ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed / not on PATH." >&2
  exit 1
fi

# Auto-detect the compose project name if not provided. docker-compose
# defaults to the basename of the directory containing docker-compose.yml,
# lowercased and with non-alphanumerics removed.
if [ -z "$PROJECT" ]; then
  PROJECT="$(basename "$REPO_ROOT" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_-')"
fi

echo "Repo root        : $REPO_ROOT"
echo "Backend root     : $BACKEND"
echo "Compose project  : $PROJECT"
echo "Force overwrite  : $([ $FORCE -eq 1 ] && echo yes || echo no)"
echo ""

# (compose volume name, local destination)
PAIRS=(
  "${PROJECT}_knowledge_data:$BACKEND/data"
  "${PROJECT}_knowledge_uploads:$BACKEND/uploads"
  "${PROJECT}_knowledge_chroma:$BACKEND/chroma_db"
  "${PROJECT}_knowledge_models:$BACKEND/models"
)

ANY_FOUND=0
for pair in "${PAIRS[@]}"; do
  VOL="${pair%%:*}"
  DEST="${pair##*:}"
  echo "----- $VOL -----"
  if ! docker volume inspect "$VOL" >/dev/null 2>&1; then
    echo "  (not found — skipping)"
    continue
  fi
  ANY_FOUND=1
  mkdir -p "$DEST"

  # Use a throwaway alpine container that bind-mounts the volume read-only
  # plus a host directory rw, then copies (-n = no clobber unless --force).
  COPY_FLAG="-n"
  [ $FORCE -eq 1 ] && COPY_FLAG=""

  docker run --rm \
    -v "${VOL}:/src:ro" \
    -v "${DEST}:/dst" \
    alpine sh -c "cp -R ${COPY_FLAG} /src/. /dst/ 2>/dev/null || true; ls -la /dst | head -30"

  echo ""
done

if [ $ANY_FOUND -eq 0 ]; then
  echo "No matching docker volumes were found under project '$PROJECT'."
  echo "List them with:  docker volume ls"
  echo "Then re-run:     bash scripts/migrate_from_docker_volumes.sh <project>"
  exit 2
fi

echo "Done. Restart uvicorn and the fabrics list should be populated."
