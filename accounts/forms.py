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
