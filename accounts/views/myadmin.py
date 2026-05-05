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
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django_ckeditor_5.widgets import CKEditor5Widget
from django.contrib.auth import logout as auth_logout
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..forms import CSVUploadForm
from ..forms_admin import BoulderAdminForm, SubmissionWindowAdminForm
from ..models import (
    AgeGroup,
    AdminMessage,
    Boulder,
    CompetitionSettings,
    CountdownSettings,
    Participant,
    Result,
    SiteSettings,
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
    boulders = forms.ModelMultipleChoiceField(
        queryset=Boulder.objects.order_by("label"),
        required=False,
        label="Boulder",
        help_text="Boulder, die dieser Altersgruppe zugewiesen sind.",
    )

    class Meta:
        model = AgeGroup
        fields = ("name", "min_age", "max_age", "gender")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["boulders"].initial = self.instance.boulders.values_list("pk", flat=True)

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            self._save_boulders(instance)
        return instance

    def _save_boulders(self, instance):
        selected = set(self.cleaned_data["boulders"].values_list("pk", flat=True))
        for boulder in Boulder.objects.filter(age_groups=instance):
            if boulder.pk not in selected:
                boulder.age_groups.remove(instance)
        for boulder in self.cleaned_data["boulders"]:
            boulder.age_groups.add(instance)


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

    ctx = {
        "page_title": "Teilnehmer",
        "page_obj": page_obj,
        "age_groups": age_groups,
        "q": q,
        "filter_gender": gender,
        "filter_age_group": age_group_id,
        "filter_locked": locked,
        "sort": sort,
        "dir": direction,
    }

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "rows": render_to_string("myadmin/participants/_rows.html", ctx, request),
            "pagination": render_to_string("myadmin/_pagination.html", ctx, request),
            "total": page_obj.paginator.count,
        })

    return render(request, "myadmin/participants/list.html", ctx)


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
        from ..services.scoring_service import ScoringService
        count = qs.update(is_locked=True)
        ScoringService.invalidate_all_scoreboards()
        messages.warning(request, str(count) + " Teilnehmer gesperrt.")

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
    ctx = {
        "page_title": "Boulder",
        "page_obj": page_obj,
        "q": q,
        "filter_zone_count": zone_count,
    }

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "rows": render_to_string("myadmin/boulders/_rows.html", ctx, request),
            "pagination": render_to_string("myadmin/_pagination.html", ctx, request),
            "total": page_obj.paginator.count,
        })

    return render(request, "myadmin/boulders/list.html", ctx)


def _agegroup_picker_ctx(instance=None):
    """Return context for the age-group chip picker."""
    agegroups_all = AgeGroup.objects.order_by("name")
    selected_pks = set(instance.age_groups.values_list("pk", flat=True)) if instance and instance.pk else set()
    return {"agegroups_all": agegroups_all, "selected_agegroup_pks": selected_pks}


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
        **_agegroup_picker_ctx(),
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
        **_agegroup_picker_ctx(boulder),
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
    qs = AgeGroup.objects.annotate(participant_count=Count("participants")).order_by("name")
    page_obj = _paginate(qs, request)
    return render(request, "myadmin/agegroups/list.html", {
        "page_title": "Altersgruppen",
        "page_obj": page_obj,
    })


def _agegroup_form_context(form, request, extra=None):
    """Build shared context for the age group add/edit views."""
    if request.method == "POST":
        selected_pks = set(int(v) for v in request.POST.getlist("boulders") if v.isdigit())
    else:
        initial = form.fields["boulders"].initial
        selected_pks = set(initial) if initial else set()
    _add_ma_classes(form)
    ctx = {
        "form": form,
        "boulders_all": Boulder.objects.order_by("label"),
        "selected_boulder_pks": selected_pks,
    }
    if extra:
        ctx.update(extra)
    return ctx


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
    return render(request, "myadmin/agegroups/form.html",
        _agegroup_form_context(form, request, {"is_add": True, "page_title": "Altersgruppe anlegen"}))


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
    return render(request, "myadmin/agegroups/form.html",
        _agegroup_form_context(form, request, {
            "agegroup": agegroup,
            "is_add": False,
            "page_title": agegroup.name + " bearbeiten",
        }))


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
        "participant_count": agegroup.participants.count(),
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

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

class ResultEditForm(forms.ModelForm):
    class Meta:
        model = Result
        fields = ("top", "zone2", "zone1", "attempts_top", "attempts_zone2", "attempts_zone1")

    def clean(self):
        cleaned_data = super().clean()
        # Re-use model's clean() logic via full_clean on a temp instance
        return cleaned_data


@myadmin_required
def myadmin_results(request):
    qs = Result.objects.select_related(
        "participant", "participant__age_group", "boulder"
    ).order_by("participant__age_group__name", "participant__name", "boulder__label")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(participant__name__icontains=q) | Q(boulder__label__icontains=q)
        )

    age_group_id = request.GET.get("age_group", "")
    if age_group_id:
        qs = qs.filter(participant__age_group_id=age_group_id)

    boulder_id = request.GET.get("boulder", "")
    if boulder_id:
        qs = qs.filter(boulder_id=boulder_id)

    top_filter = request.GET.get("top", "")
    if top_filter == "1":
        qs = qs.filter(top=True)
    elif top_filter == "0":
        qs = qs.filter(top=False)

    page_obj = _paginate(qs, request, per_page=100)
    age_groups = AgeGroup.objects.order_by("name")
    boulders = Boulder.objects.order_by("label")

    return render(request, "myadmin/results/list.html", {
        "page_title": "Ergebnisse",
        "page_obj": page_obj,
        "age_groups": age_groups,
        "boulders": boulders,
        "q": q,
        "filter_age_group": age_group_id,
        "filter_boulder": boulder_id,
        "filter_top": top_filter,
        "total_count": qs.count(),
    })


@myadmin_required
def myadmin_result_edit(request, pk):
    result = get_object_or_404(
        Result.objects.select_related("participant", "boulder"), pk=pk
    )
    if request.method == "POST":
        form = ResultEditForm(request.POST, instance=result)
        if form.is_valid():
            old = Result.objects.get(pk=pk)
            changes = []
            for field in ["top", "zone2", "zone1", "attempts_top", "attempts_zone2", "attempts_zone1"]:
                old_val = getattr(old, field)
                new_val = form.cleaned_data.get(field)
                if old_val != new_val:
                    changes.append(field + ": " + str(old_val) + " -> " + str(new_val))
            obj = form.save(commit=False)
            try:
                obj.full_clean()
            except Exception as e:
                form.add_error(None, str(e))
            else:
                obj.save()
                if changes:
                    logger.warning(
                        "Admin result change by " + request.user.username + ": "
                        + result.participant.username + " / " + result.boulder.label
                        + " -- " + ", ".join(changes)
                    )
                messages.success(request, "Ergebnis gespeichert.")
                return redirect("myadmin:results")
    else:
        form = ResultEditForm(instance=result)
    _add_ma_classes(form)
    return render(request, "myadmin/results/form.html", {
        "form": form,
        "result": result,
        "page_title": result.participant.name + " / " + result.boulder.label,
    })


@myadmin_required
def myadmin_result_delete(request, pk):
    result = get_object_or_404(
        Result.objects.select_related("participant", "boulder"), pk=pk
    )
    if request.method == "POST":
        desc = result.participant.name + " / " + result.boulder.label
        result.delete()
        messages.success(request, "Ergebnis " + desc + " geloescht.")
        return redirect("myadmin:results")
    return render(request, "myadmin/results/delete_confirm.html", {
        "result": result,
        "page_title": "Ergebnis loeschen?",
    })


# ---------------------------------------------------------------------------
# Export — shared data helpers
# ---------------------------------------------------------------------------

def _results_rows():
    """Return (headers, rows) for the results CSV/preview."""
    headers = [
        "Teilnehmer", "Benutzername", "Altersgruppe", "Boulder",
        "Top", "Zone 2", "Zone 1",
        "Versuche Top", "Versuche Zone 2", "Versuche Zone 1",
        "Flash", "Version", "Erstellt am", "Zuletzt geaendert",
    ]
    results = Result.objects.select_related(
        "participant", "participant__age_group", "boulder"
    ).order_by("participant__age_group__name", "participant__name", "boulder__label")
    rows = []
    for r in results:
        is_flash = r.top and r.attempts_top == 1
        rows.append([
            r.participant.name,
            r.participant.username,
            r.participant.age_group.name if r.participant.age_group else "--",
            r.boulder.label,
            "Ja" if r.top else "Nein",
            "Ja" if r.zone2 else "Nein",
            "Ja" if r.zone1 else "Nein",
            r.attempts_top,
            r.attempts_zone2,
            r.attempts_zone1,
            "Flash" if is_flash else "",
            r.version,
            r.created_at.strftime("%d.%m.%Y %H:%M:%S") if r.created_at else "--",
            r.updated_at.strftime("%d.%m.%Y %H:%M:%S") if r.updated_at else "--",
        ])
    return headers, rows


_HISTORY_TYPE_MAP = {"+": "Erstellt", "~": "Geaendert", "-": "Geloescht"}


def _history_rows():
    """Return (headers, rows) for the history CSV/preview.

    Queries HistoricalResult directly (single query) instead of N+1
    per-result approach. Uses select_related to avoid further queries for
    participant/boulder/history_user.
    """
    headers = [
        "Teilnehmer", "Benutzername", "Altersgruppe", "Boulder",
        "Top", "Zone 2", "Zone 1",
        "Versuche Top", "Versuche Zone 2", "Versuche Zone 1",
        "Version", "Aenderungszeitpunkt", "Aenderungstyp", "Geaendert von",
    ]
    HistoricalResult = Result.history.model
    history_qs = (
        HistoricalResult.objects
        .select_related("participant", "participant__age_group", "boulder", "history_user")
        .order_by("history_date")
    )
    rows = []
    for h in history_qs:
        try:
            p_name = h.participant.name if h.participant_id else "--"
            p_user = h.participant.username if h.participant_id else "--"
            p_group = (
                h.participant.age_group.name
                if h.participant_id and h.participant and h.participant.age_group_id
                else "--"
            )
        except Exception:
            p_name = p_user = p_group = "--"
        try:
            b_label = h.boulder.label if h.boulder_id else "--"
        except Exception:
            b_label = "--"
        rows.append([
            p_name, p_user, p_group, b_label,
            "Ja" if h.top else "Nein",
            "Ja" if h.zone2 else "Nein",
            "Ja" if h.zone1 else "Nein",
            h.attempts_top, h.attempts_zone2, h.attempts_zone1,
            h.version,
            h.history_date.strftime("%d.%m.%Y %H:%M:%S"),
            _HISTORY_TYPE_MAP.get(h.history_type, h.history_type),
            h.history_user.username if h.history_user_id and h.history_user else "System",
        ])
    return headers, rows


def _standings_groups():
    """Return list of {age_group, entries, grading_system} dicts for preview/PDF."""
    from ..services.scoring_service import ScoringService
    settings = CompetitionSettings.objects.filter(singleton_guard=True).first()
    if not settings:
        return None, None
    groups = []
    for age_group in AgeGroup.objects.order_by("name"):
        participants = list(
            Participant.objects.filter(age_group=age_group)
            .select_related("age_group").order_by("name")
        )
        if not participants:
            groups.append({"age_group": age_group, "entries": [], "grading_system": settings.grading_system})
            continue
        boulders = list(Boulder.objects.filter(age_groups=age_group))
        results_qs = Result.objects.filter(
            participant__in=participants, boulder__in=boulders
        ).select_related("participant", "boulder")
        if settings.grading_system in ("point_based_dynamic", "point_based_dynamic_attempts"):
            results_list = list(results_qs)
            result_map = ScoringService.group_results_by_participant(results_list)
            top_counts = ScoringService.count_tops_per_boulder(results_list)
            entries = ScoringService.build_scoreboard_entries(
                participants, result_map, settings.grading_system, settings,
                top_counts=top_counts, participant_count=len(participants),
            )
        else:
            result_map = ScoringService.group_results_by_participant(results_qs)
            entries = ScoringService.build_scoreboard_entries(
                participants, result_map, settings.grading_system, settings
            )
        groups.append({"age_group": age_group, "entries": entries, "grading_system": settings.grading_system})
    return settings, groups


# ---------------------------------------------------------------------------
# Export — preview views (browser)
# ---------------------------------------------------------------------------

def _rows_to_csv_text(headers, rows):
    """Render headers + rows as a UTF-8 CSV string (for in-browser display)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    return buf.getvalue()


@myadmin_required
def myadmin_preview_results_csv(request):
    headers, rows = _results_rows()
    return render(request, "myadmin/exports/preview_csv.html", {
        "page_title": "Vorschau: Ergebnisse CSV",
        "csv_text": _rows_to_csv_text(headers, rows),
        "row_count": len(rows),
        "download_url_name": "myadmin:export_results_csv",
        "filename": "ergebnisse.csv",
    })


@myadmin_required
def myadmin_preview_history_csv(request):
    headers, rows = _history_rows()
    return render(request, "myadmin/exports/preview_csv.html", {
        "page_title": "Vorschau: Verlaufsprotokoll CSV",
        "csv_text": _rows_to_csv_text(headers, rows),
        "row_count": len(rows),
        "download_url_name": "myadmin:export_history_csv",
        "filename": "ergebnisse_verlauf.csv",
    })


@myadmin_required
def myadmin_preview_standings(request):
    settings, groups = _standings_groups()
    if groups is None:
        messages.error(request, "Keine Wettkampfeinstellungen gefunden.")
        return redirect("myadmin:dashboard")
    return render(request, "myadmin/exports/preview_standings.html", {
        "page_title": "Vorschau: Rangliste",
        "inline_pdf_url": "myadmin:inline_standings_pdf",
        "download_url_name": "myadmin:export_standings_pdf",
    })


def _build_standings_pdf_elements(groups, current_time):
    """Build the ReportLab flowable elements for the standings PDF."""
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("T", parent=styles["Heading1"], fontSize=18, spaceAfter=30, alignment=1)
    group_style = ParagraphStyle("G", parent=styles["Heading2"], fontSize=14, spaceAfter=10)

    TABLE_STYLE = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 12),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 10),
    ])

    elements = []
    elements.append(Paragraph("BoulderCup Rangliste<br/><font size=12>Stand: " + current_time + "</font>", title_style))
    elements.append(Spacer(1, 0.5 * cm))

    # --- Gesamtübersicht ---
    grading_system = groups[0]["grading_system"] if groups else "ifsc"
    elements.append(Paragraph("Gesamtübersicht", group_style))
    if grading_system == "ifsc":
        overview_data = [["Altersgruppe", "Rang", "Name", "Tops", "Zonen", "Versuche Top", "Versuche Zone"]]
        for g in groups:
            for e in g["entries"]:
                overview_data.append([
                    g["age_group"].name, str(e["rank"]), e["participant"].name,
                    str(e.get("tops", 0)), str(e.get("zones", 0)),
                    str(e.get("top_attempts", 0)), str(e.get("zone_attempts", 0)),
                ])
    else:
        overview_data = [["Altersgruppe", "Rang", "Name", "Punkte", "Tops", "Zonen"]]
        for g in groups:
            for e in g["entries"]:
                overview_data.append([
                    g["age_group"].name, str(e["rank"]), e["participant"].name,
                    str(round(e.get("points", 0), 1)),
                    str(e.get("tops", 0)), str(e.get("zones", 0)),
                ])
    if len(overview_data) > 1:
        overview_table = Table(overview_data, hAlign="LEFT")
        overview_table.setStyle(TABLE_STYLE)
        elements.append(overview_table)
    else:
        elements.append(Paragraph("Keine Ergebnisse vorhanden", styles["Normal"]))
    elements.append(Spacer(1, 1.5 * cm))

    # --- Einzelne Altersgruppen ---
    for g in groups:
        elements.append(Paragraph("Altersgruppe: " + g["age_group"].name, group_style))
        entries = g["entries"]
        if not entries:
            elements.append(Paragraph("Keine Ergebnisse vorhanden", styles["Normal"]))
            elements.append(Spacer(1, 0.5 * cm))
            continue
        if g["grading_system"] == "ifsc":
            table_data = [["Rang", "Name", "Tops", "Zonen", "Versuche Top", "Versuche Zone"]]
            for e in entries:
                table_data.append([str(e["rank"]), e["participant"].name,
                    str(e.get("tops", 0)), str(e.get("zones", 0)),
                    str(e.get("top_attempts", 0)), str(e.get("zone_attempts", 0))])
        else:
            table_data = [["Rang", "Name", "Punkte", "Tops", "Zonen"]]
            for e in entries:
                table_data.append([str(e["rank"]), e["participant"].name,
                    str(round(e.get("points", 0), 1)),
                    str(e.get("tops", 0)), str(e.get("zones", 0))])
        table = Table(table_data, hAlign="LEFT")
        table.setStyle(TABLE_STYLE)
        elements.append(table)
        elements.append(Spacer(1, 1 * cm))

    return elements


@xframe_options_sameorigin
@myadmin_required
def myadmin_inline_standings_pdf(request):
    """Serve the standings PDF inline (for browser iframe embedding)."""
    from django.utils import timezone as tz
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate

    settings, groups = _standings_groups()
    if groups is None:
        return HttpResponse("Keine Wettkampfeinstellungen.", status=404)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
    doc.build(_build_standings_pdf_elements(groups, tz.now().strftime("%d.%m.%Y %H:%M:%S")))
    buf.seek(0)
    response = HttpResponse(buf.read(), content_type="application/pdf")
    response["Content-Disposition"] = "inline; filename=\"rangliste_vorschau.pdf\""
    return response


# ---------------------------------------------------------------------------
# Export — download views
# ---------------------------------------------------------------------------

@myadmin_required
def myadmin_export_results_csv(request):
    from django.utils import timezone as tz
    headers, rows = _results_rows()
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    ts = tz.now().strftime("%Y-%m-%d_%H%M")
    response["Content-Disposition"] = "attachment; filename=\"ergebnisse_" + ts + ".csv\""
    writer = csv.writer(response)
    writer.writerow(headers)
    writer.writerows(rows)
    return response


@myadmin_required
def myadmin_export_history_csv(request):
    from django.utils import timezone as tz
    headers, rows = _history_rows()
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    ts = tz.now().strftime("%Y-%m-%d_%H%M")
    response["Content-Disposition"] = "attachment; filename=\"ergebnisse_verlauf_" + ts + ".csv\""
    writer = csv.writer(response)
    writer.writerow(headers)
    writer.writerows(rows)
    return response


@myadmin_required
def myadmin_export_standings_pdf(request):
    from django.utils import timezone as tz
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate

    settings, groups = _standings_groups()
    if groups is None:
        messages.error(request, "Keine Wettkampfeinstellungen gefunden.")
        return redirect("myadmin:results")

    response = HttpResponse(content_type="application/pdf")
    ts = tz.now().strftime("%Y-%m-%d_%H%M")
    response["Content-Disposition"] = "attachment; filename=\"rangliste_" + ts + ".pdf\""

    doc = SimpleDocTemplate(response, pagesize=landscape(A4))
    doc.build(_build_standings_pdf_elements(groups, tz.now().strftime("%d.%m.%Y %H:%M:%S")))
    return response


# ---------------------------------------------------------------------------
# SubmissionWindows
# ---------------------------------------------------------------------------

@myadmin_required
def myadmin_windows(request):
    from ..models import SiteSettings
    site = SiteSettings.objects.filter(singleton_guard=True).first()
    qs = SubmissionWindow.objects.prefetch_related("age_groups").order_by("submission_start")
    page_obj = _paginate(qs, request, per_page=50)
    return render(request, "myadmin/windows/list.html", {
        "page_title": "Zeitfenster",
        "page_obj": page_obj,
        "submission_always_open": site.submission_always_open if site else False,
    })


@myadmin_required
def myadmin_toggle_submission(request):
    if request.method != "POST":
        return redirect("myadmin:windows")
    from ..models import SiteSettings
    site, _ = SiteSettings.objects.get_or_create(singleton_guard=True)
    site.submission_always_open = not site.submission_always_open
    site.save()
    if site.submission_always_open:
        messages.success(request, "Abgabe dauerhaft geöffnet.")
    else:
        messages.info(request, "Dauerhaft-offen deaktiviert. Zeitfenster gelten wieder.")
    return redirect("myadmin:windows")


@myadmin_required
def myadmin_window_add(request):
    # Pre-fill with competition date
    initial = {}
    cs = CompetitionSettings.objects.filter(singleton_guard=True).first()
    if cs and cs.competition_date:
        from datetime import datetime
        start = timezone.make_aware(datetime.combine(cs.competition_date, datetime.min.time().replace(hour=9, minute=0)))
        initial["submission_start"] = start
        initial["submission_end"] = start.replace(hour=17, minute=0)

    if request.method == "POST":
        form = SubmissionWindowAdminForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Zeitfenster wurde angelegt.")
            return redirect("myadmin:windows")
    else:
        form = SubmissionWindowAdminForm(initial=initial)
    _add_ma_classes(form)
    return render(request, "myadmin/windows/form.html", {
        "form": form, "is_add": True, "page_title": "Zeitfenster anlegen",
        **_agegroup_picker_ctx(),
    })


@myadmin_required
def myadmin_window_edit(request, pk):
    window = get_object_or_404(SubmissionWindow, pk=pk)
    if request.method == "POST":
        form = SubmissionWindowAdminForm(request.POST, instance=window)
        if form.is_valid():
            form.save()
            messages.success(request, window.name + " gespeichert.")
            return redirect("myadmin:windows")
    else:
        form = SubmissionWindowAdminForm(instance=window)
    _add_ma_classes(form)
    return render(request, "myadmin/windows/form.html", {
        "form": form, "window": window, "is_add": False,
        "page_title": window.name + " bearbeiten",
        **_agegroup_picker_ctx(window),
    })


@myadmin_required
def myadmin_window_delete(request, pk):
    window = get_object_or_404(SubmissionWindow, pk=pk)
    if request.method == "POST":
        name = window.name
        window.delete()
        messages.success(request, "Zeitfenster " + name + " geloescht.")
        return redirect("myadmin:windows")
    return render(request, "myadmin/windows/delete_confirm.html", {
        "window": window, "page_title": window.name + " loeschen?",
    })



# ---------------------------------------------------------------------------
# Settings singletons: SiteSettings, CountdownSettings, Punktesystem
# ---------------------------------------------------------------------------

class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = (
            "dashboard_heading", "greeting_enabled", "greeting_heading",
            "greeting_message", "help_text_content", "rulebook_content",
        )
        widgets = {
            "greeting_message": CKEditor5Widget(config_name="default"),
            "help_text_content": CKEditor5Widget(config_name="default"),
            "rulebook_content":  CKEditor5Widget(config_name="default"),
        }


class CountdownSettingsForm(forms.ModelForm):
    background_color = forms.CharField(widget=forms.TextInput(attrs={"type": "color", "class": "ma-input"}), label="Hintergrundfarbe")
    primary_color    = forms.CharField(widget=forms.TextInput(attrs={"type": "color", "class": "ma-input"}), label="Primaerfarbe")
    secondary_color  = forms.CharField(widget=forms.TextInput(attrs={"type": "color", "class": "ma-input"}), label="Sekundaerfarbe")

    class Meta:
        model = CountdownSettings
        fields = (
            "enabled", "countdown_end_time", "show_preview_button",
            "logo", "heading", "subtitle", "message",
            "background_image", "background_color", "primary_color", "secondary_color",
        )
        widgets = {"message": CKEditor5Widget(config_name="default")}


class PunkteSystemForm(forms.ModelForm):
    class Meta:
        model = CompetitionSettings
        fields = (
            "grading_system",
            "flash_points",
            "top_points",
            "top_points_10", "top_points_20", "top_points_30", "top_points_40",
            "top_points_50", "top_points_60", "top_points_70", "top_points_80",
            "top_points_90", "top_points_100",
            "zone_points", "zone1_points", "zone2_points",
            "min_top_points", "min_zone_points", "min_zone1_points", "min_zone2_points",
            "attempt_penalty",
        )


@myadmin_required
def myadmin_site_settings(request):
    obj, _ = SiteSettings.objects.get_or_create(singleton_guard=True)
    form = SiteSettingsForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Site-Einstellungen gespeichert.")
        return redirect("myadmin:site_settings")
    _add_ma_classes(form)
    return render(request, "myadmin/singletons/site_settings.html", {
        "form": form, "page_title": "Site-Einstellungen",
    })


@myadmin_required
def myadmin_countdown(request):
    obj, _ = CountdownSettings.objects.get_or_create(singleton_guard=True)
    form = CountdownSettingsForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Countdown-Einstellungen gespeichert.")
        return redirect("myadmin:countdown")
    _add_ma_classes(form)
    return render(request, "myadmin/singletons/countdown.html", {
        "form": form, "page_title": "Countdown",
    })


@myadmin_required
def myadmin_punktesystem(request):
    obj, _ = CompetitionSettings.objects.get_or_create(singleton_guard=True)
    form = PunkteSystemForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Punktesystem gespeichert.")
        return redirect("myadmin:punktesystem")
    _add_ma_classes(form)
    return render(request, "myadmin/singletons/punktesystem.html", {
        "form": form, "page_title": "Punktesystem",
    })
