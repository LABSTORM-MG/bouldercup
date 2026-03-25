from django.urls import path
from .views.myadmin import (
    myadmin_dashboard,
    myadmin_logout,
    # Participants
    myadmin_participants,
    myadmin_participant_add,
    myadmin_participant_edit,
    myadmin_participant_delete,
    myadmin_participant_import,
    myadmin_participant_action,
    # Boulders
    myadmin_boulders,
    myadmin_boulder_add,
    myadmin_boulder_edit,
    myadmin_boulder_delete,
    # AgeGroups
    myadmin_agegroups,
    myadmin_agegroup_add,
    myadmin_agegroup_edit,
    myadmin_agegroup_delete,
    # Singletons
    myadmin_admin_message,
    myadmin_wettkampfdatum,
)

app_name = "myadmin"

urlpatterns = [
    path("", myadmin_dashboard, name="dashboard"),
    path("logout/", myadmin_logout, name="logout"),
    # Participants
    path("teilnehmer/", myadmin_participants, name="participants"),
    path("teilnehmer/neu/", myadmin_participant_add, name="participant_add"),
    path("teilnehmer/<int:pk>/", myadmin_participant_edit, name="participant_edit"),
    path("teilnehmer/<int:pk>/loeschen/", myadmin_participant_delete, name="participant_delete"),
    path("teilnehmer/import/", myadmin_participant_import, name="participant_import"),
    path("teilnehmer/aktion/", myadmin_participant_action, name="participant_action"),
    # Boulders
    path("boulder/", myadmin_boulders, name="boulders"),
    path("boulder/neu/", myadmin_boulder_add, name="boulder_add"),
    path("boulder/<int:pk>/", myadmin_boulder_edit, name="boulder_edit"),
    path("boulder/<int:pk>/loeschen/", myadmin_boulder_delete, name="boulder_delete"),
    # AgeGroups
    path("altersgruppen/", myadmin_agegroups, name="agegroups"),
    path("altersgruppen/neu/", myadmin_agegroup_add, name="agegroup_add"),
    path("altersgruppen/<int:pk>/", myadmin_agegroup_edit, name="agegroup_edit"),
    path("altersgruppen/<int:pk>/loeschen/", myadmin_agegroup_delete, name="agegroup_delete"),
    # Singletons
    path("nachricht/", myadmin_admin_message, name="admin_message"),
    path("wettkampfdatum/", myadmin_wettkampfdatum, name="wettkampfdatum"),
]
