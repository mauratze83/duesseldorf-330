#!/usr/bin/env python3
"""Holt Läufe seit Planstart von intervals.icu und schreibt data/activities.json.
Läuft in der GitHub Action; der Schlüssel kommt aus dem Secret INTERVALS_API_KEY.
Gespeichert werden nur Datum, Name, Distanz und Laufzeit – keine GPS-Daten."""
import base64, datetime as dt, json, os, sys, urllib.request, urllib.error, pathlib

OLDEST = "2026-10-26"
OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "activities.json"

key = os.environ.get("INTERVALS_API_KEY", "").strip()
if not key:
    sys.exit("Secret INTERVALS_API_KEY fehlt (Repo → Settings → Secrets and variables → Actions).")

newest = (dt.date.today() + dt.timedelta(days=1)).isoformat()
url = f"https://intervals.icu/api/v1/athlete/0/activities?oldest={OLDEST}&newest={newest}"
auth = base64.b64encode(f"API_KEY:{key}".encode()).decode()
req = urllib.request.Request(url, headers={
    "Authorization": f"Basic {auth}", "Accept": "application/json",
    "User-Agent": "duesseldorf330-plan/1.1"})
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = json.loads(r.read().decode())
except urllib.error.HTTPError as e:
    sys.exit(f"intervals.icu Fehler {e.code}: {e.read().decode(errors='replace')[:300]}")

runs = []
for a in raw:
    if not str(a.get("type", "")).endswith("Run"):
        continue
    dist, mt = a.get("distance") or 0, a.get("moving_time") or 0
    if dist < 1000 or mt <= 0:
        continue
    runs.append({
        "id": a.get("id"), "name": a.get("name") or "Lauf",
        "start_local": a.get("start_date_local"),
        "distance_m": round(dist), "moving_time_s": int(mt),
    })
runs.sort(key=lambda x: x["start_local"] or "")

old = None
if OUT.exists():
    try: old = json.loads(OUT.read_text())
    except Exception: pass
if old and old.get("activities") == runs:
    print(f"Keine Änderung ({len(runs)} Läufe).")
    sys.exit(0)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({
    "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    "activities": runs}, ensure_ascii=False, indent=1) + "\n")
print(f"{len(runs)} Läufe geschrieben.")
