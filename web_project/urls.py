"""
URL configuration for web_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.contrib.staticfiles.storage import staticfiles_storage
from django.views.generic.base import RedirectView

from accounts.views import (
    login_view,
    participant_dashboard,
    participant_live_scoreboard,
    participant_results,
    participant_run_plan,
    participant_settings,
    participant_support,
    upload_participants,
    participant_rulebook,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path("ckeditor5/", include('django_ckeditor_5.urls')),
    path('', login_view, name='login'),
    path('upload/', upload_participants, name='upload_participants'),
    path('dashboard/', participant_dashboard, name='participant_dashboard'),
    path('dashboard/ergebnisse/', participant_results, name='participant_results'),
    path('dashboard/laufplan/', participant_run_plan, name='participant_run_plan'),
    path('dashboard/live-scoreboard/', participant_live_scoreboard, name='participant_live_scoreboard'),
    path('support/', participant_support, name='participant_support'),
    path('settings/', participant_settings, name='participant_settings'),
    path('regelwerk/', participant_rulebook, name='participant_rulebook'),
    path('favicon.ico', RedirectView.as_view(url=staticfiles_storage.url('favicon.ico'), permanent=False), name='favicon'),
]
