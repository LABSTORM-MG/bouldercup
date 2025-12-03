from django.contrib import admin

from accounts.admin import CompetitionSettingsAdmin, RulebookAdmin, SubmissionWindowAdmin
from .models import CompetitionSettingsProxy, SubmissionWindowProxy, RulebookProxy

admin.site.register(CompetitionSettingsProxy, CompetitionSettingsAdmin)
admin.site.register(SubmissionWindowProxy, SubmissionWindowAdmin)
admin.site.register(RulebookProxy, RulebookAdmin)
