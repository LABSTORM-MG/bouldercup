#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

if [[ -f ".venv/bin/activate" ]]; then
    # Use local virtualenv when available.
    source .venv/bin/activate
fi

export RESET_DB_ON_START=1
python3 manage.py migrate

unset RESET_DB_ON_START

echo "Starting Django development server on http://127.0.0.1:8000/ ..."
exec python3 manage.py runserver
