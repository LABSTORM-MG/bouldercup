from django.contrib import admin

from accounts.admin import CompetitionSettingsAdmin, RulebookAdmin, HelpTextAdmin, SubmissionWindowAdmin
from .models import CompetitionSettingsProxy, SubmissionWindowProxy, RulebookProxy, HelpTextProxy

admin.site.register(CompetitionSettingsProxy, CompetitionSettingsAdmin)
admin.site.register(SubmissionWindowProxy, SubmissionWindowAdmin)
admin.site.register(RulebookProxy, RulebookAdmin)
admin.site.register(HelpTextProxy, HelpTextAdmin)
