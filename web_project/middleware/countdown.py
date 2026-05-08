"""
Countdown page middleware.

Shows countdown page to all users until configured time.
Bypass via "Preview Site" button sets session flag.
"""

import logging
from django.core.cache import cache
from django.shortcuts import render

logger = logging.getLogger(__name__)


def _contrast_color(hex_color: str) -> str:
    """Return #ffffff or #1a1a1a depending on which has better WCAG contrast against hex_color."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return '#1a1a1a'
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)

    def _lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    luminance = 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)
    return '#ffffff' if luminance < 0.179 else '#1a1a1a'


class CountdownMiddleware:
    """Intercept requests and show countdown until configured time."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.excluded_paths = ['/admin/', '/myadmin/', '/static/', '/media/', '/favicon.ico']

    def __call__(self, request):
        # Exclude admin and static paths
        if any(request.path.startswith(p) for p in self.excluded_paths):
            return self.get_response(request)

        settings = cache.get('countdown_settings')
        if settings is None:
            from accounts.models import CountdownSettings
            settings = CountdownSettings.objects.filter(singleton_guard=True).first()
            cache.set('countdown_settings', settings, 5)

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
        text_color = _contrast_color(settings.background_color)
        context = {
            'logo': settings.logo,
            'heading': settings.heading,
            'subtitle': settings.subtitle,
            'message': settings.message,
            'background_image': settings.background_image,
            'background_color': settings.background_color,
            'primary_color': settings.primary_color,
            'secondary_color': settings.secondary_color,
            'text_color': text_color,
            'countdown_end_time': settings.countdown_end_time,
            'countdown_end_timestamp': None,
            'show_preview_button': settings.show_preview_button,
        }

        if settings.countdown_end_time:
            context['countdown_end_timestamp'] = int(settings.countdown_end_time.timestamp())

        return render(request, 'countdown.html', context)
