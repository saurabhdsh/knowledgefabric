#!/bin/sh
# Fix ownership on named volumes (they keep root from older images), then drop to weave.
set -eu

dirs="/app/uploads /app/chroma_db /app/models /app/data /app/ontology_data"
for d in $dirs; do
  mkdir -p "$d"
done

if [ "$(id -u)" = "0" ]; then
  chown -R weave:weave $dirs 2>/dev/null || true
  if command -v gosu >/dev/null 2>&1; then
    exec gosu weave "$@"
  fi
  exec su -s /bin/sh weave -c 'exec "$@"' -- "$@"
fi

exec "$@"
