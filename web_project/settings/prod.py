"""
Production settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from .base import *

# Load environment variables from .env file
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

DEBUG = False

# Security: Load secret key from environment
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY environment variable must be set in production")

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "bouldercup.labstorm.net").split(",")

# CSRF trusted origins - required for reverse proxy setup
# The Origin header from the browser is https://bouldercup.labstorm.net
# even though the internal connection to Django is HTTP
CSRF_TRUSTED_ORIGINS = [f"https://{host.strip()}" for host in ALLOWED_HOSTS]

# Security settings
# SSL terminates at the reverse proxy; Django sees plain HTTP internally.
# SECURE_PROXY_SSL_HEADER lets Django trust the X-Forwarded-Proto header so it
# treats the request as HTTPS, enabling Secure cookies without double-redirecting.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False  # proxy enforces HTTPS, Django must not double-redirect
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Redis cache for production (optional)
# Uncomment and configure when using Redis:
# CACHES = {
#     'default': {
#         'BACKEND': 'django.core.cache.backends.redis.RedisCache',
#         'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
#     }
# }

# Static files for production
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'

# Logging
# Build handler list dynamically so management commands (migrate, collectstatic)
# don't crash if /var/log/bouldercup/ doesn't exist yet during initial setup.
# Once the directory is present (created by setup.sh / systemd pre-exec) the
# file handler is enabled automatically on the next Django start.
_LOG_DIR = Path('/var/log/bouldercup')
_handlers: dict = {
    'console': {
        'level': 'INFO',
        'class': 'logging.StreamHandler',
        'formatter': 'verbose',
    },
}
_handler_names: list = ['console']

if _LOG_DIR.exists():
    _handlers['file'] = {
        'level': 'INFO',
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': str(_LOG_DIR / 'django.log'),
        'maxBytes': 1024 * 1024 * 15,  # 15MB
        'backupCount': 10,
        'formatter': 'verbose',
    }
    _handler_names = ['file', 'console']

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': _handlers,
    'root': {
        'handlers': _handler_names,
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': _handler_names,
            'level': 'INFO',
            'propagate': False,
        },
        'accounts': {
            'handlers': _handler_names,
            'level': 'INFO',
            'propagate': False,
        },
    },
}
