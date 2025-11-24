import csv
from datetime import datetime

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.text import slugify

from .forms import CSVUploadForm, LoginForm
from .models import Participant


def login_view(request):
    message = ""
    form = LoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]

        try:
            participant = Participant.objects.select_related("age_group").get(
                username=username
            )
        except Participant.DoesNotExist:
            message = "Unbekannter Teilnehmer."
        else:
            if participant.password == password:
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
def upload_participants(request):
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
                results["skipped"].append(
                    f"Zeile {row_number}: fehlende Pflichtfelder."
                )
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
            password = dob.strftime("%d%m%Y")  # simple reproducible password

            full_name = f"{first} {last}"

            if Participant.objects.filter(
                name__iexact=full_name, date_of_birth=dob
            ).exists():
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


def participant_dashboard(request):
    participant = _require_participant(request)
    if isinstance(participant, Participant):
        return render(
            request,
            "participant_dashboard.html",
            {
                "participant": participant,
            },
        )
    return participant  # redirect


def participant_support(request):
    participant = _require_participant(request)
    if isinstance(participant, Participant):
        return render(
            request,
            "participant_support.html",
            {
                "participant": participant,
            },
        )
    return participant


def participant_settings(request):
    participant = _require_participant(request)
    if isinstance(participant, Participant):
        return render(
            request,
            "participant_settings.html",
            {
                "participant": participant,
            },
        )
    return participant


def participant_results(request):
    participant = _require_participant(request)
    if isinstance(participant, Participant):
        return render(
            request,
            "participant_results.html",
            {"participant": participant, "title": "Ergebnisse eintragen"},
        )
    return participant


def participant_run_plan(request):
    participant = _require_participant(request)
    if isinstance(participant, Participant):
        return render(
            request,
            "participant_run_plan.html",
            {"participant": participant, "title": "Laufplan"},
        )
    return participant


def participant_live_scoreboard(request):
    participant = _require_participant(request)
    if isinstance(participant, Participant):
        return render(
            request,
            "participant_live_scoreboard.html",
            {"participant": participant, "title": "Live Scoreboard"},
        )
    return participant


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


def _require_participant(request):
    participant_id = request.session.get("participant_id")
    if not participant_id:
        return redirect("login")
    try:
        return Participant.objects.select_related("age_group").get(
            id=participant_id
        )
    except Participant.DoesNotExist:
        return redirect("login")
