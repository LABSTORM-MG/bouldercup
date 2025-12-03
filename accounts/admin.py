from django import forms
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from .forms import ParticipantAdminForm
from .models import AgeGroup, Boulder, Participant, Rulebook
from django_ckeditor_5.widgets import CKEditor5Widget


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
        "created_at",
    )
    list_filter = ("gender", "age_group")
    search_fields = ("name", "username")
    fields = (
        "name",
        "date_of_birth",
        "gender",
        "username",
        "password",
        "age_group",
    )
    form = ParticipantAdminForm

    @admin.display(description="Alter")
    def display_age(self, obj):
        return obj.age


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
            "Top & Flash",
            {"fields": ("top_points", "flash_points")},
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


class SubmissionWindowAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fmt = "%d.%m.%Y %H:%M"
        for name in ("submission_start", "submission_end"):
            if name in self.fields:
                self.fields[name].input_formats = [fmt]
                self.fields[name].widget.format = fmt
                self.fields[name].widget.attrs.setdefault("placeholder", "tt.mm.jjjj hh:mm")

    class Meta:
        fields = "__all__"
        widgets = {
            "submission_start": forms.DateTimeInput(
                format="%d.%m.%Y %H:%M", attrs={"placeholder": "tt.mm.jjjj hh:mm"}
            ),
            "submission_end": forms.DateTimeInput(
                format="%d.%m.%Y %H:%M", attrs={"placeholder": "tt.mm.jjjj hh:mm"}
            ),
        }


class SubmissionWindowAdmin(admin.ModelAdmin):
    form = SubmissionWindowAdminForm
    list_display = ("name", "display_start", "display_end", "updated_at")
    list_filter = ()
    search_fields = ("name", "note")
    ordering = ("submission_start",)
    list_editable = ()
    fields = ("name", "submission_start", "submission_end", "note")

    @admin.display(description="Start")
    def display_start(self, obj):
        return obj.submission_start.strftime("%d.%m.%Y %H:%M") if obj.submission_start else "—"

    @admin.display(description="Ende")
    def display_end(self, obj):
        return obj.submission_end.strftime("%d.%m.%Y %H:%M") if obj.submission_end else "—"


class RulebookAdminForm(forms.ModelForm):
    content = forms.CharField(
        widget=CKEditor5Widget(config_name="default"), required=False, label="Regelwerk"
    )

    class Meta:
        model = Rulebook
        fields = ("name", "content")


class RulebookAdmin(SingletonAdminMixin, admin.ModelAdmin):
    form = RulebookAdminForm
    list_display = ("name", "updated_at")
    fieldsets = (
        (None, {"fields": ("name", "content")}),
    )

    class Media:
        css = {
            "all": ("admin/css/ckeditor5_overrides.css",),
        }
