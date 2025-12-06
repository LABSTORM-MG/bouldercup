"""
Development settings.
"""

from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# Less strict CSRF for local development
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# Show detailed error pages
INTERNAL_IPS = [
    '127.0.0.1',
    'localhost',
]
