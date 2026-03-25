"""
Custom admin dashboard views -- replaces Django admin UI at /myadmin/.
Auth: Django's is_staff flag, same session as /admin/.
"""
import csv
import io
import logging
import zipfile
from functools import wraps

from django import forms
from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..forms import CSVUploadForm
from ..forms_admin import BoulderAdminForm
from ..models import (
    AgeGroup,
    AdminMessage,
    Boulder,
    CompetitionSettings,
    Participant,
    Result,
    SubmissionWindow,
)
from ..utils import hash_password, normalize_gender, parse_date, pick_value, unique_username

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------

def myadmin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return redirect("/admin/login/?next=" + request.path)
        return view_func(request, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# CSS class helper
# ---------------------------------------------------------------------------

def _add_ma_classes(form):
    """Apply myadmin CSS classes to all form widgets."""
    for field in form.fields.values():
        w = field.widget
        if isinstance(w, forms.CheckboxInput):
            pass  # styled via CSS selector
        elif isinstance(w, forms.Textarea):
            w.attrs.setdefault("class", "ma-textarea")
        elif isinstance(w, forms.SelectMultiple):
            w.attrs.setdefault("class", "ma-select-full")
            w.attrs.setdefault("size", "6")
        elif isinstance(w, forms.Select):
            w.attrs.setdefault("class", "ma-select-full")
        else:
            existing = w.attrs.get("class", "")
            if "ma-input" not in existing:
                w.attrs["class"] = (existing + " ma-input").strip()
    return form


# ---------------------------------------------------------------------------
# Forms (no ReadOnlyPasswordHashField)
# ---------------------------------------------------------------------------

class ParticipantAddForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        label="Geburtsdatum",
        input_formats=["%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d"],
        widget=forms.DateInput(
            format="%d.%m.%Y",
            attrs={"placeholder": "TT.MM.JJJJ", "type": "date", "class": "ma-input"},
        ),
    )
    new_password = forms.CharField(
        label="Passwort",
        required=True,
        help_text="Standard: Geburtsdatum TTMMJJJJ. Wird automatisch gehasht.",
        widget=forms.TextInput(attrs={"placeholder": "z.B. 01012000", "class": "ma-input"}),
    )

    class Meta:
        model = Participant
        fields = ("name", "date_of_birth", "gender", "username", "age_group", "is_locked")

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.password = hash_password(self.cleaned_data["new_password"])
        if commit:
            obj.save()
            obj.assign_age_group()
            obj.save()
        return obj


class ParticipantEditForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        label="Geburtsdatum",
        input_formats=["%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d"],
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={"type": "date", "class": "ma-input"},
        ),
    )
    new_password = forms.CharField(
        label="Neues Passwort",
        required=False,
        help_text="Nur ausfullen wenn Passwort geaendert werden soll.",
        widget=forms.TextInput(
            attrs={"placeholder": "Leer lassen = unveraendert", "class": "ma-input"}
        ),
    )

    class Meta:
        model = Participant
        fields = ("name", "date_of_birth", "gender", "username", "age_group", "is_locked")

    def save(self, commit=True):
        obj = super().save(commit=False)
        new_pw = self.cleaned_data.get("new_password")
        if new_pw:
            obj.password = hash_password(new_pw)
        if commit:
            obj.save()
            obj.assign_age_group()
            obj.save()
        return obj


class AgeGroupForm(forms.ModelForm):
    class Meta:
        model = AgeGroup
        fields = ("name", "min_age", "max_age", "gender")


class AdminMessageForm(forms.ModelForm):
    background_color = forms.CharField(
        widget=forms.TextInput(attrs={"type": "color", "class": "ma-input"}),
        label="Hintergrundfarbe",
    )

    class Meta:
        model = AdminMessage
        fields = ("heading", "content", "background_color")


class WettkampfdatumForm(forms.ModelForm):
    class Meta:
        model = CompetitionSettings
        fields = ("competition_date",)
        widgets = {
            "competition_date": forms.DateInput(attrs={"type": "date", "class": "ma-input"}),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _paginate(queryset, request, per_page=50):
    paginator = Paginator(queryset, per_page)
    page = request.GET.get("page", 1)
    return paginator.get_page(page)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@myadmin_required
def myadmin_dashboard(request):
    competition_settings = CompetitionSettings.objects.filter(singleton_guard=True).first()
    active_windows = SubmissionWindow.objects.filter(
        submission_start__lte=timezone.now(),
        submission_end__gte=timezone.now(),
    )
    return render(request, "myadmin/dashboard.html", {
        "page_title": "Dashboard",
        "participant_count": Participant.objects.count(),
        "boulder_count": Boulder.objects.count(),
        "result_count": Result.objects.count(),
        "agegroup_count": AgeGroup.objects.count(),
        "active_windows": active_windows,
        "competition_date": competition_settings.competition_date if competition_settings else None,
        "locked_count": Participant.objects.filter(is_locked=True).count(),
    })


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@myadmin_required
def myadmin_logout(request):
    auth_logout(request)
    return redirect("/admin/login/")


# ---------------------------------------------------------------------------
# Participants
# ---------------------------------------------------------------------------

@myadmin_required
def myadmin_participants(request):
    qs = Participant.objects.select_related("age_group").order_by("name")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(username__icontains=q))

    gender = request.GET.get("gender", "")
    if gender:
        qs = qs.filter(gender=gender)

    age_group_id = request.GET.get("age_group", "")
    if age_group_id:
        qs = qs.filter(age_group_id=age_group_id)

    locked = request.GET.get("locked", "")
    if locked == "1":
        qs = qs.filter(is_locked=True)
    elif locked == "0":
        qs = qs.filter(is_locked=False)

    sort = request.GET.get("sort", "name")
    direction = request.GET.get("dir", "asc")
    allowed_sorts = {"name", "username", "gender", "age_group__name", "is_locked", "created_at"}
    if sort in allowed_sorts:
        qs = qs.order_by(("-" if direction == "desc" else "") + sort)

    page_obj = _paginate(qs, request)
    age_groups = AgeGroup.objects.all().order_by("name")

    return render(request, "myadmin/participants/list.html", {
        "page_title": "Teilnehmer",
        "page_obj": page_obj,
        "age_groups": age_groups,
        "q": q,
        "filter_gender": gender,
        "filter_age_group": age_group_id,
        "filter_locked": locked,
        "sort": sort,
        "dir": direction,
    })


@myadmin_required
def myadmin_participant_add(request):
    if request.method == "POST":
        form = ParticipantAddForm(request.POST)
        if form.is_valid():
            p = form.save()
            messages.success(request, "Teilnehmer " + p.name + " wurde angelegt.")
            return redirect("myadmin:participants")
    else:
        form = ParticipantAddForm()
    _add_ma_classes(form)
    return render(request, "myadmin/participants/form.html", {
        "form": form,
        "is_add": True,
        "page_title": "Teilnehmer anlegen",
    })


@myadmin_required
def myadmin_participant_edit(request, pk):
    participant = get_object_or_404(Participant, pk=pk)
    if request.method == "POST":
        form = ParticipantEditForm(request.POST, instance=participant)
        if form.is_valid():
            form.save()
            messages.success(request, participant.name + " gespeichert.")
            return redirect("myadmin:participants")
    else:
        form = ParticipantEditForm(instance=participant)
    _add_ma_classes(form)
    return render(request, "myadmin/participants/form.html", {
        "form": form,
        "participant": participant,
        "is_add": False,
        "page_title": participant.name + " bearbeiten",
    })


@myadmin_required
def myadmin_participant_delete(request, pk):
    participant = get_object_or_404(Participant, pk=pk)
    if request.method == "POST":
        name = participant.name
        participant.delete()
        messages.success(request, "Teilnehmer " + name + " wurde geloescht.")
        return redirect("myadmin:participants")
    return render(request, "myadmin/participants/delete_confirm.html", {
        "participant": participant,
        "page_title": participant.name + " loeschen?",
    })


@myadmin_required
def myadmin_participant_import(request):
    results = {"created": 0, "skipped": []}
    form = CSVUploadForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        csv_file = form.cleaned_data["csv_file"]
        decoded = csv_file.read().decode("utf-8").splitlines()
        reader = csv.DictReader(decoded)

        for row_number, row in enumerate(reader, start=2):
            first = pick_value(row, "first_name", "Vorname")
            last = pick_value(row, "surname", "Nachname")
            dob_value = pick_value(row, "date_of_birth", "Geburtsdatum")
            gender_value = pick_value(row, "gender", "Geschlecht").lower()

            if not (first and last and dob_value and gender_value):
                results["skipped"].append("Zeile " + str(row_number) + ": fehlende Pflichtfelder.")
                continue

            dob = parse_date(dob_value)
            if not dob:
                results["skipped"].append(
                    "Zeile " + str(row_number) + ": ungueltig. Geburtsdatum '" + dob_value + "'."
                )
                continue

            gender = normalize_gender(gender_value)
            if not gender:
                results["skipped"].append(
                    "Zeile " + str(row_number) + ": unbekanntes Geschlecht '" + gender_value + "'."
                )
                continue

            username = unique_username((first + "." + last).lower())
            password = hash_password(dob.strftime("%d%m%Y"))
            full_name = first + " " + last

            if Participant.objects.filter(name__iexact=full_name, date_of_birth=dob).exists():
                results["skipped"].append("Zeile " + str(row_number) + ": " + full_name + " bereits vorhanden.")
                continue

            Participant.objects.create(
                username=username,
                password=password,
                name=full_name,
                date_of_birth=dob,
                gender=gender,
            )
            results["created"] += 1

        if results["created"]:
            messages.success(request, str(results["created"]) + " Teilnehmer importiert.")
        if results["skipped"]:
            messages.warning(request, str(len(results["skipped"])) + " Zeilen uebersprungen.")

    return render(request, "myadmin/participants/import.html", {
        "form": form,
        "results": results,
        "page_title": "Teilnehmer importieren",
    })


@myadmin_required
def myadmin_participant_action(request):
    """Bulk lock/unlock/walking-sheets for selected participants."""
    if request.method != "POST":
        return redirect("myadmin:participants")

    action = request.POST.get("action")
    ids = request.POST.getlist("selected_ids")
    if not ids:
        messages.warning(request, "Keine Teilnehmer ausgewaehlt.")
        return redirect("myadmin:participants")

    qs = Participant.objects.filter(pk__in=ids)

    if action == "lock":
        from django.contrib.sessions.models import Session
        from ..services.scoring_service import ScoringService
        participant_ids = list(qs.values_list("id", flat=True))
        count = qs.update(is_locked=True)
        sessions_deleted = 0
        for session in Session.objects.all():
            if session.get_decoded().get("participant_id") in participant_ids:
                session.delete()
                sessions_deleted += 1
        ScoringService.invalidate_all_scoreboards()
        messages.warning(
            request,
            str(count) + " Teilnehmer gesperrt, " + str(sessions_deleted) + " Sitzungen beendet."
        )

    elif action == "unlock":
        from ..services.scoring_service import ScoringService
        count = qs.update(is_locked=False)
        ScoringService.invalidate_all_scoreboards()
        messages.success(request, str(count) + " Teilnehmer entsperrt.")

    elif action == "walking_sheets":
        from ..admin import generate_walking_sheet_pdf
        participants = list(qs.select_related("age_group"))
        if len(participants) == 1:
            pdf_bytes = generate_walking_sheet_pdf(participants[0])
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            filename = "laufzettel_" + participants[0].username + ".pdf"
            response["Content-Disposition"] = "attachment; filename=\"" + filename + "\""
            return response
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in participants:
                zf.writestr("laufzettel_" + p.username + ".pdf", generate_walking_sheet_pdf(p))
        buf.seek(0)
        response = HttpResponse(buf.read(), content_type="application/zip")
        response["Content-Disposition"] = "attachment; filename=\"laufzettel.zip\""
        return response

    return redirect("myadmin:participants")


# ---------------------------------------------------------------------------
# Boulders
# ---------------------------------------------------------------------------

@myadmin_required
def myadmin_boulders(request):
    qs = Boulder.objects.prefetch_related("age_groups").order_by("label")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(label__icontains=q) | Q(color__icontains=q) | Q(location__icontains=q))

    zone_count = request.GET.get("zone_count", "")
    if zone_count in ("0", "1", "2"):
        qs = qs.filter(zone_count=int(zone_count))

    page_obj = _paginate(qs, request)
    return render(request, "myadmin/boulders/list.html", {
        "page_title": "Boulder",
        "page_obj": page_obj,
        "q": q,
        "filter_zone_count": zone_count,
    })


@myadmin_required
def myadmin_boulder_add(request):
    if request.method == "POST":
        form = BoulderAdminForm(request.POST)
        if form.is_valid():
            b = form.save()
            messages.success(request, "Boulder " + b.label + " wurde angelegt.")
            return redirect("myadmin:boulders")
    else:
        form = BoulderAdminForm()
    _add_ma_classes(form)
    return render(request, "myadmin/boulders/form.html", {
        "form": form,
        "is_add": True,
        "page_title": "Boulder anlegen",
    })


@myadmin_required
def myadmin_boulder_edit(request, pk):
    boulder = get_object_or_404(Boulder, pk=pk)
    if request.method == "POST":
        form = BoulderAdminForm(request.POST, instance=boulder)
        if form.is_valid():
            form.save()
            messages.success(request, "Boulder " + boulder.label + " gespeichert.")
            return redirect("myadmin:boulders")
    else:
        form = BoulderAdminForm(instance=boulder)
    _add_ma_classes(form)
    return render(request, "myadmin/boulders/form.html", {
        "form": form,
        "boulder": boulder,
        "is_add": False,
        "page_title": "Boulder " + boulder.label + " bearbeiten",
    })


@myadmin_required
def myadmin_boulder_delete(request, pk):
    boulder = get_object_or_404(Boulder, pk=pk)
    if request.method == "POST":
        label = boulder.label
        boulder.delete()
        messages.success(request, "Boulder " + label + " wurde geloescht.")
        return redirect("myadmin:boulders")
    return render(request, "myadmin/boulders/delete_confirm.html", {
        "boulder": boulder,
        "page_title": "Boulder " + boulder.label + " loeschen?",
    })


# ---------------------------------------------------------------------------
# AgeGroups
# ---------------------------------------------------------------------------

@myadmin_required
def myadmin_agegroups(request):
    qs = AgeGroup.objects.annotate(participant_count=Count("participant")).order_by("name")
    page_obj = _paginate(qs, request)
    return render(request, "myadmin/agegroups/list.html", {
        "page_title": "Altersgruppen",
        "page_obj": page_obj,
    })


@myadmin_required
def myadmin_agegroup_add(request):
    if request.method == "POST":
        form = AgeGroupForm(request.POST)
        if form.is_valid():
            ag = form.save()
            messages.success(request, "Altersgruppe " + ag.name + " wurde angelegt.")
            return redirect("myadmin:agegroups")
    else:
        form = AgeGroupForm()
    _add_ma_classes(form)
    return render(request, "myadmin/agegroups/form.html", {
        "form": form,
        "is_add": True,
        "page_title": "Altersgruppe anlegen",
    })


@myadmin_required
def myadmin_agegroup_edit(request, pk):
    agegroup = get_object_or_404(AgeGroup, pk=pk)
    if request.method == "POST":
        form = AgeGroupForm(request.POST, instance=agegroup)
        if form.is_valid():
            form.save()
            messages.success(request, agegroup.name + " gespeichert.")
            return redirect("myadmin:agegroups")
    else:
        form = AgeGroupForm(instance=agegroup)
    _add_ma_classes(form)
    return render(request, "myadmin/agegroups/form.html", {
        "form": form,
        "agegroup": agegroup,
        "is_add": False,
        "page_title": agegroup.name + " bearbeiten",
    })


@myadmin_required
def myadmin_agegroup_delete(request, pk):
    agegroup = get_object_or_404(AgeGroup, pk=pk)
    if request.method == "POST":
        name = agegroup.name
        agegroup.delete()
        messages.success(request, "Altersgruppe " + name + " wurde geloescht.")
        return redirect("myadmin:agegroups")
    return render(request, "myadmin/agegroups/delete_confirm.html", {
        "agegroup": agegroup,
        "participant_count": agegroup.participant_set.count(),
        "page_title": agegroup.name + " loeschen?",
    })


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

@myadmin_required
def myadmin_admin_message(request):
    obj, _ = AdminMessage.objects.get_or_create(singleton_guard=True)
    form = AdminMessageForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Admin-Nachricht gespeichert.")
        return redirect("myadmin:admin_message")
    _add_ma_classes(form)
    return render(request, "myadmin/singletons/admin_message.html", {
        "form": form,
        "page_title": "Admin-Nachricht",
    })


@myadmin_required
def myadmin_wettkampfdatum(request):
    obj, _ = CompetitionSettings.objects.get_or_create(singleton_guard=True)
    form = WettkampfdatumForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Wettkampfdatum gespeichert.")
        return redirect("myadmin:wettkampfdatum")
    _add_ma_classes(form)
    return render(request, "myadmin/singletons/wettkampfdatum.html", {
        "form": form,
        "page_title": "Wettkampfdatum",
    })
