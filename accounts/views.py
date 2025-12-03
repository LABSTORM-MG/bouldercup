from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Callable, Iterable

from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.text import slugify

from .forms import CSVUploadForm, LoginForm
from .models import AgeGroup, Boulder, CompetitionSettings, Participant, Result, Rulebook
from .services import build_scoreboard_entries, group_results_by_participant


@dataclass
class SubmittedResult:
    zone1: bool
    zone2: bool
    top: bool
    attempts_zone1: int
    attempts_zone2: int
    attempts_top: int
    timestamp: float | None = None


def _get_participant_from_session(request: HttpRequest) -> Participant | None:
    participant_id = request.session.get("participant_id")
    if not participant_id:
        return None
    try:
        return Participant.objects.select_related("age_group").get(id=participant_id)
    except Participant.DoesNotExist:
        return None


def participant_required(
    view_func: Callable[[HttpRequest, Participant, ...], HttpResponse]
):
    """Redirect to login when no participant session is present."""

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        participant = _get_participant_from_session(request)
        if not participant:
            return redirect("login")
        return view_func(request, participant, *args, **kwargs)

    return wrapper


def _render_section(
    request: HttpRequest,
    participant: Participant,
    template: str,
    section_title: str,
    extra_context: dict | None = None,
) -> HttpResponse:
    context = {"participant": participant, "section_title": section_title}
    if extra_context:
        context.update(extra_context)
    return render(request, template, context)


def _active_competition_settings() -> CompetitionSettings | None:
    return CompetitionSettings.objects.order_by("-updated_at", "-id").first()


def _safe_int(value: str | None) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _parse_timestamp(raw_value: str | None) -> float | None:
    try:
        return float(raw_value) if raw_value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _extract_submission(post_data, boulder_id: int) -> SubmittedResult:
    return SubmittedResult(
        zone1=bool(post_data.get(f"zone1_{boulder_id}", False)),
        zone2=bool(post_data.get(f"zone2_{boulder_id}", False)),
        top=bool(post_data.get(f"sent_{boulder_id}", False)),
        attempts_zone1=_safe_int(post_data.get(f"attempts_zone1_{boulder_id}")),
        attempts_zone2=_safe_int(post_data.get(f"attempts_zone2_{boulder_id}")),
        attempts_top=_safe_int(post_data.get(f"attempts_top_{boulder_id}")),
        timestamp=_parse_timestamp(post_data.get(f"ts_{boulder_id}")),
    )


def _normalize_submission(boulder: Boulder, submission: SubmittedResult) -> SubmittedResult:
    """Enforce zone hierarchy and attempt defaults for a submitted result."""
    zone1 = submission.zone1
    zone2 = submission.zone2
    top = submission.top

    if boulder.zone_count == 0:
        zone1 = False
        zone2 = False
    elif boulder.zone_count == 1:
        zone2 = False
        if top:
            zone1 = True
        if not zone1:
            top = False
    else:
        if top:
            zone2 = True
            zone1 = True
        if zone2 and not zone1:
            zone1 = True
        if not zone1:
            zone2 = False
            top = False

    attempts_z1 = max(submission.attempts_zone1, 0)
    attempts_z2 = max(submission.attempts_zone2, 0)
    attempts_top = max(submission.attempts_top, 0)

    if zone1 and attempts_z1 < 1:
        attempts_z1 = 1
    if zone2 and attempts_z2 < 1:
        attempts_z2 = 1
    if top and attempts_top < 1:
        attempts_top = 1

    if top and attempts_top and attempts_z2 == 0 and boulder.zone_count >= 2:
        attempts_z2 = attempts_top
    if top and attempts_top and attempts_z1 == 0:
        attempts_z1 = attempts_top
    if zone2 and attempts_z2 and attempts_z1 == 0:
        attempts_z1 = attempts_z2

    return SubmittedResult(
        zone1=zone1,
        zone2=zone2,
        top=top,
        attempts_zone1=attempts_z1,
        attempts_zone2=attempts_z2,
        attempts_top=attempts_top,
        timestamp=submission.timestamp,
    )


def _result_payload(result: Result) -> dict:
    return {
        "top": result.top,
        "zone2": result.zone2,
        "zone1": result.zone1,
        "attempts_top": result.attempts_top,
        "attempts_zone2": result.attempts_zone2,
        "attempts_zone1": result.attempts_zone1,
        "updated_at": result.updated_at.timestamp(),
    }


def _load_existing_results(participant: Participant, boulders: Iterable[Boulder]) -> dict[int, Result]:
    return {
        res.boulder_id: res
        for res in Result.objects.filter(participant=participant, boulder__in=boulders)
    }


def _handle_results_submission(
    request: HttpRequest, participant: Participant, boulders: Iterable[Boulder]
) -> dict[int, dict]:
    payload: dict[int, dict] = {}
    with transaction.atomic():
        for boulder in boulders:
            submission = _normalize_submission(boulder, _extract_submission(request.POST, boulder.id))

            current_result = (
                Result.objects.select_for_update()
                .filter(participant=participant, boulder=boulder)
                .first()
            )
            if current_result and submission.timestamp is not None:
                if current_result.updated_at.timestamp() - submission.timestamp > 0.0001:
                    payload[boulder.id] = _result_payload(current_result)
                    continue

            if not current_result:
                current_result = Result(participant=participant, boulder=boulder)

            current_result.zone1 = submission.zone1
            current_result.zone2 = submission.zone2
            current_result.top = submission.top
            current_result.attempts_zone1 = submission.attempts_zone1
            current_result.attempts_zone2 = submission.attempts_zone2
            current_result.attempts_top = submission.attempts_top
            current_result.attempts = (
                submission.attempts_top
                if submission.top
                else (submission.attempts_zone2 if submission.zone2 else submission.attempts_zone1)
            )
            current_result.save()
            payload[boulder.id] = _result_payload(current_result)
    return payload


def login_view(request: HttpRequest) -> HttpResponse:
    message = ""
    form = LoginForm(request.POST or None)

    def _normalize_username(value: str) -> list[str]:
        raw = value.strip().lower()
        variants = [
            raw,
            raw.replace(" ", "").replace(".", "").replace("-", ""),
            slugify(raw).replace("-", ""),
            slugify(raw).replace("-", "."),
        ]
        seen: list[str] = []
        for variant in variants:
            if variant and variant not in seen:
                seen.append(variant)
        return seen

    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]

        participant = None
        for candidate in _normalize_username(username):
            try:
                participant = Participant.objects.select_related("age_group").get(username=candidate)
                break
            except Participant.DoesNotExist:
                continue

        if not participant:
            message = "Unbekannter Teilnehmer."
        elif participant.password == password:
            request.session["participant_id"] = participant.id
            return redirect("participant_dashboard")
        else:
            message = "Falsches Passwort."

    return render(
        request,
        "login.html",
        {
            "form": form,
            "message": message,
        },
    )


@staff_member_required
def upload_participants(request: HttpRequest) -> HttpResponse:
    """Allow staff to import participants from a CSV file."""

    results = {"created": 0, "skipped": []}
    form = CSVUploadForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        csv_file = form.cleaned_data["csv_file"]
        decoded = csv_file.read().decode("utf-8").splitlines()
        reader = csv.DictReader(decoded)

        for row_number, row in enumerate(reader, start=2):  # header is row 1
            first = _pick_value(row, "first_name", "Vorname")
            last = _pick_value(row, "surname", "Nachname")
            dob_value = _pick_value(row, "date_of_birth", "Geburtsdatum")
            gender_value = _pick_value(row, "gender", "Geschlecht").lower()

            if not (first and last and dob_value and gender_value):
                results["skipped"].append(f"Zeile {row_number}: fehlende Pflichtfelder.")
                continue

            dob = _parse_date(dob_value)
            if not dob:
                results["skipped"].append(
                    f"Zeile {row_number}: ungültiges Geburtsdatum '{dob_value}'."
                )
                continue

            gender = _normalize_gender(gender_value)
            if not gender:
                results["skipped"].append(
                    f"Zeile {row_number}: unbekanntes Geschlecht '{gender_value}'."
                )
                continue

            username = _unique_username(f"{first}.{last}".lower())
            password = dob.strftime("%d%m%Y")
            full_name = f"{first} {last}"

            if Participant.objects.filter(name__iexact=full_name, date_of_birth=dob).exists():
                results["skipped"].append(
                    f"Zeile {row_number}: Teilnehmer {full_name} bereits vorhanden."
                )
                continue

            Participant.objects.create(
                username=username,
                password=password,
                name=full_name,
                date_of_birth=dob,
                gender=gender,
            )
            results["created"] += 1

    return render(
        request,
        "upload_participants.html",
        {
            "form": form,
            "results": results,
            "admin_home": reverse("admin:index"),
        },
    )


@participant_required
def participant_dashboard(request: HttpRequest, participant: Participant) -> HttpResponse:
    return render(
        request,
        "participant_dashboard.html",
        {"participant": participant},
    )


@participant_required
def participant_support(request: HttpRequest, participant: Participant) -> HttpResponse:
    return _render_section(
        request,
        participant,
        "participant_support.html",
        "Hilfe & Support",
    )


@participant_required
def participant_settings(request: HttpRequest, participant: Participant) -> HttpResponse:
    return _render_section(
        request,
        participant,
        "participant_settings.html",
        "Einstellungen",
    )


@participant_required
def participant_results(request: HttpRequest, participant: Participant) -> HttpResponse:
    boulders = (
        Boulder.objects.filter(age_groups=participant.age_group).order_by("label")
        if participant.age_group_id
        else Boulder.objects.none()
    )
    existing_results = _load_existing_results(participant, boulders)
    for boulder in boulders:
        boulder.existing_result = existing_results.get(boulder.id)

    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    if request.method == "GET" and is_ajax:
        payload = {
            boulder.id: _result_payload(res)
            for boulder, res in ((b, b.existing_result) for b in boulders)
            if res is not None
        }
        return JsonResponse({"ok": True, "results": payload})

    if request.method == "POST":
        payload = _handle_results_submission(request, participant, boulders)
        return JsonResponse({"ok": True, "results": payload})

    return render(
        request,
        "participant_results.html",
        {
            "participant": participant,
            "title": "Ergebnisse eintragen",
            "boulders": boulders,
        },
    )


@participant_required
def participant_run_plan(request: HttpRequest, participant: Participant) -> HttpResponse:
    return _render_section(
        request,
        participant,
        "participant_run_plan.html",
        "Laufplan",
    )


@participant_required
def participant_live_scoreboard(request: HttpRequest, participant: Participant) -> HttpResponse:
    settings_obj = _active_competition_settings()
    grading_system = settings_obj.grading_system if settings_obj else "ifsc"

    age_groups = list(
        AgeGroup.objects.filter(participants__isnull=False).distinct().order_by("name")
    )
    requested_group_id = request.GET.get("age_group")
    selected_group = None
    show_all = requested_group_id == "all"
    if requested_group_id and not show_all:
        selected_group = next((g for g in age_groups if str(g.id) == requested_group_id), None)
    if not selected_group and not show_all:
        selected_group = participant.age_group if participant.age_group_id else (age_groups[0] if age_groups else None)

    entries: list[dict] = []
    if selected_group or show_all:
        boulders = (
            Boulder.objects.filter(age_groups=selected_group).order_by("label")
            if selected_group
            else Boulder.objects.all().order_by("label")
        )
        participants = list(
            Participant.objects.filter(age_group__in=[selected_group] if selected_group else age_groups).order_by(
                "name"
            )
        )
        results = (
            Result.objects.filter(participant__in=participants, boulder__in=boulders)
            .select_related("participant", "boulder")
        )
        result_map = group_results_by_participant(results)
        entries = build_scoreboard_entries(participants, result_map, grading_system, settings_obj)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        payload = [
            {
                "rank": entry["rank"],
                "name": entry["participant"].name,
                "tops": entry.get("tops", 0),
                "top_attempts": entry.get("top_attempts", 0),
                "zones": entry.get("zones", 0),
                "zone_attempts": entry.get("zone_attempts", 0),
                "points": entry.get("points", 0),
            }
            for entry in entries
        ]
        return JsonResponse({"ok": True, "entries": payload, "grading": grading_system})

    return render(
        request,
        "participant_live_scoreboard.html",
        {
            "participant": participant,
            "title": "Live-Ergebnisse",
            "entries": entries,
            "age_groups": age_groups,
            "selected_group": selected_group,
            "grading_system": grading_system,
        },
    )


@participant_required
def participant_rulebook(request: HttpRequest, participant: Participant) -> HttpResponse:
    settings_obj = _active_competition_settings()
    grading_system = settings_obj.grading_system if settings_obj else "ifsc"
    rulebook = Rulebook.objects.order_by("-updated_at", "-id").first()
    rules_text = rulebook.content if rulebook else ""
    return render(
        request,
        "participant_rulebook.html",
        {
            "participant": participant,
            "title": "Regelwerk",
            "grading_system": grading_system,
            "rules_text": rules_text,
        },
    )


def _parse_date(value: str):
    formats = ("%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d")
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _normalize_gender(value: str):
    mapping = {
        "m": "male",
        "male": "male",
        "w": "female",
        "f": "female",
        "female": "female",
        "weiblich": "female",
        "männlich": "male",
        "divers": "mixed",
        "mixed": "mixed",
        "other": "mixed",
    }
    return mapping.get(value)


def _unique_username(base: str) -> str:
    cleaned = slugify(base) or "teilnehmer"
    candidate = cleaned
    counter = 1
    while Participant.objects.filter(username=candidate).exists():
        counter += 1
        candidate = f"{cleaned}{counter}"
    return candidate


def _pick_value(row, *keys):
    for key in keys:
        value = row.get(key)
        if value is not None and value.strip():
            return value.strip()
    return ""
