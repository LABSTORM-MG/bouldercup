import logging
from functools import wraps
from typing import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from web_project.settings.config import TIMING

from ..forms import PasswordChangeForm
from ..models import AgeGroup, Boulder, Participant, Result, Rulebook, SubmissionWindow
from ..services import ResultService, ScoringService

logger = logging.getLogger(__name__)


def _get_participant_from_session(request: HttpRequest) -> Participant | None:
    """Get participant from session ID."""
    participant_id = request.session.get("participant_id")
    if not participant_id:
        return None
    try:
        return Participant.objects.select_related("age_group").get(id=participant_id)
    except Participant.DoesNotExist:
        return None


def participant_required(
    view_func: Callable[[HttpRequest, Participant, ...], HttpResponse]
):
    """Redirect to login when no participant session is present."""

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        participant = _get_participant_from_session(request)
        if not participant:
            return redirect("login")
        return view_func(request, participant, *args, **kwargs)

    return wrapper


def _render_section(
    request: HttpRequest,
    participant: Participant,
    template: str,
    section_title: str,
    extra_context: dict | None = None,
) -> HttpResponse:
    """Render a participant section with common context."""
    context = {"participant": participant, "section_title": section_title}
    if extra_context:
        context.update(extra_context)
    return render(request, template, context)


@participant_required
def participant_dashboard(request: HttpRequest, participant: Participant) -> HttpResponse:
    """Main dashboard for participants."""
    return render(
        request,
        "participant_dashboard.html",
        {"participant": participant},
    )


@participant_required
def participant_support(request: HttpRequest, participant: Participant) -> HttpResponse:
    """Support and help section."""
    return _render_section(
        request,
        participant,
        "participant_support.html",
        "Hilfe & Support",
    )


@participant_required
def participant_settings(request: HttpRequest, participant: Participant) -> HttpResponse:
    """Settings section with password change."""
    success_message = ""

    if request.method == "POST":
        form = PasswordChangeForm(participant, request.POST)
        if form.is_valid():
            participant.password = form.cleaned_data["new_password"]
            participant.save(update_fields=["password"])
            success_message = "Dein Passwort wurde aktualisiert."
            form = PasswordChangeForm(participant)
    else:
        form = PasswordChangeForm(participant)

    return _render_section(
        request,
        participant,
        "participant_settings.html",
        "Einstellungen",
        {
            "form": form,
            "success_message": success_message,
        },
    )


@participant_required
def participant_results(request: HttpRequest, participant: Participant) -> HttpResponse:
    """
    Handle result submission and display.

    Supports both AJAX (for autosave) and regular POST.
    Enforces submission windows when configured for the participant's age group.
    """
    boulders = (
        Boulder.objects.filter(age_groups=participant.age_group)
        .prefetch_related('age_groups')
        .order_by("label")
        if participant.age_group_id
        else Boulder.objects.none()
    )

    existing_results = ResultService.load_existing_results(participant, boulders)
    for boulder in boulders:
        boulder.existing_result = existing_results.get(boulder.id)

    # Check if submission is allowed for this participant's age group
    can_submit = SubmissionWindow.is_submission_allowed(participant.age_group)
    has_windows = SubmissionWindow.has_windows_for_age_group(participant.age_group)
    active_window = SubmissionWindow.get_active_for_age_group(participant.age_group)
    next_window = None
    next_window_timestamp = None
    active_window_end_timestamp = None

    if can_submit and active_window and active_window.submission_end:
        # Pass the active window end timestamp for countdown display
        active_window_end_timestamp = active_window.submission_end.timestamp()

    # Always check for next window, regardless of current submission state
    if participant.age_group:
        next_window = SubmissionWindow.get_next_upcoming_for_age_group(participant.age_group)
        if next_window and next_window.submission_start:
            next_window_timestamp = next_window.submission_start.timestamp()

    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"

    if request.method == "GET" and is_ajax:
        # Re-check submission status for AJAX (countdown may have expired or windows changed)
        can_submit = SubmissionWindow.is_submission_allowed(participant.age_group)
        has_windows = SubmissionWindow.has_windows_for_age_group(participant.age_group)
        active_window = SubmissionWindow.get_active_for_age_group(participant.age_group)
        next_window = None
        next_window_timestamp = None
        active_window_end_timestamp = None

        if can_submit and active_window and active_window.submission_end:
            active_window_end_timestamp = active_window.submission_end.timestamp()

        if participant.age_group:
            next_window = SubmissionWindow.get_next_upcoming_for_age_group(participant.age_group)
            if next_window and next_window.submission_start:
                next_window_timestamp = next_window.submission_start.timestamp()

        payload = {
            boulder.id: ResultService.result_to_payload(res)
            for boulder, res in ((b, b.existing_result) for b in boulders)
            if res is not None
        }
        return JsonResponse({
            "ok": True,
            "results": payload,
            "can_submit": can_submit,
            "has_windows": has_windows,
            "next_window_timestamp": next_window_timestamp,
            "active_window_end_timestamp": active_window_end_timestamp,
        })

    if request.method == "POST":
        # Re-check submission status with 30-second grace period
        # Grace period prevents data loss due to network latency and clock differences
        can_submit = SubmissionWindow.is_submission_allowed(participant.age_group, grace_period_seconds=TIMING.GRACE_PERIOD_SECONDS)
        if not can_submit:
            return JsonResponse({
                "ok": False,
                "error": "Ergebniseintragung ist außerhalb des Zeitfensters nicht möglich."
            }, status=403)
        payload = ResultService.handle_submission(request.POST, participant, boulders)
        return JsonResponse({"ok": True, "results": payload})

    return render(
        request,
        "participant_results.html",
        {
            "participant": participant,
            "title": "Ergebnisse eintragen",
            "boulders": boulders,
            "can_submit": can_submit,
            "has_windows": has_windows,
            "active_window": active_window,
            "next_window": next_window,
            "next_window_timestamp": next_window_timestamp,
            "active_window_end_timestamp": active_window_end_timestamp,
        },
    )


@participant_required
def participant_run_plan(request: HttpRequest, participant: Participant) -> HttpResponse:
    """Run plan section (placeholder)."""
    return _render_section(
        request,
        participant,
        "participant_run_plan.html",
        "Laufplan",
    )


@participant_required
def participant_live_scoreboard(request: HttpRequest, participant: Participant) -> HttpResponse:
    """
    Live scoreboard with caching and AJAX updates.
    
    Supports filtering by age group and caches results for performance.
    """
    settings_obj = ScoringService.get_active_settings()
    grading_system = settings_obj.grading_system if settings_obj else "ifsc"

    age_groups = list(
        AgeGroup.objects.filter(participants__isnull=False).distinct().order_by("name")
    )
    
    requested_group_id = request.GET.get("age_group")
    selected_group = None
    show_all = requested_group_id == "all"
    
    if requested_group_id and not show_all:
        selected_group = next((g for g in age_groups if str(g.id) == requested_group_id), None)
    if not selected_group and not show_all:
        selected_group = participant.age_group if participant.age_group_id else (age_groups[0] if age_groups else None)

    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    
    # For AJAX requests, try cache first
    if is_ajax:
        age_group_key = selected_group.id if selected_group else "all"
        cached_data = ScoringService.get_cached_scoreboard(age_group_key, grading_system)
        
        if cached_data:
            return JsonResponse(cached_data)
    
    # Calculate scoreboard
    entries: list[dict] = []
    if selected_group or show_all:
        boulders = (
            Boulder.objects.filter(age_groups=selected_group)
            .prefetch_related('age_groups')
            .order_by("label")
            if selected_group
            else Boulder.objects.all().order_by("label")
        )

        participants_qs = (
            Participant.objects
            .filter(age_group__in=[selected_group] if selected_group else age_groups)
            .select_related('age_group')
            .order_by("name")
        )
        participants = list(participants_qs)

        results = (
            Result.objects
            .filter(participant__in=participants, boulder__in=boulders)
            .select_related("participant__age_group", "boulder")
        )

        # For dynamic scoring, we need to calculate top counts per boulder
        if grading_system in ("point_based_dynamic", "point_based_dynamic_attempts"):
            results_list = list(results)
            result_map = ScoringService.group_results_by_participant(results_list)
            top_counts = ScoringService.count_tops_per_boulder(results_list)
            entries = ScoringService.build_scoreboard_entries(
                participants, result_map, grading_system, settings_obj,
                top_counts=top_counts, participant_count=len(participants)
            )
        else:
            result_map = ScoringService.group_results_by_participant(results)
            entries = ScoringService.build_scoreboard_entries(
                participants, result_map, grading_system, settings_obj
            )

    if is_ajax:
        payload = {
            "ok": True,
            "entries": [
                {
                    "rank": entry["rank"],
                    "name": entry["participant"].name,
                    "tops": entry.get("tops", 0),
                    "top_attempts": entry.get("top_attempts", 0),
                    "zones": entry.get("zones", 0),
                    "zone_attempts": entry.get("zone_attempts", 0),
                    "points": entry.get("points", 0),
                }
                for entry in entries
            ],
            "grading": grading_system,
        }
        
        # Cache the result
        age_group_key = selected_group.id if selected_group else "all"
        ScoringService.cache_scoreboard(age_group_key, grading_system, payload)
        
        return JsonResponse(payload)

    return render(
        request,
        "participant_live_scoreboard.html",
        {
            "participant": participant,
            "title": "Live-Ergebnisse",
            "entries": entries,
            "age_groups": age_groups,
            "selected_group": selected_group,
            "grading_system": grading_system,
        },
    )


@participant_required
def participant_rulebook(request: HttpRequest, participant: Participant) -> HttpResponse:
    """Display competition rulebook."""
    settings_obj = ScoringService.get_active_settings()
    grading_system = settings_obj.grading_system if settings_obj else "ifsc"
    rulebook = Rulebook.objects.order_by("-updated_at", "-id").first()
    rules_text = rulebook.content if rulebook else ""
    
    return render(
        request,
        "participant_rulebook.html",
        {
            "participant": participant,
            "title": "Regelwerk",
            "grading_system": grading_system,
            "rules_text": rules_text,
        },
    )
