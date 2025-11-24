from django.contrib import admin

from .models import AgeGroup, Participant


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 1
    fields = ("name", "age", "gender", "username", "password", "age_group")


@admin.register(AgeGroup)
class AgeGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "min_age", "max_age", "gender")
    list_filter = ("gender",)
    search_fields = ("name",)
    inlines = [ParticipantInline]


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ("name", "username", "age", "gender", "age_group", "created_at")
    list_filter = ("gender", "age_group")
    search_fields = ("name", "username")
