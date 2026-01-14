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
  - `models.py`: AgeGroup, Participant, Boulder, Result, CompetitionSettings, Rulebook, SubmissionWindow
  - `views/`: Split into `auth.py` (login/logout), `participant.py` (dashboard, results, scoreboard), `admin.py` (CSV upload)
  - `services/`: Business logic extraction
    - `scoring_service.py`: All scoring algorithms (IFSC, point-based, dynamic point-based)
    - `result_service.py`: Result submission handling, normalization, validation
  - `admin.py`: Django admin customization with singleton pattern for settings

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
- **Singleton models**: `CompetitionSettings` and `Rulebook` use `singleton_guard` field for single-instance enforcement
- **Zone hierarchy normalization**: `ResultService` enforces that top implies zone2 implies zone1 based on boulder's `zone_count`
- **Caching**: Competition settings cached 5 minutes, scoreboards cached 5 seconds (see `scoring_service.py`)
- **AJAX autosave**: Results page uses XMLHttpRequest with timestamp-based conflict resolution

### Database

SQLite in development (`db.sqlite3`). The `dev_start.sh` script deletes and recreates it by default.

## Language

UI text and model labels are in German. Code comments and variable names are in English.
