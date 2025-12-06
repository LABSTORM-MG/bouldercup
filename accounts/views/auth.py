from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.text import slugify

from ..forms import LoginForm
from ..models import Participant


def login_view(request: HttpRequest) -> HttpResponse:
    """Handle participant login with username/password."""
    message = ""
    form = LoginForm(request.POST or None)

    def _normalize_username(value: str) -> list[str]:
        """Generate username variants for flexible login."""
        raw = value.strip().lower()
        variants = [
            raw,
            raw.replace(" ", "").replace(".", "").replace("-", ""),
            slugify(raw).replace("-", ""),
            slugify(raw).replace("-", "."),
        ]
        seen: list[str] = []
        for variant in variants:
            if variant and variant not in seen:
                seen.append(variant)
        return seen

    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]

        participant = None
        for candidate in _normalize_username(username):
            try:
                participant = Participant.objects.select_related("age_group").get(username=candidate)
                break
            except Participant.DoesNotExist:
                continue

        if not participant:
            message = "Unbekannter Teilnehmer."
        elif participant.password == password:
            request.session["participant_id"] = participant.id
            return redirect("participant_dashboard")
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
