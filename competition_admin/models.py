from accounts.models import CompetitionSettings, SubmissionWindow, Rulebook, HelpText


class CompetitionSettingsProxy(CompetitionSettings):
    class Meta:
        proxy = True
        verbose_name = "Punktesystem"
        verbose_name_plural = "Punktesystem"


class SubmissionWindowProxy(SubmissionWindow):
    class Meta:
        proxy = True
        verbose_name = "Zeitslot"
        verbose_name_plural = "Zeitslots"


class RulebookProxy(Rulebook):
    class Meta:
        proxy = True
        verbose_name = "Regelwerk"
        verbose_name_plural = "Regelwerk"


class HelpTextProxy(HelpText):
    class Meta:
        proxy = True
        verbose_name = "Hilfetext"
        verbose_name_plural = "Hilfetext"
