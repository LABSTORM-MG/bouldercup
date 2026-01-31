"""
Unified system status and monitoring for BoulderCup.

Admin-only views for monitoring system health, metrics, and logs.
"""
import psutil
import json
import logging
from datetime import datetime
from pathlib import Path

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache

from web_project.settings.config import HEALTH

logger = logging.getLogger(__name__)


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

    return JsonResponse({
        'timestamp': datetime.now().isoformat(),
        'health': health,
        'metrics': metrics,
        'logs': logs,
        'log_count': len(logs)
    })
