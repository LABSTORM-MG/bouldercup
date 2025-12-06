"""
Settings module that imports the correct settings based on environment.
"""

import os

# Default to development settings
DJANGO_ENV = os.getenv('DJANGO_ENV', 'dev')

if DJANGO_ENV == 'production':
    from .prod import *
else:
    from .dev import *
