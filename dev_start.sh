#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

if [[ -f ".venv/bin/activate" ]]; then
    # Use local virtualenv when available.
    source .venv/bin/activate
fi

KEEP_DB=false
RUNSERVER_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --keepDB)
            KEEP_DB=true
            shift
            ;;
        *)
            RUNSERVER_ARGS+=("$1")
            shift
            ;;
    esac
done

if [[ "$KEEP_DB" == false ]]; then
    rm -f db.sqlite3
fi

python3 manage.py migrate

echo "Starting Django development server on http://127.0.0.1:8000/ ..."
exec python3 manage.py runserver "${RUNSERVER_ARGS[@]}"
