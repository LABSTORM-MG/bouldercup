#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Ensure virtualenv exists and is activated (switch over if a different venv is active).
if [[ -z "${VIRTUAL_ENV:-}" || "${VIRTUAL_ENV}" != "${PROJECT_ROOT}/.venv" ]]; then
    if [[ -n "${VIRTUAL_ENV:-}" && "${VIRTUAL_ENV}" != "${PROJECT_ROOT}/.venv" ]]; then
        # Leave any other virtualenv to avoid mixing site-packages.
        if command -v deactivate >/dev/null 2>&1; then
            deactivate
        fi
    fi
    if [[ ! -d ".venv" ]]; then
        python3 -m venv .venv
    fi
    # shellcheck source=/dev/null
    source .venv/bin/activate
fi

# Make sure Django is present so migrations/admin work out of the box.
if ! python -m django --version >/dev/null 2>&1; then
    pip install "django>=5.2,<5.3"
fi

KEEP_DB=false
RUNSERVER_ARGS=()
SEED_PARTICIPANTS=true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --keepDB)
            KEEP_DB=true
            shift
            ;;
        --no-seed)
            SEED_PARTICIPANTS=false
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

# Be smart about migrations: only create when model changes are pending.
echo "Checking for pending migrations..."
python3 manage.py makemigrations --check --dry-run || python3 manage.py makemigrations accounts
python3 manage.py migrate

if [[ "$SEED_PARTICIPANTS" == true ]]; then
    python3 manage.py shell <<'PY'
from accounts.models import Participant, AgeGroup
from datetime import date
from django.utils.text import slugify

seed_data = [
    ("Timo Schuster", date(2000, 1, 1), "male"),
    ("Anna Schmidt", date(2015, 3, 12), "female"),  # pw: 12032015
    ("Gerd Franke", date(1999, 3, 3), "male"),
    ("Heinz Keller", date(1998, 4, 4), "male"),
    ("Lena Klein", date(2002, 5, 5), "female"),
    ("Mara Berger", date(2003, 6, 6), "female"),
    ("Max Müller", date(1997, 7, 7), "male"),
    ("Oliver Graf", date(1996, 8, 8), "male"),
    ("Sarah Lang", date(2004, 9, 9), "female"),
    ("Ute Jansen", date(1995, 10, 10), "female"),
]

default_group, _ = AgeGroup.objects.get_or_create(
    name="all (0-99, Gemischt)",
    defaults={"min_age": 0, "max_age": 99, "gender": "mixed"},
)

print("Seeding demo participants (username / password):")
for name, dob, gender in seed_data:
    username = slugify(name).replace("-", "")
    defaults = {
        "name": name,
        "date_of_birth": dob,
        "password": dob.strftime("%d%m%Y"),
        "gender": gender,
        "age_group": default_group,
    }
    obj, created = Participant.objects.get_or_create(username=username, defaults=defaults)
    if created:
        obj.assign_age_group(force=True)
        obj.save()
        print(f"  {username} / {obj.password}")
    else:
        updated = False
        for field, val in defaults.items():
            if getattr(obj, field) != val:
                setattr(obj, field, val)
                updated = True
        if updated:
            obj.assign_age_group(force=True)
            obj.save()
            print(f"  updated {username} / {obj.password}")
        else:
            print(f"  exists {username} / {obj.password}")
PY
fi

DEFAULT_ADDR="0.0.0.0:8000"
echo "Starting Django development server on http://${DEFAULT_ADDR}/ (reachable on local network) ..."
exec python3 manage.py runserver "${RUNSERVER_ARGS[@]}" "${DEFAULT_ADDR}"
