"""
Context processors for making configuration available in templates.
"""
from web_project.settings.config import FRONTEND


def frontend_config(request):
    """Make frontend configuration available in all templates."""
    return {'frontend_config': FRONTEND}
