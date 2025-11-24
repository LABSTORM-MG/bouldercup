from django import forms


class LoginForm(forms.Form):
    username = forms.CharField(label="Benutzername", max_length=150)
    password = forms.CharField(label="Passwort", widget=forms.PasswordInput)


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        label="Teilnehmer CSV",
        help_text="Erwartet Spalten: first_name, surname, date_of_birth (YYYY-MM-DD) und gender.",
    )
