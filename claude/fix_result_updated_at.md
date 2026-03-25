# Fix: Result.updated_at wird bei Boulder-Änderungen fälschlicherweise aktualisiert

**Branch:** `feature/custom-admin-dashboard`
**Status:** Geplant, noch nicht implementiert
**Datum:** 2026-03-25

---

## Problem

In der Ergebnisse-CSV zeigt die Spalte „Zuletzt geändert" (`updated_at`) für alle
Zeilen denselben Zeitstempel, auch wenn nur ein Boulder geändert wurde und kein
einziges Ergebnis tatsächlich angefasst wurde.

---

## Ursachenanalyse

### Root Cause 1 (bestätigt): `auto_now=True`

```python
# accounts/models.py, Zeile 360
updated_at = models.DateTimeField(auto_now=True)
```

`auto_now=True` setzt den Zeitstempel bei **jedem** `.save()`-Aufruf, egal ob
sich tatsächliche Ergebnisdaten (top/zone/versuche) geändert haben oder nicht.
Jeder versehentliche Re-Save aus beliebigem Anlass (Admin-Aktionen, Signale,
Management-Commands) aktualisiert den Timestamp.

### Root Cause 2 (vermutet): Unkannter Re-Save-Trigger

Kein expliziter Signal- oder View-Code gefunden, der beim Boulder-Speichern alle
Results massenhaft `.save()`-t. Mögliche Ursachen:
- Django Admin bulk-Aktionen
- Externe Management-Commands
- Zukünftige Signale

Auch wenn der genaue Trigger unbekannt bleibt: Part 1 des Fixes macht ihn
irrelevant.

### Untersuchte Dateien (ohne Fund)
- `accounts/signals.py` — kein `post_save` für Boulder
- `accounts/models.py` — `Boulder.save()` berührt keine Results
- `accounts/views/myadmin.py` — `myadmin_boulder_edit` ruft nur `form.save()` auf
- `accounts/forms_admin.py` — `BoulderAdminForm` hat kein custom `save()`
- `accounts/services/result_service.py` — nur einzelne Result-Saves bei Einreichung
- `accounts/services/scoring_service.py` — `invalidate_all_scoreboards()` löscht
  nur Cache-Einträge, keine DB-Writes

---

## Fix-Plan

### Part 1: `auto_now=True` durch intelligentes manuelles Tracking ersetzen

**Datei:** `accounts/models.py`

```python
# Vorher:
updated_at = models.DateTimeField(auto_now=True)

# Nachher:
updated_at = models.DateTimeField(default=timezone.now, blank=True)
```

`Result.save()` erweitern — `updated_at` nur setzen, wenn sich echte Ergebnisdaten
geändert haben:

```python
TRACKED_FIELDS = frozenset({
    "top", "zone1", "zone2",
    "attempts_top", "attempts_zone1", "attempts_zone2",
})

def save(self, *args, **kwargs):
    if self.pk:
        self.version += 1
        # Nur updated_at setzen wenn sich Ergebnisdaten geändert haben
        try:
            old = Result.objects.filter(pk=self.pk).values(*self.TRACKED_FIELDS).get()
            if any(old[f] != getattr(self, f) for f in self.TRACKED_FIELDS):
                self.updated_at = timezone.now()
        except Result.DoesNotExist:
            self.updated_at = timezone.now()
    else:
        self.updated_at = timezone.now()
    super().save(*args, **kwargs)
```

**Migration erforderlich** — Feldänderung von `auto_now=True` zu
`auto_now=False, default=timezone.now`. Kein Schema-Change (SQLite), Django
trackt es aber als Felddefinitionsänderung.

```bash
python manage.py makemigrations accounts --name fix_result_updated_at_no_auto_now
```

---

### Part 2: Boulder-Zone-Normalisierung via `QuerySet.update()`

**Datei:** `accounts/signals.py`

Wenn `zone_count` eines Boulders geändert wird, werden verknüpfte Results
normalisiert (z.B. Zone-Flags löschen bei 0-Zonen-Boulder) — **ohne** `.save()`
aufzurufen, damit `updated_at`, `HistoricalRecords` und `version` unberührt
bleiben.

```python
from django.db.models.signals import post_save, pre_save
from .models import Boulder, Result

# Alten zone_count vor dem Speichern merken
@receiver(pre_save, sender=Boulder)
def capture_boulder_zone_count(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._old_zone_count = Boulder.objects.filter(pk=instance.pk).values_list('zone_count', flat=True).get()
        except Boulder.DoesNotExist:
            instance._old_zone_count = None
    else:
        instance._old_zone_count = None


@receiver(post_save, sender=Boulder)
def normalize_results_after_zone_change(sender, instance, **kwargs):
    old_zone_count = getattr(instance, '_old_zone_count', None)
    if old_zone_count is None or old_zone_count == instance.zone_count:
        return  # Kein zone_count-Wechsel

    qs = Result.objects.filter(boulder=instance)

    if instance.zone_count == 0:
        # Keine Zonen: alle Zone-Felder und Versuche zurücksetzen
        qs.update(zone1=False, zone2=False, attempts_zone1=0, attempts_zone2=0)
    elif instance.zone_count == 1:
        # Eine Zone: zone2 löschen
        qs.filter(zone2=True).update(zone2=False, attempts_zone2=0)

    # QuerySet.update() bypasses .save(), auto_now, HistoricalRecords und version-Counter
    # → updated_at bleibt unverändert, kein History-Eintrag für technische Bereinigung
```

**Keine Migration** für Part 2 nötig.

---

## Implementierungsreihenfolge

1. `accounts/models.py` — Feldänderung + erweitertes `save()`
2. `python manage.py makemigrations accounts --name fix_result_updated_at_no_auto_now`
3. `accounts/signals.py` — pre_save + post_save für Boulder ergänzen
4. Testen: Boulder zone_count ändern → CSV exportieren → `updated_at` darf sich
   nicht geändert haben
5. Testen: Ergebnis einreichen → `updated_at` muss sich aktualisieren
6. Commit + ggf. in master mergen

---

## Hinweise

- Der extra `SELECT` in `Result.save()` (`.filter(pk=...).values(...).get()`)
  hat vernachlässigbaren Performance-Impact, da Result-Saves nur einzeln bei
  Teilnehmer-Einreichungen passieren (kein Bulk-Betrieb).
- `QuerySet.update()` in Part 2 schreibt absichtlich **keinen** History-Eintrag
  und inkrementiert **nicht** `version`, da es sich um eine technische
  Daten-Bereinigung handelt, nicht um eine Teilnehmer-Aktion.
- Falls der ursprüngliche Re-Save-Trigger später identifiziert wird, sollte
  auch dort `.save()` durch `.update()` oder `update_fields` ohne `updated_at`
  ersetzt werden.
