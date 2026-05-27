# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## About This Folder (`claude/`)

This folder contains documentation and analysis files for AI assistants working on this codebase:

- **CLAUDE.md** (this file): Project documentation, development commands, architecture overview, coding standards
- **overview.md**: Architectural analysis, kept up to date as the project evolves

**Note**: The `claude/` folder is NOT git-ignored — it is tracked but not deployed. Do not put secrets here.

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

**CRITICAL: NEVER LEAVE DEV SERVERS RUNNING**
- You are FORBIDDEN from leaving dev servers running after your response is complete
- If you start the dev server for testing, you MUST kill it before finishing your response
- After testing, ALWAYS run: `lsof -ti:8000 | xargs -r kill -9`
- Check with `lsof -i:8000` to verify no process is running
- This is NON-NEGOTIABLE - leaving servers running wastes resources and causes port conflicts
- If you fail to stop the server, you have failed the task

## Architecture

### Django Apps

- **accounts**: Core app containing all business logic
  - `models.py`: AgeGroup, Participant, Boulder, Result, CompetitionSettings (+ proxy models Punktesystem, Wettkampfdatum), AdminMessage, SiteSettings (+ `submission_always_open` global flag), GreetingAcknowledgment, SubmissionWindow, CountdownSettings
  - `views/`: Split into `auth.py` (login/logout), `participant.py` (dashboard, results, scoreboard, admin message API), `admin.py` (CSV upload), `myadmin.py` (custom admin dashboard)
  - `services/`: Business logic extraction
    - `scoring_service.py`: All scoring algorithms (IFSC, point-based, dynamic point-based)
    - `result_service.py`: Result submission handling, normalization, validation
  - `utils.py`: Password hashing utilities (`hash_password()`, `verify_password()`) and CSV helpers
  - `admin.py`: Django admin customization with singleton pattern for settings, admin message broadcast

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
- **Zone hierarchy normalization**: `ResultService` enforces that top implies zone2 implies zone1 based on boulder's `zone_count`. When a boulder's `zone_count` changes, `signals.py` normalizes related Results via `QuerySet.update()` (bypasses `.save()`, so `updated_at`/version/history are untouched)
- **Global submission override**: `SiteSettings.submission_always_open` bypasses all time-window checks when enabled — checked first in `window_service.py`
- **Smart `updated_at` tracking**: `Result.updated_at` is only refreshed when result data fields actually change (not on every `.save()` call)
- **Caching**: Competition settings cached 5 minutes, scoreboards cached 5 seconds (see `scoring_service.py`)
- **Audit logging**: Strategic logging captures failed authentications, submissions outside time windows, and admin changes to results. All logs include relevant context (usernames, IDs, field changes)
- **AJAX autosave**: Results page uses `fetch` with version-based optimistic locking; `sendBeacon` on unload; auto-retry on reconnect via `online`/`offline` events (`offline_queue.js`)

### Database

SQLite in development (`db.sqlite3`). The `dev_start.sh` script deletes and recreates it by default. Production also uses SQLite (configurable for PostgreSQL via `DATABASE_URL` environment variable).

## Production Deployment

See `DEPLOYMENT.md` for one-time manual deployment and `DEV_DEPLOYMENT.md` for the full GitHub Actions pipeline.

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
- `CSRF_TRUSTED_ORIGINS` configured for reverse proxy setup
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
- `DEPLOYMENT.md` - One-time manual deployment guide (no GitHub Actions)
- `DEV_DEPLOYMENT.md` - Full CI/CD deployment guide (GitHub Actions pipeline)
- `CLAUDE.md` - This file (project documentation for AI assistants, local-only)
- `TODO.md` - Project todo list

## Git Workflow Rules

**IMPORTANT: Follow these rules strictly:**

### Master Branch
- `master` is the main development branch
- **Only commit to master for significant changes** (features, bug fixes, refactoring)
- Do NOT commit every tiny change - batch related changes together
- Master should always be stable and deployable

### Deploy Branch
- `deploy` branch triggers automated deployment via GitHub Actions
- **NEVER push to deploy unless user explicitly asks**
- Deploy branch should only be updated when user says "deploy" or "push to deploy"
- User controls when production deployment happens

### Typical Workflow
```bash
# Make changes and commit to master
git checkout master
git add <files>
git commit -m "Description"
git push origin master

# ONLY push to deploy when user explicitly requests it
# User will say "deploy this" or "push to production"
git checkout deploy
git reset --hard master
git push origin deploy
```

### When to Commit to Master

**CRITICAL RULE: ONLY COMMIT WHEN USER EXPLICITLY ASKS**
- NEVER commit automatically after making changes
- Wait for user to say "commit", "you can commit", "commit this", etc.
- User must explicitly request a commit
- This gives user a chance to review changes before they're committed
- If you commit without being asked, you have failed

✅ **DO commit for (when user asks):**
- New features
- Bug fixes
- Refactoring
- Configuration changes
- Documentation updates (if substantial)
- Security fixes

❌ **DON'T commit for:**
- Tiny typo fixes
- Single-line changes
- Minor formatting
- Small doc tweaks

**Batch small changes together** into one meaningful commit (when user requests it).

### When to Push to Deploy
✅ **ONLY when user explicitly says:**
- "deploy"
- "push to deploy"
- "push to production"
- "test the deployment"

❌ **NEVER automatically push to deploy** after committing to master

## File Exclusions

The following files/directories are in .gitignore (not committed):
- `.claude/` - Claude CLI settings (hidden folder, gitignored)
- `.vscode/` - VS Code settings (all files)
- `logs/` - Application logs
- `backups/` - Database backups
- `.env` - Production secrets

The `claude/` folder (this folder) is tracked by git but not deployed.
