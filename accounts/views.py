from django.shortcuts import render

from .forms import LoginForm
from .models import Participant


def login_view(request):
    message = ""
    form = LoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]

        try:
            participant = Participant.objects.select_related("age_group").get(
                username=username
            )
        except Participant.DoesNotExist:
            message = "Unbekannter Teilnehmer."
        else:
            if participant.password == password:
                request.session["participant_id"] = participant.id
                group_label = (
                    participant.age_group.name
                    if participant.age_group
                    else "deiner Gruppe"
                )
                message = (
                    f"Hallo {participant.name}! "
                    f"Du wurdest der Gruppe {group_label} zugeordnet."
                )
                form = LoginForm()
            else:
                message = "Falsches Passwort."

    return render(
        request,
        "login.html",
        {
            "form": form,
            "message": message,
        },
    )
