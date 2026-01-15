"""
Health check and monitoring endpoints for BoulderCup.
"""
import json
import logging
import os
from datetime import datetime

from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse

from web_project.settings.config import HEALTH

logger = logging.getLogger(__name__)


def health_check(request):
    """
    Public health check endpoint - basic system status.

    Returns JSON with overall status and individual component checks.
    """
    status = "OK"
    checks = {}

    # Database connectivity
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks['database'] = 'OK'
    except Exception as e:
        checks['database'] = f'ERROR: {str(e)}'
        status = "ERROR"
        logger.error(f"Health check: database error - {str(e)}")

    # Cache connectivity
    try:
        cache.set('health_check', 'ok', 10)
        if cache.get('health_check') == 'ok':
            checks['cache'] = 'OK'
        else:
            checks['cache'] = 'WARNING: Set/Get mismatch'
            status = "WARNING" if status == "OK" else status
    except Exception as e:
        checks['cache'] = f'ERROR: {str(e)}'
        status = "ERROR"
        logger.error(f"Health check: cache error - {str(e)}")

    # Disk space
    try:
        stat = os.statvfs('.')
        free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
        checks['disk_space_gb'] = round(free_gb, 2)
        if free_gb < 1:
            checks['disk_warning'] = 'Low disk space'
            status = "WARNING" if status == "OK" else status
            logger.warning(f"Health check: low disk space ({free_gb:.2f} GB)")
    except Exception as e:
        checks['disk_space'] = f'ERROR: {str(e)}'
        logger.error(f"Health check: disk space check error - {str(e)}")

    # Active participants and submission windows
    try:
        from accounts.models import Participant, SubmissionWindow
        checks['total_participants'] = Participant.objects.count()
        checks['submission_windows'] = SubmissionWindow.objects.count()
    except Exception as e:
        checks['participants'] = f'ERROR: {str(e)}'
        logger.error(f"Health check: participants query error - {str(e)}")

    return JsonResponse({
        'status': status,
        'timestamp': datetime.now().isoformat(),
        'checks': checks
    })


@staff_member_required
def health_logs(request):
    """
    Staff-only endpoint for viewing application logs.

    Returns the most recent log entries in JSON format.
    Requires Django admin authentication.
    """
    log_file = os.path.join(HEALTH.LOG_DIR, 'bouldercup.log')
    entries = []

    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                # Get last N entries
                for line in lines[-HEALTH.HEALTH_LOG_ENTRIES:]:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        entries.append(entry)
                    except json.JSONDecodeError:
                        # Plain text log entry (fallback)
                        entries.append({'message': line})
        except Exception as e:
            logger.error(f"Error reading log file: {str(e)}")
            return JsonResponse({
                'error': f'Failed to read logs: {str(e)}'
            }, status=500)
    else:
        return JsonResponse({
            'entries': [],
            'count': 0,
            'message': 'Log file does not exist yet'
        })

    return JsonResponse({
        'entries': entries,
        'count': len(entries),
        'log_file': log_file
    })
