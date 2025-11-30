from django.contrib import admin

from .forms import ParticipantAdminForm
from .models import AgeGroup, Boulder, Participant, CompetitionSettings


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


@admin.register(CompetitionSettings)
class CompetitionSettingsAdmin(admin.ModelAdmin):
    list_display = ("grading_system", "top_points", "zone_points", "flash_points", "attempt_penalty", "updated_at")
    fields = ("grading_system", "top_points", "zone_points", "flash_points", "attempt_penalty")

    def has_add_permission(self, request):
        # Only one settings row
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

    class Media:
        js = ("admin/js/competition_settings_toggle.js",)
