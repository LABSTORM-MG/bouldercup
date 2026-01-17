# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BoulderCup is a Django 5.2 web application for managing bouldering competitions. It handles participant registration, result tracking, and live scoreboards with multiple scoring systems.

## Development Commands

```bash
# Start development server (resets DB by default, seeds demo data)
./dev_start.sh

# Keep existing database between restarts
./dev_start.sh --keepDB

# Skip seeding demo participants
./dev_start.sh --no-seed

# Run Django management commands
python3 manage.py runserver
python3 manage.py makemigrations accounts
python3 manage.py migrate
python3 manage.py test accounts

# Activate virtualenv manually
source .venv/bin/activate
```

## Architecture

### Django Apps

- **accounts**: Core app containing all business logic
  - `models.py`: AgeGroup, Participant, Boulder, Result, CompetitionSettings, Rulebook, HelpText, AdminMessage, SubmissionWindow
  - `views/`: Split into `auth.py` (login/logout), `participant.py` (dashboard, results, scoreboard, admin message API), `admin.py` (CSV upload)
  - `services/`: Business logic extraction
    - `scoring_service.py`: All scoring algorithms (IFSC, point-based, dynamic point-based)
    - `result_service.py`: Result submission handling, normalization, validation
  - `utils.py`: Password hashing utilities (`hash_password()`, `verify_password()`) and CSV helpers
  - `admin.py`: Django admin customization with singleton pattern for settings, admin message broadcast

- **competition_admin**: Admin proxy models (minimal, mostly delegates to accounts)

- **web_project**: Django project configuration
  - `settings/`: Split settings (base.py, dev.py, prod.py)

### Scoring Systems

Three grading modes configured in `CompetitionSettings.grading_system`:
1. **ifsc**: IFSC-style (tops, zones, attempts) - no points, ranked by tops > zones > fewer attempts
2. **point_based**: Fixed points per top/zone with attempt penalty
3. **point_based_dynamic**: Top points vary based on percentage of participants who topped each boulder

### Key Patterns

- **Session-based participant auth**: No Django User model; participants authenticate via username/DOB password stored in `Participant` model
- **Password security**: Participant passwords are hashed using Django's `make_password` (PBKDF2 SHA256 by default). The `accounts.utils` module provides `hash_password()` and `verify_password()` utilities. Default passwords are generated from DOB (DDMMYYYY format) and automatically hashed when participants are created via signals
- **Singleton models**: `CompetitionSettings`, `Rulebook`, `HelpText`, and `AdminMessage` use `singleton_guard` field for single-instance enforcement
- **Content caching**: `HelpText`, `Rulebook`, and `AdminMessage` singleton models cache their content for 5 minutes. Cache is automatically invalidated on save
- **Admin message broadcast**: Real-time message broadcasting to all participants via polling API (`/api/admin-message/`). Frontend polls every 30s with jitter (5-10s initial delay). Messages display as dismissible modals with custom background colors
- **Zone hierarchy normalization**: `ResultService` enforces that top implies zone2 implies zone1 based on boulder's `zone_count`
- **Caching**: Competition settings cached 5 minutes, scoreboards cached 5 seconds (see `scoring_service.py`)
- **Audit logging**: Strategic logging captures failed authentications, submissions outside time windows, and admin changes to results. All logs include relevant context (usernames, IDs, field changes)
- **AJAX autosave**: Results page uses XMLHttpRequest with timestamp-based conflict resolution

### Database

SQLite in development (`db.sqlite3`). The `dev_start.sh` script deletes and recreates it by default. Production also uses SQLite (configurable for PostgreSQL via `DATABASE_URL` environment variable).

## Production Deployment

See `DEPLOYMENT.md` for complete deployment guide.

**Architecture:**
- External reverse proxy (HTTPS) → VM nginx (port 80) → Gunicorn (Unix socket) → Django
- Dedicated deployment user (`bouldercup-deploy`) with minimal sudo permissions
- GitHub Actions for automated deployment on push to `deploy` branch
- Systemd service management with auto-restart on failure

**Key files:**
- `deploy.sh`: Automated deployment script (pulls code, installs deps, migrates, restarts)
- `.env`: Production environment variables (SECRET_KEY, ALLOWED_HOSTS)
- Configuration files embedded in DEPLOYMENT.md (systemd service, nginx config)

**Security:**
- `DEBUG = False` in production
- `SECURE_SSL_REDIRECT = False` (external proxy handles SSL)
- Password hashing with PBKDF2 SHA256
- Session-based authentication
- Principle of least privilege for deployment user

## Language

UI text and model labels are in German. Code comments and variable names are in English.

## Repository Structure

- `plans/` - Planning documents (gitignored)
- `accounts/` - Main Django app
- `web_project/` - Django project configuration
- `static/` - Frontend assets (CSS, JS)
- `templates/` - Django templates
- `DEPLOYMENT.md` - Production deployment guide
- `CLAUDE.md` - This file (project documentation for AI assistants)
- `TODO.md` - Project todo list
