import logging

from django import forms
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from .forms import ParticipantAdminForm
from .models import AgeGroup, Boulder, Participant, AdminMessage, SiteSettings, Result, SubmissionWindow
from django_ckeditor_5.widgets import CKEditor5Widget

logger = logging.getLogger(__name__)


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 1
    fields = ("name", "date_of_birth", "gender", "username", "password", "age_group")
    form = ParticipantAdminForm


class BoulderInline(admin.TabularInline):
    model = Boulder.age_groups.through
    extra = 1
    verbose_name = "Boulder"
    verbose_name_plural = "Boulder"
    fields = ("boulder",)


@admin.register(AgeGroup)
class AgeGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "min_age", "max_age", "gender")
    list_filter = ("gender",)
    search_fields = ("name",)
    inlines = [BoulderInline, ParticipantInline]


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    change_list_template = "admin/accounts/participant/change_list.html"
    list_display = (
        "name",
        "username",
        "display_age",
        "gender",
        "age_group",
        "display_lock_status",
        "created_at",
    )
    list_filter = ("gender", "age_group", "is_locked")
    search_fields = ("name", "username")
    fields = (
        "name",
        "date_of_birth",
        "gender",
        "username",
        "password",
        "age_group",
        "is_locked",
    )
    form = ParticipantAdminForm
    actions = ["lock_participants", "unlock_participants"]

    @admin.display(description="Alter")
    def display_age(self, obj):
        return obj.age

    @admin.display(description="Status", boolean=True)
    def display_lock_status(self, obj):
        """Display lock status (green checkmark = unlocked, red X = locked)."""
        return not obj.is_locked

    @admin.action(description="Ausgewählte Teilnehmer sperren")
    def lock_participants(self, request, queryset):
        """Lock selected participants and invalidate their sessions."""
        from django.contrib.sessions.models import Session
        from django.core.cache import cache
        import logging

        logger = logging.getLogger(__name__)

        # Get participant IDs before update
        participant_ids = list(queryset.values_list('id', flat=True))

        # Update lock status
        count = queryset.update(is_locked=True)

        # Invalidate sessions for locked participants
        sessions_deleted = 0
        for session in Session.objects.all():
            session_data = session.get_decoded()
            participant_id = session_data.get('participant_id')
            if participant_id in participant_ids:
                session.delete()
                sessions_deleted += 1

        # Invalidate all caches (scoreboards will update immediately)
        cache.clear()

        self.message_user(
            request,
            f"{count} Teilnehmer gesperrt. {sessions_deleted} Sitzungen beendet.",
            level="WARNING"
        )
        logger.warning(
            f"Admin {request.user.username} locked {count} participants: "
            f"IDs {participant_ids}. {sessions_deleted} sessions invalidated."
        )

    @admin.action(description="Ausgewählte Teilnehmer entsperren")
    def unlock_participants(self, request, queryset):
        """Unlock selected participants."""
        from django.core.cache import cache
        import logging

        logger = logging.getLogger(__name__)
        participant_ids = list(queryset.values_list('id', flat=True))
        count = queryset.update(is_locked=False)

        # Invalidate all caches
        cache.clear()

        self.message_user(
            request,
            f"{count} Teilnehmer entsperrt.",
            level="SUCCESS"
        )
        logger.info(
            f"Admin {request.user.username} unlocked {count} participants: "
            f"IDs {participant_ids}"
        )


admin.site.site_title = "BoulderCup Verwaltung"
admin.site.site_header = "BoulderCup Verwaltung"


@admin.register(Boulder)
class BoulderAdmin(admin.ModelAdmin):
    list_display = ("label", "color", "display_zone_count", "location", "created_at")
    search_fields = ("label", "color", "location", "note")
    ordering = ("label",)
    list_filter = ("zone_count", "color")
    filter_horizontal = ()
    exclude = ("age_groups",)

    @admin.display(description="Zonen")
    def display_zone_count(self, obj):
        return obj.get_zone_count_display()


class SingletonAdminMixin:
    """Force a single instance by redirecting the changelist to the edit view."""

    def has_add_permission(self, request):
        # Only allow creating the singleton if it does not yet exist.
        return not self.model.objects.exists()

    def changelist_view(self, request, extra_context=None):
        qs = self.get_queryset(request)
        if qs.count() == 1:
            obj = qs.first()
            url = reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk])
            return redirect(url)
        return super().changelist_view(request, extra_context=extra_context)


class CompetitionMetadataAdmin(SingletonAdminMixin, admin.ModelAdmin):
    """Admin for competition-wide metadata (date, etc.)."""
    list_display = ("competition_date", "updated_at")
    fieldsets = (
        (
            None,
            {"fields": ("competition_date",)},
        ),
    )

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of the singleton."""
        return False


class CompetitionSettingsAdmin(SingletonAdminMixin, admin.ModelAdmin):
    list_display = (
        "grading_system",
        "top_points",
        "flash_points",
        "min_top_points",
        "zone_points",
        "zone1_points",
        "zone2_points",
        "min_zone_points",
        "min_zone1_points",
        "min_zone2_points",
        "attempt_penalty",
        "updated_at",
    )
    list_filter = ("grading_system",)
    search_fields = ("name",)
    ordering = ("name",)
    fieldsets = (
        (
            None,
            {"fields": ("grading_system",)},
        ),
        (
            "Flash-Punkte",
            {"fields": ("flash_points",)},
        ),
        (
            "Top-Punkte (Punktebasiert)",
            {"fields": ("top_points",)},
        ),
        (
            "Top-Punkte nach Prozentsatz (Dynamisch)",
            {"fields": (
                "top_points_10",
                "top_points_20",
                "top_points_30",
                "top_points_40",
                "top_points_50",
                "top_points_60",
                "top_points_70",
                "top_points_80",
                "top_points_90",
                "top_points_100",
            )},
        ),
        (
            "Zonenpunkte",
            {"fields": ("zone_points", "zone1_points", "zone2_points")},
        ),
        (
            "Mindestpunkte",
            {"fields": ("min_top_points", "min_zone_points", "min_zone1_points", "min_zone2_points")},
        ),
        (
            "Strafen",
            {"fields": ("attempt_penalty",)},
        ),
    )

    class Media:
        js = ("admin/js/competition_settings_toggle.js",)


class AdminSplitDateTimeNoSeconds(admin.widgets.AdminSplitDateTime):
    """AdminSplitDateTime without seconds in the time field."""
    def __init__(self, attrs=None):
        super().__init__(attrs)
        # Override the time widget format to exclude seconds
        self.widgets[1].format = "%H:%M"


class SubmissionWindowAdminForm(forms.ModelForm):
    submission_start = forms.SplitDateTimeField(
        required=False,
        label="Start",
        input_time_formats=["%H:%M", "%H:%M:%S"],
        widget=AdminSplitDateTimeNoSeconds(),
    )
    submission_end = forms.SplitDateTimeField(
        required=False,
        label="Ende",
        input_time_formats=["%H:%M", "%H:%M:%S"],
        widget=AdminSplitDateTimeNoSeconds(),
    )

    class Meta:
        model = SubmissionWindow
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("submission_start")
        end = cleaned_data.get("submission_end")

        if start and end and end <= start:
            raise forms.ValidationError(
                "Das Ende des Zeitfensters muss nach dem Start liegen."
            )

        return cleaned_data


class SubmissionWindowAdmin(admin.ModelAdmin):
    form = SubmissionWindowAdminForm
    list_display = ("name", "display_age_groups", "display_start", "display_end", "display_status", "updated_at")
    list_filter = ("age_groups",)
    search_fields = ("name", "note")
    ordering = ("submission_start",)
    filter_horizontal = ("age_groups",)
    fields = ("name", "age_groups", "submission_start", "submission_end", "note")

    class Media:
        js = ("admin/js/submission_window_time.js",)

    def get_changeform_initial_data(self, request):
        """Pre-fill dates with competition date if set."""
        initial = super().get_changeform_initial_data(request)

        # Get competition date from settings
        from accounts.models import CompetitionSettings
        from django.utils import timezone
        from datetime import datetime

        settings = CompetitionSettings.objects.filter(singleton_guard=True).first()
        if settings and settings.competition_date:
            # Create datetime at 9:00 AM on competition date
            competition_datetime = timezone.make_aware(
                datetime.combine(settings.competition_date, datetime.min.time().replace(hour=9, minute=0))
            )
            initial['submission_start'] = competition_datetime
            initial['submission_end'] = competition_datetime.replace(hour=17, minute=0)  # 5:00 PM

        return initial

    @admin.display(description="Altersgruppen")
    def display_age_groups(self, obj):
        groups = obj.age_groups.all()
        if not groups:
            return "—"
        return ", ".join(g.name for g in groups[:3]) + ("..." if groups.count() > 3 else "")

    @admin.display(description="Start")
    def display_start(self, obj):
        return obj.submission_start.strftime("%d.%m.%Y %H:%M") if obj.submission_start else "—"

    @admin.display(description="Ende")
    def display_end(self, obj):
        return obj.submission_end.strftime("%d.%m.%Y %H:%M") if obj.submission_end else "—"

    @admin.display(description="Status")
    def display_status(self, obj):
        if obj.is_active():
            return "Aktiv"
        return "Inaktiv"


class AdminMessageAdminForm(forms.ModelForm):
    background_color = forms.CharField(
        widget=forms.TextInput(attrs={"type": "color"}),
        label="Hintergrundfarbe",
        help_text="Hintergrundfarbe der Nachricht (Hex-Code).",
    )

    class Meta:
        model = AdminMessage
        fields = ("heading", "content", "background_color")


@admin.register(AdminMessage)
class AdminMessageAdmin(SingletonAdminMixin, admin.ModelAdmin):
    form = AdminMessageAdminForm
    list_display = ("heading", "updated_at")
    fieldsets = (
        (None, {"fields": ("heading", "content", "background_color")}),
    )

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Customize the change view to hide 'Save and add another' button."""
        extra_context = extra_context or {}
        extra_context['show_save_and_add_another'] = False
        extra_context['show_save_and_continue'] = False  # Only show main Save button
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def response_add(self, request, obj, post_url_continue=None):
        """Redirect to the change view after adding (instead of changelist)."""
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        return HttpResponseRedirect(
            reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk])
        )

    def response_change(self, request, obj):
        """Keep user on the same page after saving."""
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        from django.contrib import messages

        # Always redirect back to the change page
        messages.success(request, "Admin-Nachricht erfolgreich gespeichert.")
        return HttpResponseRedirect(
            reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk])
        )

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of the singleton."""
        return False


class SiteSettingsAdminForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = ("dashboard_heading", "greeting_enabled", "greeting_heading", "greeting_message", "help_text_content", "rulebook_content")
        widgets = {
            "greeting_message": CKEditor5Widget(config_name="default"),
            "help_text_content": CKEditor5Widget(config_name="default"),
            "rulebook_content": CKEditor5Widget(config_name="default"),
        }


class SiteSettingsAdmin(SingletonAdminMixin, admin.ModelAdmin):
    form = SiteSettingsAdminForm
    list_display = ("name", "updated_at")
    fieldsets = (
        ("Dashboard", {"fields": ("dashboard_heading",)}),
        ("Begrüßungsnachricht", {"fields": ("greeting_enabled", "greeting_heading", "greeting_message", "greeting_version")}),
        ("Hilfe & Support", {"fields": ("help_text_content",)}),
        ("Regelwerk", {"fields": ("rulebook_content",)}),
    )
    readonly_fields = ("greeting_version",)

    class Media:
        css = {
            "all": ("admin/css/ckeditor5_overrides.css",),
        }

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of the singleton."""
        return False


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('participant', 'boulder', 'top', 'zone2', 'zone1', 'attempts', 'updated_at')
    list_filter = ('top', 'zone2', 'zone1', 'boulder', 'participant__age_group')
    search_fields = ('participant__name', 'boulder__label')
    readonly_fields = ('updated_at',)

    def save_model(self, request, obj, form, change):
        """Log admin changes to results."""
        if change:
            # Get old values for comparison
            old_obj = Result.objects.get(pk=obj.pk)
            changes = []
            for field in ['top', 'zone2', 'zone1', 'attempts', 'attempts_top', 'attempts_zone2', 'attempts_zone1']:
                old_val = getattr(old_obj, field)
                new_val = getattr(obj, field)
                if old_val != new_val:
                    changes.append(f"{field}: {old_val} → {new_val}")

            if changes:
                logger.warning(
                    f"Admin result change by {request.user.username}: "
                    f"Participant {obj.participant.username} (ID: {obj.participant.id}), "
                    f"Boulder {obj.boulder.label}, "
                    f"Changes: {', '.join(changes)}"
                )
        else:
            logger.info(
                f"Admin result created by {request.user.username}: "
                f"Participant {obj.participant.username} (ID: {obj.participant.id}), "
                f"Boulder {obj.boulder.label}"
            )

        super().save_model(request, obj, form, change)