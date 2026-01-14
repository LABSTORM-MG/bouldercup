from django import forms

from .models import Participant


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
        if current_password != self.participant.password:
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

    class Meta:
        model = Participant
        fields = "__all__"
