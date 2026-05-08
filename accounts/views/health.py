"""
Unified system status and monitoring for BoulderCup.

Admin-only views for monitoring system health, metrics, and logs.
"""
import psutil
import json
import logging
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from django.utils import timezone

from django.db.models import Count, Q

from accounts.models import Boulder, Participant, Result, SubmissionWindow
from web_project.settings.config import HEALTH

logger = logging.getLogger(__name__)


@staff_member_required
def clear_logs(request):
    """Truncate the log file. POST only."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    log_file = Path(HEALTH.LOG_DIR) / 'bouldercup.log'
    try:
        log_file.write_text('')
        logger.info('Log file cleared by admin')
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@staff_member_required
def system_status(request):
    """Admin-only unified status page."""
    return render(request, 'admin/system_status.html')


@staff_member_required
def status_api(request):
    """JSON API for status data (health + logs + metrics)."""

    # System metrics using psutil
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    network = psutil.net_io_counters()

    # Health checks
    health = {
        'database': 'OK',
        'cache': 'OK',
        'status': 'OK'
    }

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as e:
        health['database'] = f'ERROR: {e}'
        health['status'] = 'ERROR'
        logger.error(f"Status API: database error - {e}")

    try:
        cache.set('health_check', 'ok', 1)
        if cache.get('health_check') != 'ok':
            raise Exception("Cache verification failed")
    except Exception as e:
        health['cache'] = f'ERROR: {e}'
        health['status'] = 'ERROR'
        logger.error(f"Status API: cache error - {e}")

    # System metrics
    metrics = {
        'cpu_percent': cpu_percent,
        'memory_percent': memory.percent,
        'memory_used_gb': memory.used / (1024**3),
        'memory_total_gb': memory.total / (1024**3),
        'disk_percent': disk.percent,
        'disk_used_gb': disk.used / (1024**3),
        'disk_total_gb': disk.total / (1024**3),
        'network_sent_mb': network.bytes_sent / (1024**2),
        'network_recv_mb': network.bytes_recv / (1024**2),
    }

    # Read filtered logs (WARNING and above only)
    logs = []
    log_file = Path(HEALTH.LOG_DIR) / "bouldercup.log"

    if log_file.exists():
        try:
            with open(log_file, 'r') as f:
                # Read last 200 lines, filter to WARNING+, return last 100
                all_lines = f.readlines()
                recent_lines = all_lines[-200:] if len(all_lines) > 200 else all_lines

                for line in recent_lines:
                    try:
                        entry = json.loads(line.strip())
                        level = entry.get('levelname', 'INFO')
                        # Filter: Only WARNING, ERROR, CRITICAL
                        if level in ['WARNING', 'ERROR', 'CRITICAL']:
                            logs.append(entry)
                    except json.JSONDecodeError:
                        # Plain text log line - include if it looks important
                        if any(keyword in line.lower() for keyword in ['error', 'warning', 'critical', 'failed']):
                            logs.append({
                                'message': line.strip(),
                                'levelname': 'UNKNOWN',
                                'timestamp': None
                            })

                # Keep last 100 important logs
                logs = logs[-100:]
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
            logs = [{'message': f'Error reading logs: {e}', 'levelname': 'ERROR'}]

    # Competition stats
    now = timezone.now()
    p_stats = Participant.objects.aggregate(
        total=Count('id'),
        locked=Count('id', filter=Q(is_locked=True)),
    )
    total_p  = p_stats['total']
    locked_p = p_stats['locked']
    r_stats = Result.objects.aggregate(
        total=Count('id'),
        topped=Count('id', filter=Q(top=True)),
        with_participants=Count('participant_id', distinct=True),
    )
    total_r        = r_stats['total']
    topped_r       = r_stats['topped']
    with_results_p = r_stats['with_participants']

    windows = []
    for w in SubmissionWindow.objects.prefetch_related('age_groups').order_by('submission_start'):
        if w.submission_start and w.submission_end:
            if w.submission_start <= now <= w.submission_end:
                status = 'active'
            elif now < w.submission_start:
                status = 'upcoming'
            else:
                status = 'past'
        else:
            status = 'unknown'
        windows.append({
            'name': w.name,
            'age_groups': [ag.name for ag in w.age_groups.all()],
            'start': w.submission_start.isoformat() if w.submission_start else None,
            'end':   w.submission_end.isoformat()   if w.submission_end   else None,
            'status': status,
        })

    db_path = Path(settings.DATABASES['default']['NAME'])
    db_size_mb = round(db_path.stat().st_size / (1024 ** 2), 2) if db_path.exists() else 0

    competition = {
        'participants_total':        total_p,
        'participants_locked':       locked_p,
        'participants_with_results': with_results_p,
        'results_total':             total_r,
        'results_topped':            topped_r,
        'boulders_total':            Boulder.objects.count(),
        'windows':                   windows,
        'db_size_mb':                db_size_mb,
    }

    return JsonResponse({
        'timestamp': datetime.now().isoformat(),
        'health': health,
        'metrics': metrics,
        'competition': competition,
        'logs': logs,
        'log_count': len(logs)
    })
