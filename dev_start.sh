#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Ensure virtualenv exists and is activated.
if [[ ! -d ".venv" ]]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

# Make sure Django is present so migrations/admin work out of the box.
if ! python -m django --version >/dev/null 2>&1; then
    pip install "django>=5.2,<5.3"
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

DEFAULT_ADDR="0.0.0.0:8000"
echo "Starting Django development server on http://${DEFAULT_ADDR}/ (reachable on local network) ..."
exec python3 manage.py runserver "${RUNSERVER_ARGS[@]}" "${DEFAULT_ADDR}"
