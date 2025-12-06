import csv

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse

from ..forms import CSVUploadForm
from ..models import Participant
from ..utils import parse_date, normalize_gender, unique_username, pick_value


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
            first = pick_value(row, "first_name", "Vorname")
            last = pick_value(row, "surname", "Nachname")
            dob_value = pick_value(row, "date_of_birth", "Geburtsdatum")
            gender_value = pick_value(row, "gender", "Geschlecht").lower()

            if not (first and last and dob_value and gender_value):
                results["skipped"].append(f"Zeile {row_number}: fehlende Pflichtfelder.")
                continue

            dob = parse_date(dob_value)
            if not dob:
                results["skipped"].append(
                    f"Zeile {row_number}: ungültiges Geburtsdatum '{dob_value}'."
                )
                continue

            gender = normalize_gender(gender_value)
            if not gender:
                results["skipped"].append(
                    f"Zeile {row_number}: unbekanntes Geschlecht '{gender_value}'."
                )
                continue

            username = unique_username(f"{first}.{last}".lower())
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
