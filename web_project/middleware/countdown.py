"""
Countdown page middleware.

Shows countdown page to all users until configured time.
Bypass via "Preview Site" button sets session flag.

NO CACHING - directly checks DB every request (max 300 users, no need for cache complexity).
"""

import logging
from django.shortcuts import render

logger = logging.getLogger(__name__)


class CountdownMiddleware:
    """Intercept requests and show countdown until configured time."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.excluded_paths = ['/admin/', '/static/', '/media/', '/favicon.ico']

    def __call__(self, request):
        # Exclude admin and static paths
        if any(request.path.startswith(p) for p in self.excluded_paths):
            return self.get_response(request)

        # Get settings directly from DB (no caching - 300 users max)
        from accounts.models import CountdownSettings
        settings = CountdownSettings.objects.filter(singleton_guard=True).first()

        # No settings or not active = normal site immediately
        if not settings or not settings.is_active():
            return self.get_response(request)

        # Handle preview parameter
        if request.GET.get('preview') == '1':
            request.session['countdown_bypass'] = True
            logger.info(f"Countdown bypass enabled for session {request.session.session_key}")

        # Check bypass flag
        if request.session.get('countdown_bypass', False):
            return self.get_response(request)

        # Show countdown page
        # JavaScript handles visual countdown, server just provides end timestamp
        context = {
            'logo': settings.logo,
            'heading': settings.heading,
            'subtitle': settings.subtitle,
            'message': settings.message,
            'background_image': settings.background_image,
            'background_color': settings.background_color,
            'primary_color': settings.primary_color,
            'secondary_color': settings.secondary_color,
            'countdown_end_time': settings.countdown_end_time,
            'countdown_end_timestamp': None,
        }

        if settings.countdown_end_time:
            context['countdown_end_timestamp'] = int(settings.countdown_end_time.timestamp())

        return render(request, 'countdown.html', context)
