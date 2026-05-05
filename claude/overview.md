# BoulderCup — Architecture Overview

**Generated**: 2026-02-09
**Last updated**: 2026-05-05 (reflects `feature/custom-admin-dashboard` branch)
**Analyzed by**: Claude Code (Sonnet 4.6)
**Repository**: Django 5.2 bouldering competition management system

---

## Repository Structure

```
bouldercup/
├── accounts/                   # Core app — all business logic
│   ├── models.py               # 9 models
│   ├── forms.py                # LoginForm, CSVUploadForm, PasswordChangeForm,
│   │                           # ParticipantAdminForm, ResultSubmissionForm
│   ├── admin.py                # Django admin (~35KB, rich customization)
│   ├── signals.py              # Auto age-group assignment, password hashing
│   ├── utils.py                # hash_password(), verify_password(), CSV helpers
│   ├── context_processors.py   # Frontend config injection
│   ├── color_translations.py   # German/CSS color name mappings
│   ├── services/
│   │   ├── scoring_service.py  # All 4 scoring algorithms + caching
│   │   ├── result_service.py   # Submission handling, optimistic locking
│   │   └── window_service.py   # Submission window state service
│   ├── views/
│   │   ├── auth.py             # Login/logout
│   │   ├── participant.py      # Dashboard, results, scoreboard, admin message API
│   │   ├── admin.py            # CSV upload
│   │   ├── myadmin.py          # Custom admin dashboard (CRUD for all entities)
│   │   └── health.py           # Health check endpoint
│   ├── management/commands/    # normalize_boulder_colors, reset_participants,
│   │                           # backup_database, restore_database
│   ├── migrations/             # 31 migrations; latest: 0031_add_submission_always_open
│   ├── tests.py                # 23 tests — core functionality
│   ├── test_forms.py           # 16 tests — ResultSubmissionForm validation
│   └── test_scoring_service.py # 76 tests — all scoring modes
├── web_project/
│   ├── settings/               # base.py, dev.py, prod.py, config.py
│   └── urls.py
├── templates/                  # Participant templates + admin overrides + custom admin
│   ├── includes/               # Shared fragments: admin_message_poll.html, header_back.html
│   ├── myadmin/                # Custom admin dashboard templates
│   │   ├── base.html, dashboard.html, _form_fields.html, _pagination.html, _messages.html
│   │   ├── _agegroup_picker.html  # Chip picker for M2M boulder↔age-group assignments
│   │   ├── agegroups/, results/, singletons/, exports/
│   │   ├── boulders/  list.html, form.html, _rows.html (AJAX partial)
│   │   ├── participants/  list.html, form.html, _rows.html (AJAX partial)
│   │   └── windows/  list.html, form.html
│   └── admin/                  # Custom admin base, index, system_status,
│       │                       # participant change_list
│       └── accounts/participant/change_list.html
├── static/
│   ├── js/
│   │   ├── participant_results_modular.js  # Entry point (modular)
│   │   ├── participant_results.js          # Legacy monolith (kept as fallback)
│   │   ├── cascade_logic.js                # Checkbox/attempt cascade enforcement
│   │   ├── countdown_timer.js              # Window start/end countdowns
│   │   ├── result_autosave.js              # AJAX save with version conflict handling
│   │   ├── offline_queue.js                # Auto-retry on reconnect via online/offline events
│   │   ├── window_poller.js                # Polls submission window state
│   │   └── admin_message_poll.js           # Broadcasts admin messages
│   └── css/
│       ├── participant_results.css
│       ├── participant_section_base.css
│       ├── scoreboard.css                  # Extracted from template (was inline)
│       ├── login.css
│       ├── admin_status.css
│       └── myadmin.css                     # Custom admin dashboard styles
├── DEPLOYMENT.md
├── TODO.md
└── dev_start.sh
```

**Removed**: `competition_admin/` app — fully deleted (was an empty proxy layer).

---

## Django Apps

### `accounts` (primary app)
All business logic, models, services, and views live here. No app-level URLs — all routes in root `urls.py`.

### `web_project` (project config)
Split settings: `base.py`, `dev.py`, `prod.py`, `config.py` (centralized timing constants).

---

## Domain Model

### Models (`accounts/models.py`) — 12 model classes

1. **AgeGroup** (min_age, max_age, gender)
   - n:m with Boulder
   - 1:n with Participant
   - Reassigns participants on save via signal (uses `bulk_update`)

2. **Participant** (username, password, DOB, gender, age_group, is_locked)
   - 1:n with Result
   - Session-based auth (no Django User model)
   - Password: PBKDF2 SHA256 via `hash_password()`, default = DOB as DDMMYYYY
   - `is_locked`: prevents login, hides from scoreboard, flushes active session

3. **Boulder** (label, color, zone_count, location)
   - n:m with AgeGroup
   - Color stored as CSS hex; closest CSS3 name computed on save
   - Color picker widget in admin; fuzzy color matching for imports

4. **Result** (participant, boulder, top/zone booleans, attempt counts, version)
   - Unique constraint: (participant, boulder)
   - Attempt fields: `attempts_top`, `attempts_zone1`, `attempts_zone2` (legacy `attempts` field removed in migration 0022)
   - `version = PositiveIntegerField(default=0)` — auto-incremented on each save
   - `updated_at = DateTimeField(null=True)` — only updated when result data fields actually change (migration 0030 replaced `auto_now=True`); `TRACKED_FIELDS` frozenset drives the comparison
   - `history = HistoricalRecords()` — full change audit trail via `django-simple-history`
   - `clean()` enforces zone hierarchy + attempt cascade at model level

5. **CompetitionSettings** (singleton)
   - `grading_system`: ifsc | point_based | point_based_dynamic | point_based_dynamic_attempts
   - All point/penalty values; `competition_date` for age calculations
   - Cached 5 minutes; invalidated on save
   - **Punktesystem** (proxy): admin-only proxy for point settings
   - **Wettkampfdatum** (proxy): admin-only proxy for competition date

6. **CountdownSettings** (singleton)
   - Controls the public countdown display (start time, colors, logo, show_preview_button)
   - Added in migrations 0024–0029

7. **SubmissionWindow** (time-based submission control)
   - n:m with AgeGroup
   - Active window checks with 30-second grace period

8. **AdminMessage** (singleton)
   - Broadcast to all participants via polling API
   - Custom background color; cached 5 minutes

9. **SiteSettings** (singleton)
   - Dashboard heading, greeting message (with version for acknowledgment tracking)
   - Help text and rulebook content
   - `submission_always_open` — global flag that bypasses all time-window checks for every participant (added in migration 0031)

10. **GreetingAcknowledgment**
    - 1:1 with Participant
    - Tracks which greeting version the participant has seen

---

## Services

### `scoring_service.py`
Four grading modes:
- **ifsc**: tops > zones > fewer attempts (no points)
- **point_based**: fixed points, attempt penalty, flash bonus, minimum enforcement
- **point_based_dynamic**: top points vary by % of participants who topped each boulder
- **point_based_dynamic_attempts**: dynamic points + attempt penalty

Scoreboard cached 5 seconds. `count_tops_per_boulder()` used for dynamic modes.

### `result_service.py`
- `extract_from_post()` — uses `ResultSubmissionForm` for validated parsing
- `normalize_submission()` — enforces zone hierarchy (top → zone2 → zone1)
- `handle_submission()` — transaction with `select_for_update()` + version check:
  - If `current_result.version != submission.version` → conflict, return server state
  - If versions match → update, increment version, invalidate scoreboard cache

### `window_service.py`
- `SubmissionWindowStatus` dataclass encapsulates all window state
- `get_submission_status(age_group)` → returns can_submit, active/next window, timestamps
  - Checks `SiteSettings.submission_always_open` first — if True, returns `can_submit=True` immediately regardless of windows
- `to_context_dict()` / `to_json_dict()` for views/AJAX responses
- Replaces 30+ lines of inline window logic in `participant_results` view

---

## Forms

### `ResultSubmissionForm`
- Validates zone booleans, attempt integers (non-negative), version integer
- `get_submitted_result()` returns a `SubmittedResult` dataclass
- Used by `ResultService.extract_from_post()`

---

## Key Patterns

- **Session-based auth**: No Django User; participants log in with username + DOB-derived password
- **Singleton models**: `CompetitionSettings`, `SiteSettings`, `AdminMessage` use `singleton_guard` field
- **Content caching**: Singleton models cache 5 minutes, auto-invalidated on save
- **Optimistic locking**: `Result.version` checked client↔server; `select_for_update()` for DB row lock
- **Audit trail**: `django-simple-history` on Result — all changes tracked with timestamp
- **Admin exports**: CSV (current + full history) and PDF standings per age group
- **Boulder zone normalization via signals**: `pre_save`/`post_save` on Boulder (in `signals.py`) detects `zone_count` changes and normalizes related Result zone fields via `QuerySet.update()` — bypasses `.save()` so `updated_at`, `version`, and `HistoricalRecords` are untouched
- **Bulk operations**: `bulk_update()` for age group reassignment (not N individual saves)
- **Targeted cache invalidation**: `cache.delete(key)` — never `cache.clear()`
- **Jitter on polling**: 5–10s random delay prevents thundering herd on window changes
- **AJAX partial rendering**: Participants and boulders list views return JSON (`rows` + `pagination` HTML partials) for `XMLHttpRequest` calls, enabling in-place filtering/sorting without full page reloads
- **AJAX locked-participant guard**: `participant_required` decorator returns `{"error": "locked", "redirect": ...}` JSON (HTTP 403) for AJAX requests instead of an HTML redirect

---

## JavaScript Architecture

The result submission UI is split into focused modules:

| Module | Responsibility |
|--------|---------------|
| `participant_results_modular.js` | Entry point, wires modules together |
| `cascade_logic.js` | Checkbox: top → zone2 → zone1; attempts_top ≥ attempts_zone2 ≥ attempts_zone1 |
| `countdown_timer.js` | Next window start / active window end countdowns |
| `result_autosave.js` | 5s debounced AJAX POST, sends version field, handles conflict response; amber toast when offline |
| `offline_queue.js` | `online`/`offline` events → auto-retry `queueSubmit` when connectivity returns |
| `window_poller.js` | 15s poll for window state changes, triggers page reload with jitter |
| `admin_message_poll.js` | 30s poll, dismissible modal with localStorage dedup |

The original `participant_results.js` monolith (530 lines) is kept as a fallback.

---

## Admin Interface

### Registered models
AgeGroup, Participant, Boulder, AdminMessage, Result, CompetitionSettings, SubmissionWindow, SiteSettings

### Key admin features
- **AgeGroup form includes boulder picker** — chip-style M2M selector (`_agegroup_picker.html`) manages the boulder↔age-group relationship directly from the age group form (and from boulder/window forms)
- **Lock/unlock participants** — flushes session, removes from scoreboard
- **Toggle global submission** — `/myadmin/zeitfenster/abgabe-umschalten/` toggles `SiteSettings.submission_always_open` (replaces bulk window creation)
- **Export results CSV** — current results with version and flash detection
- **Export history CSV** — full audit trail via django-simple-history
- **Export standings PDF** — formatted by age group, supports IFSC and point-based modes
- **Admin message broadcast** — instant dismissible modal to all logged-in participants
- **Color picker** on Boulder admin
- **System status page** — custom admin template at `/admin/system-status/`

### Cache behavior
- No `cache.clear()` calls — all invalidations are targeted by key or pattern

---

## Test Coverage

| File | Tests | Coverage area |
|------|-------|---------------|
| `accounts/tests.py` | 23 | Auth, caching, bulk actions, result tracking |
| `accounts/test_forms.py` | 16 | ResultSubmissionForm, cascade validation |
| `accounts/test_scoring_service.py` | 76 | All 4 scoring modes, flash, penalties, ranking |
| **Total** | **115** | |

**No JS tests** — `offline_queue.js`, `result_autosave.js`, `cascade_logic.js` are untested by automation.

---

## Database

SQLite in development (`db.sqlite3`), reset by default in `dev_start.sh`.
Production: SQLite (configurable for PostgreSQL via `DATABASE_URL`).
31 migrations; most recent: `0031_add_submission_always_open` (adds `SiteSettings.submission_always_open`); `0030_fix_result_updated_at_no_auto_now` (changes `Result.updated_at` from `auto_now` to nullable with smart tracking).

---

## Known Gaps / Remaining Work

1. **No JS test framework** — `offline_queue.js`, `result_autosave.js`, `cascade_logic.js` have no automated tests; Vitest + jsdom would fill this gap (intentionally skipped: project is build-tool free)

---

## Production Deployment

- External HTTPS proxy → VM nginx (port 80) → Gunicorn (Unix socket) → Django
- GitHub Actions: push to `deploy` branch triggers automated deployment
- Deployment user: `bouldercup-deploy` (minimal sudo permissions)
- Key files: `deploy.sh`, `.env` (SECRET_KEY, ALLOWED_HOSTS)
- `DEBUG = False`, session-based auth, CSRF trusted origins configured
