from django.contrib import admin

from accounts.admin import CompetitionSettingsAdmin, CompetitionMetadataAdmin, SiteSettingsAdmin, SubmissionWindowAdmin
from .models import CompetitionSettingsProxy, CompetitionMetadataProxy, SubmissionWindowProxy, SiteSettingsProxy

admin.site.register(CompetitionMetadataProxy, CompetitionMetadataAdmin)
admin.site.register(CompetitionSettingsProxy, CompetitionSettingsAdmin)
admin.site.register(SubmissionWindowProxy, SubmissionWindowAdmin)
admin.site.register(SiteSettingsProxy, SiteSettingsAdmin)
