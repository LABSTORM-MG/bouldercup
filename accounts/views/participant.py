import logging
from functools import wraps
from typing import Callable

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from web_project.settings.config import TIMING

from ..forms import PasswordChangeForm
from ..models import AgeGroup, Boulder, Participant, Result, AdminMessage, SiteSettings, SubmissionWindow
from ..services import ResultService, ScoringService
from ..services.window_service import WindowService
from ..utils import hash_password

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
    """Redirect to login when no participant session is present or participant is locked."""

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        participant = _get_participant_from_session(request)
        if not participant:
            return redirect("login")

        # Check if participant is locked
        if participant.is_locked:
            # Clear session and redirect to login with locked message
            request.session.flush()
            logger.warning(f"Locked participant attempted access: {participant.username} (ID: {participant.id})")
            return HttpResponseRedirect(reverse("login") + "?locked=1")

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
    # Get dashboard heading from site settings
    site_settings = SiteSettings.objects.first()
    dashboard_heading = site_settings.dashboard_heading if site_settings else "Willkommen beim BoulderCup"

    # Check if user needs to acknowledge greeting message
    show_greeting = False
    greeting_heading = ""
    greeting_message = ""
    if site_settings and site_settings.greeting_enabled:
        # Get user's acknowledged version
        try:
            from ..models import GreetingAcknowledgment
            acknowledgment = GreetingAcknowledgment.objects.get(participant=participant)
            acknowledged_version = acknowledgment.acknowledged_version
        except GreetingAcknowledgment.DoesNotExist:
            acknowledged_version = 0

        # Show greeting if current version is newer
        if site_settings.greeting_version > acknowledged_version:
            show_greeting = True
            greeting_heading = site_settings.greeting_heading
            greeting_message = site_settings.greeting_message

    return render(
        request,
        "participant_dashboard.html",
        {
            "participant": participant,
            "dashboard_heading": dashboard_heading,
            "show_greeting": show_greeting,
            "greeting_heading": greeting_heading,
            "greeting_message": greeting_message,
        },
    )


@participant_required
def participant_support(request: HttpRequest, participant: Participant) -> HttpResponse:
    """Support and help section."""
    site_settings = SiteSettings.objects.first()
    help_text_content = site_settings.help_text_content if site_settings else ""

    return _render_section(
        request,
        participant,
        "participant_support.html",
        "Hilfe & Support",
        {"help_text": help_text_content},
    )


@participant_required
def participant_settings(request: HttpRequest, participant: Participant) -> HttpResponse:
    """Settings section with password change."""
    success_message = ""

    if request.method == "POST":
        form = PasswordChangeForm(participant, request.POST)
        if form.is_valid():
            participant.password = hash_password(form.cleaned_data["new_password"])
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

    # Get submission window status (initial check without grace period)
    window_status = WindowService.get_submission_status(participant.age_group)

    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"

    if request.method == "GET" and is_ajax:
        # Re-check submission status for AJAX (countdown may have expired or windows changed)
        window_status = WindowService.get_submission_status(participant.age_group)

        payload = {
            boulder.id: ResultService.result_to_payload(res)
            for boulder, res in ((b, b.existing_result) for b in boulders)
            if res is not None
        }
        return JsonResponse({
            "ok": True,
            "results": payload,
            **WindowService.to_json_dict(window_status),
        })

    if request.method == "POST":
        # Re-check submission status with grace period
        # Grace period prevents data loss due to network latency and clock differences
        window_status = WindowService.get_submission_status(
            participant.age_group,
            grace_period_seconds=TIMING.GRACE_PERIOD_SECONDS
        )

        if not window_status.can_submit:
            logger.warning(
                f"Result submission rejected: participant {participant.username} "
                f"(ID: {participant.id}) outside time window"
            )
            return JsonResponse({
                "ok": False,
                "error": "Ergebniseintragung ist außerhalb des Zeitfensters nicht möglich."
            }, status=403)

        payload = ResultService.handle_submission(request.POST, participant, boulders)
        logger.info(
            f"Results submitted: participant {participant.username} "
            f"(ID: {participant.id}), {len(payload)} boulders"
        )
        return JsonResponse({"ok": True, "results": payload})

    return render(
        request,
        "participant_results.html",
        {
            "participant": participant,
            "title": "Ergebnisse eintragen",
            "boulders": boulders,
            **WindowService.to_context_dict(window_status),
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
            .filter(is_locked=False)
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
                    "participant_id": entry["participant"].id,
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

    site_settings = SiteSettings.objects.first()
    rules_text = site_settings.rulebook_content if site_settings else ""

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


@participant_required
def acknowledge_greeting(request: HttpRequest, participant: Participant) -> JsonResponse:
    """API endpoint to record greeting message acknowledgment."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        from ..models import GreetingAcknowledgment
        site_settings = SiteSettings.objects.first()

        if not site_settings:
            return JsonResponse({"error": "No site settings found"}, status=404)

        # Create or update acknowledgment
        acknowledgment, created = GreetingAcknowledgment.objects.update_or_create(
            participant=participant,
            defaults={"acknowledged_version": site_settings.greeting_version}
        )

        logger.info(
            f"Greeting acknowledged: {participant.username} (ID: {participant.id}), "
            f"version {site_settings.greeting_version}"
        )

        return JsonResponse({"success": True})

    except Exception as e:
        logger.error(f"Error acknowledging greeting for {participant.username}: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@participant_required
def participant_detail_results(request: HttpRequest, participant: Participant, participant_id: int) -> HttpResponse:
    """
    Display detailed boulder-by-boulder results for a specific participant.

    Shows individual performance on each boulder with tops, zones, attempts,
    and points (for point-based systems). Any authenticated participant can
    view any other participant's results.
    """
    from django.shortcuts import get_object_or_404

    # Get target participant
    target_participant = get_object_or_404(
        Participant.objects.select_related('age_group'),
        id=participant_id
    )

    # Handle case where participant has no age group
    if not target_participant.age_group:
        return render(
            request,
            "participant_detail_results.html",
            {
                "participant": participant,
                "target_participant": target_participant,
                "boulder_results": [],
                "grading_system": "ifsc",
                "is_point_based": False,
                "has_two_zone_boulders": False,
                "total_points": 0,
                "total_tops": 0,
                "total_zones": 0,
                "boulders_without_results": [],
                "no_age_group": True,
            },
        )

    # Get boulders for their age group
    boulders = list(
        Boulder.objects.filter(age_groups=target_participant.age_group)
        .order_by("label")
    )

    # Get results with boulder data
    results = list(
        Result.objects.filter(
            participant=target_participant,
            boulder__in=boulders
        )
        .select_related('boulder')
        .order_by('boulder__label')
    )

    # Get grading system
    settings = ScoringService.get_active_settings()
    grading_system = settings.grading_system if settings else "ifsc"
    is_point_based = grading_system in ScoringService.POINT_BASED_SYSTEMS

    # For dynamic systems, calculate top counts
    top_counts = None
    participant_count = None
    if grading_system in ScoringService.DYNAMIC_SYSTEMS and settings:
        # Get all results for the age group to calculate percentages
        all_results = Result.objects.filter(
            participant__age_group=target_participant.age_group,
            boulder__in=boulders
        ).select_related('participant', 'boulder')
        top_counts = ScoringService.count_tops_per_boulder(all_results)
        participant_count = Participant.objects.filter(
            age_group=target_participant.age_group,
            is_locked=False
        ).count()

    # Build boulder results list
    boulder_results = []
    boulders_without_results = []
    has_two_zone_boulders = False
    total_points = 0
    total_tops = 0
    total_zones = 0

    result_map = {r.boulder_id: r for r in results}

    for boulder in boulders:
        res = result_map.get(boulder.id)

        if res:
            # Calculate points for this boulder
            points = 0
            if is_point_based and settings:
                points = ScoringService.calculate_boulder_points(
                    res, grading_system, settings, top_counts, participant_count
                )
                total_points += points

            # Track totals
            if res.top:
                total_tops += 1
            if res.zone2 or res.zone1:
                total_zones += 1

            # Check if this boulder has 2 zones
            if boulder.zone_count >= 2:
                has_two_zone_boulders = True

            boulder_results.append({
                'boulder': boulder,
                'result': res,
                'points': points,
                'top': res.top,
                'zone2': res.zone2,
                'zone1': res.zone1,
                'attempts_top': res.attempts_top or res.attempts or 0,
                'attempts_zone2': res.attempts_zone2 or res.attempts or 0,
                'attempts_zone1': res.attempts_zone1 or res.attempts or 0,
                'top_display': f"✓ ({res.attempts_top or res.attempts})" if res.top else "-",
                'zone2_display': f"✓ ({res.attempts_zone2 or res.attempts})" if res.zone2 else ("-" if boulder.zone_count >= 2 else "N/A"),
                'zone1_display': f"✓ ({res.attempts_zone1 or res.attempts})" if res.zone1 else ("-" if boulder.zone_count >= 1 else "N/A"),
            })
        else:
            # Boulder not attempted
            if boulder.zone_count >= 2:
                has_two_zone_boulders = True
            boulders_without_results.append(boulder)

    return render(
        request,
        "participant_detail_results.html",
        {
            "participant": participant,
            "target_participant": target_participant,
            "boulder_results": boulder_results,
            "grading_system": grading_system,
            "is_point_based": is_point_based,
            "has_two_zone_boulders": has_two_zone_boulders,
            "total_points": total_points,
            "total_tops": total_tops,
            "total_zones": total_zones,
            "boulders_without_results": boulders_without_results,
            "no_age_group": False,
        },
    )


@participant_required
def get_admin_message(request: HttpRequest, participant: Participant) -> JsonResponse:
    """
    API endpoint to fetch active admin broadcast message.

    Returns the current admin message if it has content, or null if empty.
    Results are cached for 5 minutes (SETTINGS_CACHE_TIMEOUT).
    """
    # Check cache first
    cached_message = cache.get('admin_message')

    if cached_message is not None:
        # Cache hit - return cached data
        return JsonResponse({"ok": True, "message": cached_message})

    # Cache miss - query database
    admin_message = AdminMessage.objects.order_by("-updated_at", "-id").first()

    if not admin_message or not admin_message.has_content():
        # No message or empty message
        message_data = None
    else:
        # Build message response
        message_data = {
            "heading": admin_message.heading,
            "content": admin_message.content,
            "background_color": admin_message.background_color,
            "updated_at": admin_message.updated_at.timestamp(),
        }

    # Cache the result
    cache.set('admin_message', message_data, TIMING.SETTINGS_CACHE_TIMEOUT)
    logger.debug("Admin message cached")

    return JsonResponse({"ok": True, "message": message_data})
