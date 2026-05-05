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
    # Results
    myadmin_results,
    myadmin_result_edit,
    myadmin_result_delete,
    # Exports
    myadmin_preview_results_csv,
    myadmin_preview_history_csv,
    myadmin_preview_standings,
    myadmin_inline_standings_pdf,
    myadmin_export_results_csv,
    myadmin_export_history_csv,
    myadmin_export_standings_pdf,
    # SubmissionWindows
    myadmin_windows,
    myadmin_window_add,
    myadmin_window_edit,
    myadmin_window_delete,
    myadmin_toggle_submission,
    # Singletons
    myadmin_admin_message,
    myadmin_wettkampfdatum,
    myadmin_site_settings,
    myadmin_countdown,
    myadmin_punktesystem,
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
    # Results
    path("ergebnisse/", myadmin_results, name="results"),
    path("ergebnisse/<int:pk>/", myadmin_result_edit, name="result_edit"),
    path("ergebnisse/<int:pk>/loeschen/", myadmin_result_delete, name="result_delete"),
    # Exports — previews
    path("export/ergebnisse-csv/vorschau/", myadmin_preview_results_csv, name="preview_results_csv"),
    path("export/verlauf-csv/vorschau/", myadmin_preview_history_csv, name="preview_history_csv"),
    path("export/rangliste/vorschau/", myadmin_preview_standings, name="preview_standings"),
    path("export/rangliste/inline/", myadmin_inline_standings_pdf, name="inline_standings_pdf"),
    # Exports — downloads
    path("export/ergebnisse-csv/", myadmin_export_results_csv, name="export_results_csv"),
    path("export/verlauf-csv/", myadmin_export_history_csv, name="export_history_csv"),
    path("export/rangliste-pdf/", myadmin_export_standings_pdf, name="export_standings_pdf"),
    # SubmissionWindows
    path("zeitfenster/", myadmin_windows, name="windows"),
    path("zeitfenster/neu/", myadmin_window_add, name="window_add"),
    path("zeitfenster/<int:pk>/", myadmin_window_edit, name="window_edit"),
    path("zeitfenster/<int:pk>/loeschen/", myadmin_window_delete, name="window_delete"),
    path("zeitfenster/abgabe-umschalten/", myadmin_toggle_submission, name="toggle_submission"),
    # Singletons
    path("nachricht/", myadmin_admin_message, name="admin_message"),
    path("wettkampfdatum/", myadmin_wettkampfdatum, name="wettkampfdatum"),
    path("site-einstellungen/", myadmin_site_settings, name="site_settings"),
    path("countdown/", myadmin_countdown, name="countdown"),
    path("punktesystem/", myadmin_punktesystem, name="punktesystem"),
]
