# Düsseldorf 3:30

Marathonplan für den Uniper Düsseldorf Marathon am 18. April 2027: 25 Wochen, 3 Läufe pro Woche, Zielzeit 3:30 (4:58 /km).

- `index.html` – die Web-App (Wochenansicht, Gesamtplan, Paces, Tipps, Workout-Downloads)
- `data/activities.json` – Ist-Läufe, wird von der GitHub Action aus intervals.icu geholt (nur Datum, Name, Distanz, Laufzeit)
- `tools/fetch_activities.py` – holt die Läufe (läuft in der Action)
- `tools/duesseldorf330_to_intervals.py` – schreibt den Plan in den intervals.icu-Kalender (lokal ausführen)

## Einrichtung

1. **Settings → Secrets and variables → Actions → New repository secret**: Name `INTERVALS_API_KEY`, Wert = API-Schlüssel aus intervals.icu (Settings → Developer Settings).
2. **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. **Actions → „Läufe aktualisieren und veröffentlichen“ → Run workflow**.

Danach aktualisiert sich die Seite zweimal täglich von selbst.

## Paces nach einem Rennen anpassen

Neue HM-Zeit auf der Seite unter „Paces & Puls“ eintragen (wird im Browser gespeichert) und den Kalender neu schreiben:

```
python3 tools/duesseldorf330_to_intervals.py --hm 1:42:30
```
