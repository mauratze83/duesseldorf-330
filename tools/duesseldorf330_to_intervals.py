#!/usr/bin/env python3
"""
Düsseldorf 3:30 – Marathonplan in den intervals.icu-Kalender schreiben.
Von dort synchronisiert intervals.icu die Workouts der jeweils nächsten Woche
automatisch über die Zepp-App auf die Amazfit Balance 2.

Aufruf:
    python3 duesseldorf330_to_intervals.py                 # Paces aus HM 1:45:00
    python3 duesseldorf330_to_intervals.py --hm 1:42:10    # nach neuem HM neu rechnen
    python3 duesseldorf330_to_intervals.py --dry-run       # nur anzeigen, nichts hochladen

Der API-Schlüssel steht in intervals.icu unter Settings -> Developer Settings.
Das Skript fragt ihn ab (oder liest die Umgebungsvariable INTERVALS_API_KEY).
Erneutes Ausführen aktualisiert die Einheiten statt sie doppelt anzulegen.
Nur Python-Standardbibliothek, keine Installation nötig.
"""
import argparse, base64, datetime as dt, getpass, json, os, sys, urllib.request, urllib.error

START = dt.date(2026, 10, 26)  # Montag Woche 0

# ---------- Trainingsbereiche (identisch zur Web-App) ----------
def zone(z, p):
    return {
        "E": (p + 45, p + 75),
        "L": (p + 40, p + 65),
        "M": (p * 1.04 - 4, p * 1.04 + 4),
        "G": (294, 302),
        "H": (p - 3, p + 3),
        "T": (p * .975 - 4, p * .975 + 4),
        "I": (p * .905 - 4, p * .905 + 4),
        "S": (p * .82, p * .88),
        "J": (p + 90, p + 120),
    }[z]

CUE = {"E": "Locker", "L": "Langer Lauf", "M": "Marathontempo", "G": "Zieltempo 4:58",
       "H": "HM-Tempo", "T": "Schwelle", "I": "Intervall", "S": "Steigerung", "J": "Trabpause"}

# ---------- Bausteine ----------
def ez(d): return [{"d": d, "z": "E"}]
def ezS(d, n=6): return [{"d": d, "z": "E"}, {"r": n, "s": [{"t": 1/3, "z": "S"}, {"t": 1, "z": "J"}]}]
def lr(d): return [{"d": d, "z": "L"}]
def lrM(d1, d2, z): return [{"d": d1, "z": "L"}, {"d": d2, "z": z}]
def rep(n, d, z, rt): return [{"d": 2, "z": "E"}, {"r": n, "s": [{"d": d, "z": z}, {"t": rt, "z": "J"}]}, {"d": 1.5, "z": "E"}]
def tempo(pre, d, z, post):
    s = [{"d": pre, "z": "E"}, {"d": d, "z": z}]
    return s + [{"d": post, "z": "E"}] if post else s
def S(name, steps, opt=False): return {"n": name, "steps": steps, "opt": opt}

# Wochen: (Tages-Offsets ab Montag, [Einheiten])
D = [1, 3, 6]  # Di, Do, So
W = [
 ([2, 4, 6], [S("Lockerer Wiederanlauf", ez(5)), S("Locker", ez(6)), S("Lockerer Sonntagslauf", lr(10))]),
 (D, [S("Schwelle 4 × 1 km", rep(4, 1, "T", 1.5)), S("Locker + Steigerungen", ezS(7)), S("Langer Lauf", lr(14))]),
 (D, [S("Schwelle 3 × 2 km", rep(3, 2, "T", 2)), S("Locker + Steigerungen", ezS(8)), S("Langer Lauf", lr(16))]),
 (D, [S("Intervalle 6 × 800 m", rep(6, .8, "I", 2)), S("Locker mit MRT-Finish", tempo(7, 2, "M", 0)), S("Langer Lauf", lr(18))]),
 (D, [S("Schwelle 3 × 1,5 km", rep(3, 1.5, "T", 2)), S("Locker + Steigerungen", ezS(7)), S("Langer Lauf", lr(14))]),
 (D, [S("Schwelle 2 × 3 km", rep(2, 3, "T", 3)), S("Marathontempo 3 km", tempo(5, 3, "M", 1)), S("Langer Lauf", lr(19))]),
 (D, [S("Intervalle 5 × 1 km", rep(5, 1, "I", 2)), S("Locker + Steigerungen", ezS(10)), S("Langer Lauf", lr(21))]),
 (D, [S("Schwelle 4 × 2 km", rep(4, 2, "T", 2)), S("Marathontempo 4 km", tempo(5, 4, "M", 1)), S("Langer Lauf", lr(22))]),
 ([0, 2, 5], [S("Tempodauerlauf 4 km", tempo(2, 4, "T", 1.5)), S("Locker + Steigerungen", ezS(8)), S("Langer Lauf", lr(18))]),
 ([1, 3], [S("Optional locker (Skiurlaub)", ez(6), True), S("Optional locker (Skiurlaub)", ez(8), True)]),
 (D, [S("Schwelle 4 × 1,5 km", rep(4, 1.5, "T", 2)), S("Marathontempo 3 km", tempo(6, 3, "M", 1)), S("Langer Lauf", lr(20))]),
 (D, [S("Intervalle 6 × 1 km", rep(6, 1, "I", 2)), S("Marathontempo 5 km", tempo(5, 5, "M", 1)), S("Langer Lauf", lr(24))]),
 (D, [S("Schwelle 3 × 3 km", rep(3, 3, "T", 3)), S("Locker + Steigerungen", ezS(10)), S("Langer Lauf mit MRT-Finish", lrM(22, 4, "M"))]),
 (D, [S("Schwelle 5 × 1 km", rep(5, 1, "T", 1.5)), S("Locker + Steigerungen", ezS(8)), S("Langer Lauf", lr(18))]),
 (D, [S("Schwelle 2 × 4 km", rep(2, 4, "T", 3)), S("Marathontempo 7 km", tempo(3, 7, "M", 2)), S("Langer Lauf", lr(28))]),
 (D, [S("Intervalle 6 × 1 km", rep(6, 1, "I", 2)), S("Locker + Steigerungen", ezS(10)), S("Langer Lauf, 8 km MRT", lrM(18, 8, "M"))]),
 (D, [S("Schwelle 4 × 2 km", rep(4, 2, "T", 2)), S("Zieltempo 8 km", tempo(3, 8, "G", 2)), S("Langer Lauf", lr(28))]),
 (D, [S("Schwelle 3 × 2 km", rep(3, 2, "T", 2)), S("Locker + Steigerungen", ezS(9)), S("Langer Lauf, 8 km Zieltempo", lrM(14, 8, "G"))]),
 (D, [S("Intervalle 5 × 1 km", rep(5, 1, "I", 2)), S("Zieltempo 10 km", tempo(3, 10, "G", 1)), S("Langer Lauf", lr(30))]),
 ([1, 3, 5], [S("HM-Tempo 3 × 1 km", rep(3, 1, "H", 2)), S("Locker + Steigerungen", ezS(5, 4)),
              S("Halbmarathon Duisburg", [{"d": 2, "z": "E"}, {"d": 21.1, "z": "H"}, {"d": 1, "z": "E"}])]),
 ([2, 4, 6], [S("Erholungslauf", ez(7)), S("Schwelle 3 × 3 km", rep(3, 3, "T", 3)), S("Längster Lauf", lr(32))]),
 (D, [S("Intervalle 5 × 1 km", rep(5, 1, "I", 2)), S("Zieltempo 8 km", tempo(3, 8, "G", 1)), S("Marathon-Simulation 30 km", lrM(16, 14, "G"))]),
 (D, [S("Schwelle 3 × 2 km", rep(3, 2, "T", 2)), S("Zieltempo 6 km", tempo(3, 6, "G", 1)), S("Langer Lauf", lr(24))]),
 (D, [S("Schwelle 5 × 1 km", rep(5, 1, "T", 1.5)), S("Zieltempo 5 km", tempo(3, 5, "G", 2)), S("Langer Lauf 18 km", lrM(13, 5, "G"))]),
 (D, [S("Zieltempo 3 × 1 km", rep(3, 1, "G", 2)), S("Locker + Steigerungen", ezS(5, 4)), S("Düsseldorf Marathon", [{"d": 42.2, "z": "G"}])]),
]

# ---------- intervals.icu-Workouttext ----------
def fp(s):
    s = round(s); return f"{s // 60}:{s % 60:02d}"

def dur(x):
    if "d" in x:
        return f"{x['d']:g}km"
    sec = round(x["t"] * 60); m, s = divmod(sec, 60)
    if m == 0: return f"{s}s"
    return f"{m}m" + (f"{s:02d}" if s else "")

def line(x, p):
    a, b = zone(x["z"], p)
    lo, hi = sorted((a, b))
    return f"- {CUE[x['z']]} {dur(x)} {fp(lo)}-{fp(hi)}/km Pace"

def header(x, i, n, nxt=None):
    if n == 1: return "Lauf"
    if i == 0 and nxt and "r" in nxt and nxt["s"][0]["z"] == "S": return "Locker"
    if n > 1 and i == 0 and x["z"] in "EL": return "Aufwärmen" if x["z"] == "E" else "Langer Lauf"
    if n > 1 and i == n - 1 and x["z"] == "E": return "Abkühlen"
    return "Hauptteil"

def workout_text(steps, p):
    parts = []
    n = len(steps)
    for i, x in enumerate(steps):
        if "r" in x:
            name = "Steigerungen" if x["s"][0]["z"] == "S" else "Hauptteil"
            parts.append(f"{name} {x['r']}x\n" + "\n".join(line(y, p) for y in x["s"]))
        else:
            parts.append(header(x, i, n, steps[i + 1] if i + 1 < n else None) + "\n" + line(x, p))
    return "\n\n".join(parts)

def km(steps, p):
    def seg(x):
        if "d" in x: return x["d"]
        a, b = zone(x["z"], p); return x["t"] * 60 / ((a + b) / 2)
    return sum(x["r"] * sum(seg(y) for y in x["s"]) if "r" in x else seg(x) for x in steps)

def parse_hm(t):
    parts = [int(v) for v in t.split(":")]
    if len(parts) != 3: raise ValueError
    return parts[0] * 3600 + parts[1] * 60 + parts[2]

def build(p, include_past):
    today = dt.date.today(); events = []
    for wi, (offs, sessions) in enumerate(W):
        for si, (off, s) in enumerate(zip(offs, sessions)):
            day = START + dt.timedelta(days=wi * 7 + off)
            if day < today and not include_past: continue
            k = km(s["steps"], p)
            desc = (f"Woche {wi} · ≈ {k:.1f} km · Plan: Düsseldorf 3:30".replace(".", ",", 1)
                    + ("\nOptional – nur wenn du Lust hast." if s["opt"] else "")
                    + "\n\n" + workout_text(s["steps"], p))
            events.append({
                "category": "WORKOUT", "type": "Run", "target": "PACE",
                "start_date_local": f"{day.isoformat()}T00:00:00",
                "name": s["n"], "description": desc,
                "external_id": f"dus330-w{wi:02d}-s{si}",
            })
    return events

def main():
    ap = argparse.ArgumentParser(description="Düsseldorf 3:30 Plan nach intervals.icu")
    ap.add_argument("--hm", default="1:45:00", help="Halbmarathon-Referenzzeit h:mm:ss (Standard 1:45:00)")
    ap.add_argument("--dry-run", action="store_true", help="nur anzeigen, nichts hochladen")
    ap.add_argument("--all", action="store_true", help="auch Einheiten in der Vergangenheit schreiben")
    a = ap.parse_args()
    try: p = parse_hm(a.hm) / 21.0975
    except ValueError: sys.exit("Zeit bitte als h:mm:ss angeben, z. B. --hm 1:42:30")

    events = build(p, a.all)
    if a.dry_run:
        for e in events[:6]:
            print(f"\n=== {e['start_date_local'][:10]} {e['name']} ===\n{e['description']}")
        print(f"\n… insgesamt {len(events)} Einheiten (Dry-Run, nichts hochgeladen).")
        return

    key = (os.environ.get("INTERVALS_API_KEY") or getpass.getpass("intervals.icu API-Schlüssel (Eingabe bleibt unsichtbar): ")).strip().strip('"').strip("'")
    if not key: sys.exit("Kein API-Schlüssel angegeben.")
    auth = base64.b64encode(f"API_KEY:{key}".encode()).decode()
    req = urllib.request.Request(
        "https://intervals.icu/api/v1/athlete/0/events/bulk?upsert=true",
        data=json.dumps(events).encode(), method="POST",
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json",
                 "Accept": "application/json", "User-Agent": "duesseldorf330-plan/1.1"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.loads(r.read().decode() or "[]")
        print(f"Fertig: {len(res)} Einheiten in intervals.icu eingetragen (Paces aus HM {a.hm}).")
        print("Die Zepp-App holt sich jeweils die nächste Woche auf die Uhr.")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:400]
        if e.code == 401:
            sys.exit(f"Fehler 401: intervals.icu hat den Schlüssel abgelehnt ({len(key)} Zeichen erkannt). Antwort: {body}")
        if e.code == 403:
            sys.exit(f"Fehler 403: Zugriff verweigert. Antwort: {body}")
        sys.exit(f"Fehler {e.code} von intervals.icu: {body}")
    except urllib.error.URLError as e:
        sys.exit(f"intervals.icu nicht erreichbar: {e.reason}")

if __name__ == "__main__":
    main()
