from accounts.models import CompetitionSettings, SubmissionWindow, Rulebook


class CompetitionSettingsProxy(CompetitionSettings):
    class Meta:
        proxy = True
        verbose_name = "Punktesystem"
        verbose_name_plural = "Punktesysteme"


class SubmissionWindowProxy(SubmissionWindow):
    class Meta:
        proxy = True
        verbose_name = "Zeitslot"
        verbose_name_plural = "Zeitslots"


class RulebookProxy(Rulebook):
    class Meta:
        proxy = True
        verbose_name = "Regelwerk"
        verbose_name_plural = "Regelwerke"
