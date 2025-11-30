import csv
from datetime import datetime

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.text import slugify

from .forms import CSVUploadForm, LoginForm
from django.db import transaction

from .models import Boulder, Participant, Result


def _score_results(results):
    """Aggregate IFSC-style scoring metrics for a set of results."""
    tops = zones = top_attempts = zone_attempts = 0
    for res in results:
        if res.top:
            tops += 1
            top_attempts += res.attempts
        if res.zone2 or res.zone1:
            zones += 1
            zone_attempts += res.attempts
    return {
        "tops": tops,
        "zones": zones,
        "top_attempts": top_attempts,
        "zone_attempts": zone_attempts,
    }


def _rank_entries(entries):
    """Assign ranks based on IFSC sorting (tops, zones, attempts)."""

    def sort_key(entry):
        top_att = entry["top_attempts"] if entry["tops"] > 0 else float("inf")
        zone_att = entry["zone_attempts"] if entry["zones"] > 0 else float("inf")
        return (
            -entry["tops"],
            -entry["zones"],
            top_att,
            zone_att,
            entry["participant"].name.lower(),
        )

    entries.sort(key=sort_key)
    last_key = None
    current_rank = 0
    for idx, entry in enumerate(entries, start=1):
        key = sort_key(entry)
        if key != last_key:
            current_rank = idx
            last_key = key
        entry["rank"] = current_rank


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
        boulders = (
            Boulder.objects.filter(age_groups=participant.age_group).order_by("label")
            if participant.age_group_id
            else Boulder.objects.none()
        )
        existing_results = {
            r.boulder_id: r
            for r in Result.objects.filter(participant=participant, boulder__in=boulders)
        }
        for b in boulders:
            b.existing_result = existing_results.get(b.id)
        if request.method == "GET" and request.headers.get("x-requested-with") == "XMLHttpRequest":
            payload = {
                b.id: {
                    "top": res.top,
                    "zone2": res.zone2,
                    "zone1": res.zone1,
                    "attempts": res.attempts,
                    "updated_at": res.updated_at.timestamp(),
                }
                for b, res in ((b, b.existing_result) for b in boulders)
                if res is not None
            }
            return JsonResponse({"ok": True, "results": payload})
        if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
            payload = {}
            with transaction.atomic():
                for boulder in boulders:
                    attempts_raw = request.POST.get(f"attempts_{boulder.id}", "0")
                    try:
                        attempts = int(attempts_raw)
                    except (TypeError, ValueError):
                        attempts = 0
                    z1 = bool(request.POST.get(f"zone1_{boulder.id}", False))
                    z2 = bool(request.POST.get(f"zone2_{boulder.id}", False))
                    top = bool(request.POST.get(f"sent_{boulder.id}", False))
                    posted_ts_raw = request.POST.get(f"ts_{boulder.id}")
                    posted_ts = None
                    try:
                        posted_ts = float(posted_ts_raw) if posted_ts_raw not in (None, "") else None
                    except (TypeError, ValueError):
                        posted_ts = None

                    current_result = (
                        Result.objects.select_for_update()
                        .filter(participant=participant, boulder=boulder)
                        .first()
                    )
                    if current_result and posted_ts is not None:
                        # If client timestamp is older than the stored value, don't overwrite.
                        if current_result.updated_at.timestamp() - posted_ts > 0.0001:
                            payload[boulder.id] = {
                                "top": current_result.top,
                                "zone2": current_result.zone2,
                                "zone1": current_result.zone1,
                                "attempts": current_result.attempts,
                                "updated_at": current_result.updated_at.timestamp(),
                            }
                            continue

                    # Normalize based on zone availability and hierarchy.
                    if boulder.zone_count == 0:
                        # Only top available; zones are irrelevant.
                        z1 = False
                        z2 = False
                    elif boulder.zone_count == 1:
                        z2 = False
                        if top:
                            z1 = True
                        if z2 and not z1:
                            z2 = False
                        if not z1:
                            top = False
                    else:  # two zones available
                        if top:
                            z2 = True
                            z1 = True
                        if z2 and not z1:
                            z1 = True
                        if not z1:
                            z2 = False
                            top = False

                    if (top or z1 or z2) and attempts < 1:
                        attempts = 1
                    if attempts < 0:
                        attempts = 0

                    if not current_result:
                        current_result = Result(participant=participant, boulder=boulder)
                    current_result.zone1 = z1
                    current_result.zone2 = z2
                    current_result.top = top
                    current_result.attempts = attempts
                    current_result.save()
                    existing_results[boulder.id] = current_result
                    payload[boulder.id] = {
                        "top": current_result.top,
                        "zone2": current_result.zone2,
                        "zone1": current_result.zone1,
                        "attempts": current_result.attempts,
                        "updated_at": current_result.updated_at.timestamp(),
                    }
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
        entries = []
        if participant.age_group_id:
            boulders = Boulder.objects.filter(age_groups=participant.age_group).order_by("label")
            participants = (
                Participant.objects.filter(age_group=participant.age_group)
                .order_by("name")
                .prefetch_related("results")
            )
            results = (
                Result.objects.filter(participant__in=participants, boulder__in=boulders)
                .select_related("participant", "boulder")
            )
            result_map = {}
            for res in results:
                result_map.setdefault(res.participant_id, []).append(res)

            for p in participants:
                scored = _score_results(result_map.get(p.id, []))
                entries.append(
                    {
                        "participant": p,
                        **scored,
                    }
                )
            _rank_entries(entries)

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            payload = [
                {
                    "rank": e["rank"],
                    "name": e["participant"].name,
                    "tops": e["tops"],
                    "top_attempts": e["top_attempts"],
                    "zones": e["zones"],
                    "zone_attempts": e["zone_attempts"],
                }
                for e in entries
            ]
            return JsonResponse({"ok": True, "entries": payload})

        return render(
            request,
            "participant_live_scoreboard.html",
            {
                "participant": participant,
                "title": "Live Scoreboard",
                "entries": entries,
            },
        )
    return participant


def participant_rulebook(request):
    participant = _require_participant(request)
    if isinstance(participant, Participant):
        return render(
            request,
            "participant_rulebook.html",
            {"participant": participant, "title": "Regelwerk"},
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
