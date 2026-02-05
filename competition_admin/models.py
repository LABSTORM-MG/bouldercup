from accounts.models import CompetitionSettings, SubmissionWindow, SiteSettings


class CompetitionSettingsProxy(CompetitionSettings):
    class Meta:
        proxy = True
        verbose_name = "Punktesystem"
        verbose_name_plural = "Punktesystem"


class CompetitionMetadataProxy(CompetitionSettings):
    class Meta:
        proxy = True
        verbose_name = "Wettkampfdatum"
        verbose_name_plural = "Wettkampfdatum"


class SubmissionWindowProxy(SubmissionWindow):
    class Meta:
        proxy = True
        verbose_name = "Zeitslot"
        verbose_name_plural = "Zeitslots"


class SiteSettingsProxy(SiteSettings):
    class Meta:
        proxy = True
        verbose_name = "Site-Einstellungen"
        verbose_name_plural = "Site-Einstellungen"
