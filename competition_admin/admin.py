from django.contrib import admin

from accounts.admin import CompetitionSettingsAdmin, SiteSettingsAdmin, SubmissionWindowAdmin
from .models import CompetitionSettingsProxy, SubmissionWindowProxy, SiteSettingsProxy

admin.site.register(CompetitionSettingsProxy, CompetitionSettingsAdmin)
admin.site.register(SubmissionWindowProxy, SubmissionWindowAdmin)
admin.site.register(SiteSettingsProxy, SiteSettingsAdmin)
