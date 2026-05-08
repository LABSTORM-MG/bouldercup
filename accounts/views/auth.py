import logging

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from ..forms import LoginForm
from ..models import Participant
from ..utils import verify_password

logger = logging.getLogger(__name__)

_RATE_LIMIT_ATTEMPTS = 3
_RATE_LIMIT_WINDOW = 60  # seconds


def _login_rate_limited(request: HttpRequest) -> bool:
    ip = request.META.get("REMOTE_ADDR", "unknown")
    key = f"login_attempts_{ip}"
    attempts = cache.get(key, 0)
    if attempts >= _RATE_LIMIT_ATTEMPTS:
        return True
    cache.set(key, attempts + 1, timeout=_RATE_LIMIT_WINDOW)
    return False


def login_view(request: HttpRequest) -> HttpResponse:
    """Handle participant login with username/password."""
    message = ""
    message_type = "error"  # default, "locked" for locked accounts
    form = LoginForm(request.POST or None)

    # Check if user was redirected due to being locked
    if request.GET.get("locked") == "1":
        message = "Dein Zugang wurde gesperrt. Bitte wende dich an das Personal oder die Organisatoren."
        message_type = "locked"

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
        if _login_rate_limited(request):
            message = "Zu viele Anmeldeversuche. Bitte warte 1 Minute."
            return render(request, "login.html", {"form": form, "message": message, "message_type": message_type})

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
            message = "Ungültige Anmeldedaten."
            logger.warning(f"Login failed: unknown user '{username}'")
        elif participant.is_locked:
            message = "Dein Zugang wurde gesperrt. Bitte wende dich an das Personal oder die Organisatoren."
            message_type = "locked"
            logger.warning(f"Login blocked: locked user '{participant.username}' (ID: {participant.id})")
        elif verify_password(password, participant.password):
            request.session["participant_id"] = participant.id
            logger.info(f"Login successful: {participant.username} (ID: {participant.id})")
            return redirect("participant_dashboard")
        else:
            message = "Ungültige Anmeldedaten."
            logger.warning(f"Login failed: incorrect password for user '{participant.username}' (ID: {participant.id})")

    return render(
        request,
        "login.html",
        {
            "form": form,
            "message": message,
            "message_type": message_type,
        },
    )


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    request.session.flush()
    return redirect("login")
