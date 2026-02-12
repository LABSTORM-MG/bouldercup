from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField

from .models import Boulder, Participant
from .services.result_service import SubmittedResult
from .utils import verify_password, hash_password


class LoginForm(forms.Form):
    username = forms.CharField(label="Benutzername", max_length=150)
    password = forms.CharField(label="Passwort", widget=forms.PasswordInput)


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        label="Teilnehmer CSV",
        help_text="Erwartet Spalten: first_name, surname, date_of_birth (DD-MM-YYYY) und gender.",
    )


class PasswordChangeForm(forms.Form):
    current_password = forms.CharField(label="Aktuelles Passwort", widget=forms.PasswordInput)
    new_password = forms.CharField(
        label="Neues Passwort", widget=forms.PasswordInput, min_length=6, help_text="Mindestens 6 Zeichen."
    )
    confirm_password = forms.CharField(label="Neues Passwort bestätigen", widget=forms.PasswordInput)

    def __init__(self, participant: Participant, *args, **kwargs):
        self.participant = participant
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        current_password = self.cleaned_data["current_password"]
        if not verify_password(current_password, self.participant.password):
            raise forms.ValidationError("Aktuelles Passwort ist nicht korrekt.")
        return current_password

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if new_password and confirm_password and new_password != confirm_password:
            self.add_error("confirm_password", "Die Passwörter stimmen nicht überein.")

        if new_password and new_password == cleaned_data.get("current_password"):
            self.add_error("new_password", "Das neue Passwort muss sich vom alten unterscheiden.")

        return cleaned_data


class ParticipantAdminForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        label="Geburtsdatum",
        input_formats=["%d-%m-%Y"],
        widget=forms.DateInput(
            format="%d-%m-%Y",
            attrs={"placeholder": "DD-MM-YYYY"},
        ),
    )
    password = ReadOnlyPasswordHashField(
        label="Passwort",
        help_text=(
            "Passwörter werden gehasht gespeichert und können nicht im Klartext angezeigt werden. "
            "Das Standard-Passwort ist das Geburtsdatum im Format TTMMJJJJ (z.B. 01012000)."
        ),
    )

    class Meta:
        model = Participant
        fields = "__all__"

    def clean_password(self):
        # Regardless of what the user provides, return the initial value.
        # This is done here, rather than on the field, because the
        # field does not have access to the initial value
        return self.initial.get("password")


class ResultSubmissionForm(forms.Form):
    """
    Form for validating result submission data from POST.

    Validates checkbox states and attempt counts for a single boulder result.
    Returns a SubmittedResult dataclass from cleaned_data['submitted_result'].
    """
    zone1 = forms.BooleanField(required=False)
    zone2 = forms.BooleanField(required=False)
    top = forms.BooleanField(required=False)
    attempts_zone1 = forms.IntegerField(required=False)
    attempts_zone2 = forms.IntegerField(required=False)
    attempts_top = forms.IntegerField(required=False)
    version = forms.IntegerField(required=False)

    def __init__(self, boulder_id: int, *args, **kwargs):
        """
        Initialize form with boulder-specific field names.

        Args:
            boulder_id: ID of the boulder this result is for
        """
        self.boulder_id = boulder_id
        self._validated = False
        super().__init__(*args, **kwargs)

    def is_valid(self):
        """Mark form as validated when is_valid is called."""
        result = super().is_valid()
        self._validated = True
        return result

    def clean_attempts_zone1(self):
        """Ensure attempts_zone1 is non-negative."""
        value = self.cleaned_data.get('attempts_zone1')
        return max(0, value) if value is not None else 0

    def clean_attempts_zone2(self):
        """Ensure attempts_zone2 is non-negative."""
        value = self.cleaned_data.get('attempts_zone2')
        return max(0, value) if value is not None else 0

    def clean_attempts_top(self):
        """Ensure attempts_top is non-negative."""
        value = self.cleaned_data.get('attempts_top')
        return max(0, value) if value is not None else 0

    def clean_version(self):
        """Parse version number, returning None if invalid."""
        value = self.cleaned_data.get('version')
        if value is None or value == '':
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def get_submitted_result(self) -> SubmittedResult:
        """
        Return SubmittedResult dataclass from cleaned data.

        Must be called after is_valid() returns True.
        """
        if not self._validated:
            raise ValueError("Form must be validated (call is_valid()) before getting submitted result")

        return SubmittedResult(
            zone1=self.cleaned_data.get('zone1', False),
            zone2=self.cleaned_data.get('zone2', False),
            top=self.cleaned_data.get('top', False),
            attempts_zone1=self.cleaned_data.get('attempts_zone1', 0),
            attempts_zone2=self.cleaned_data.get('attempts_zone2', 0),
            attempts_top=self.cleaned_data.get('attempts_top', 0),
            version=self.cleaned_data.get('version'),
        )
