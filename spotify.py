#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spotify.py
==========

Greift deine persönlichen Spotify-Daten über die Web API ab, berechnet daraus
lokal Hör-Muster + Persönlichkeits-Tendenzen und erzeugt:

  1. spotify_export.json        -> vollständige Rohdaten + Kennzahlen
  2. music_profile_for_llm.md   -> kompakte LLM-Zusammenfassung mit Prompt

Außerdem Start des Web-Dashboards:
      python spotify.py --web        (öffnet hübsches UI im Browser)
      python spotify.py              (nur Daten einsammeln -> Dateien)

WICHTIG (Stand 2026): Die Endpunkte audio-features / audio-analysis /
recommendations / related-artists wurden von Spotify deprecatet. Genutzt werden
nur noch verfügbare Daten: Top-Listen, zuletzt Gehörtes, Bibliothek,
Popularität, Erscheinungsjahre, Genre-Tags.

------------------------------------------------------------------------------
EINRICHTUNG (auch unter Windows einfach)
------------------------------------------------------------------------------
1. App registrieren: https://developer.spotify.com/dashboard  ("Create app")
   Redirect URI eintragen:  http://127.0.0.1:8888/callback
2. pip install -r requirements.txt
3. .env-Datei anlegen (Kopie von .env.example) ODER Umgebungsvariablen setzen:
       SPOTIPY_CLIENT_ID=...
       SPOTIPY_CLIENT_SECRET=...
       SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
4. Start:  python spotify.py --web      (oder run.bat doppelklicken)
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------- #
# WINDOWS-FREUNDLICHKEIT
# --------------------------------------------------------------------------- #
# Konsole auf UTF-8 zwingen, damit Umlaute/Emojis nicht crashen (cp1252).
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Alle Pfade relativ zum Skript -> egal von wo (Doppelklick) gestartet wird.
BASE_DIR = Path(__file__).resolve().parent

# .env laden, falls vorhanden (kein harter Zwang auf python-dotenv).
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except Exception:
    # Mini-Fallback-Parser, falls python-dotenv fehlt.
    envfile = BASE_DIR / ".env"
    if envfile.exists():
        for line in envfile.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
except ImportError:
    sys.exit("Fehlt: spotipy. Installiere alles mit:  pip install -r requirements.txt")

from analysis import compute_patterns
from genres import attach_genres_to_top_artists

# --------------------------------------------------------------------------- #
# CONFIG
# --------------------------------------------------------------------------- #
CONFIG = {
    "client_id":     os.getenv("SPOTIPY_CLIENT_ID", ""),
    "client_secret": os.getenv("SPOTIPY_CLIENT_SECRET", ""),
    "redirect_uri":  os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
}

SCOPES = "user-top-read user-read-recently-played user-library-read"
MAX_SAVED_TRACKS = 5000

CACHE_PATH = str(BASE_DIR / ".spotify_cache")
OUT_JSON = str(BASE_DIR / "spotify_export.json")
OUT_PROMPT = str(BASE_DIR / "music_profile_for_llm.md")


# --------------------------------------------------------------------------- #
# CLIENT / AUTH
# --------------------------------------------------------------------------- #
def make_oauth(open_browser: bool = True) -> SpotifyOAuth:
    if not CONFIG["client_id"] or not CONFIG["client_secret"]:
        sys.exit(
            "Keine Zugangsdaten gefunden.\n"
            "Lege eine .env-Datei an (siehe .env.example) oder setze die "
            "Umgebungsvariablen SPOTIPY_CLIENT_ID und SPOTIPY_CLIENT_SECRET."
        )
    return SpotifyOAuth(
        client_id=CONFIG["client_id"],
        client_secret=CONFIG["client_secret"],
        redirect_uri=CONFIG["redirect_uri"],
        scope=SCOPES,
        cache_path=CACHE_PATH,
        open_browser=open_browser,
    )


def get_client(open_browser: bool = True) -> "spotipy.Spotify":
    auth = make_oauth(open_browser=open_browser)
    return spotipy.Spotify(auth_manager=auth, requests_timeout=20, retries=3)


# --------------------------------------------------------------------------- #
# SLIM-HELFER
# --------------------------------------------------------------------------- #
def parse_year(release_date):
    if not release_date:
        return None
    try:
        return int(str(release_date)[:4])
    except ValueError:
        return None


def slim_track(t: dict) -> dict:
    return {
        "name": t.get("name"),
        "artists": [a.get("name") for a in t.get("artists", [])],
        "artist_ids": [a.get("id") for a in t.get("artists", [])],
        "album": t.get("album", {}).get("name"),
        "image": (t.get("album", {}).get("images") or [{}])[0].get("url"),
        "release_year": parse_year(t.get("album", {}).get("release_date")),
        "popularity": t.get("popularity"),
        "explicit": t.get("explicit"),
        "duration_min": round(t.get("duration_ms", 0) / 60000, 2),
    }


def slim_artist(a: dict) -> dict:
    return {
        "name": a.get("name"),
        "genres": a.get("genres", []),
        "popularity": a.get("popularity"),
        "followers": a.get("followers", {}).get("total"),
        "image": (a.get("images") or [{}])[0].get("url"),
    }


# --------------------------------------------------------------------------- #
# DATENABRUF
# --------------------------------------------------------------------------- #
def fetch_top(sp, kind: str) -> dict:
    ranges = {"short_term": "letzte_4_wochen",
              "medium_term": "letzte_6_monate",
              "long_term": "all_time"}
    out = {}
    for api_range, label in ranges.items():
        items = (sp.current_user_top_artists(limit=50, time_range=api_range)
                 if kind == "artists"
                 else sp.current_user_top_tracks(limit=50, time_range=api_range))
        rows = items.get("items", [])
        out[label] = ([slim_artist(x) for x in rows] if kind == "artists"
                      else [slim_track(x) for x in rows])
    return out


def fetch_recently_played(sp) -> list:
    items = sp.current_user_recently_played(limit=50).get("items", [])
    return [{
        "played_at": it.get("played_at"),
        "track": it.get("track", {}).get("name"),
        "artists": [a.get("name") for a in it.get("track", {}).get("artists", [])],
    } for it in items]


def fetch_saved_tracks(sp, cap: int = MAX_SAVED_TRACKS, progress=None) -> list:
    out, offset = [], 0
    while offset < cap:
        page = sp.current_user_saved_tracks(limit=50, offset=offset)
        items = page.get("items", [])
        if not items:
            break
        for it in items:
            row = slim_track(it.get("track", {}))
            row["added_at"] = it.get("added_at")
            out.append(row)
        offset += 50
        if progress:
            progress(len(out))
    return out


# --------------------------------------------------------------------------- #
# PROFIL BAUEN (von CLI und Web genutzt)
# --------------------------------------------------------------------------- #
def build_profile(sp, log=print) -> dict:
    me = sp.current_user()
    log(f">> Angemeldet als: {me.get('display_name')} ({me.get('id')})")
    log(">> Lade Top-Tracks ...")
    top_tracks = fetch_top(sp, "tracks")
    log(">> Lade Top-Artists ...")
    top_artists = fetch_top(sp, "artists")
    log(">> Reichere Genres an (Spotify liefert keine mehr) ...")
    top_artists = attach_genres_to_top_artists(top_artists, log=log)
    log(">> Lade zuletzt Gehörtes ...")
    recently = fetch_recently_played(sp)
    log(">> Lade gespeicherte Titel (komplette Bibliothek) ...")
    saved = fetch_saved_tracks(sp, progress=lambda n: log(f"   ... {n} Titel"))
    log(f"   -> {len(saved)} Titel geladen")

    log(">> Berechne Muster + Persönlichkeit ...")
    patterns = compute_patterns(top_tracks, top_artists, recently, saved)

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "user": {"display_name": me.get("display_name"),
                 "country": me.get("country"),
                 "image": (me.get("images") or [{}])[0].get("url")},
        "note": ("Spotify (Dev-Mode 2026) liefert keine audio-features, Genres, "
                 "Artist-/Track-Popularität oder Follower mehr. Genres extern "
                 "(MusicBrainz/Last.fm) ergänzt; Mainstream/Nische entfällt."),
        "top_tracks": top_tracks,
        "top_artists": top_artists,
        "recently_played": recently,
        "saved_tracks_sample": saved,
        "patterns": patterns,
    }


def save_profile(profile: dict) -> None:
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    md = build_llm_markdown(profile)
    with open(OUT_PROMPT, "w", encoding="utf-8") as f:
        f.write(md)


def load_profile() -> dict | None:
    p = Path(OUT_JSON)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# LLM-PROMPT
# --------------------------------------------------------------------------- #
def build_llm_markdown(profile: dict) -> str:
    p = profile["patterns"]
    ta = profile["top_artists"]
    tt = profile["top_tracks"]

    def fmt_list(items, n=10):
        return ", ".join(items[:n]) if items else "(keine Daten)"

    md = ["# Musikprofil zur LLM-Analyse\n",
          f"_Erzeugt am {profile['generated_at']} aus Spotify-Daten._\n",
          "## Auftrag an das auswertende Modell\n",
          ("Du bist Musikpsychologe. Analysiere das Profil in DREI Teilen und "
           "stütze dich strikt auf die unten mitgelieferten empirischen "
           "Korrelationen (Greenberg et al. 2016; Rentfrow & Gosling 2003; "
           "Bonneville-Roussy et al. 2013). Erfinde keine Zusammenhänge.\n\n"
           "**1) Persönlichkeit (Big Five).** Leite Tendenzen aus dem "
           "Arousal/Valence/Depth-Profil (AVD) ab. Nutze die AVD↔Big-Five-"
           "Korrelationstabelle unten. Es werden NUR die drei Merkmale mit "
           "belastbarem Bezug geliefert: Offenheit (über Depth, r≈.13, am "
           "robustesten), Verträglichkeit (−Arousal, r≈−.12) und "
           "Gewissenhaftigkeit (−Arousal, r≈−.08). Extraversion und "
           "Neurotizismus sind aus Musik kaum vorhersagbar (r≈.05) und werden "
           "bewusst NICHT bewertet - bitte ebenfalls nicht spekulieren.\n\n"
           "**2) Lebensphase & Alter.** Schätze die Lebensphase aus (a) dem "
           "'Reminiscence Bump' (stärkste Prägung mit ~14-24 J. → prägende "
           "Musikjahre/Altersspanne unten) und (b) Bonneville-Roussy: intense/"
           "contemporary Musik dominiert in der Jugend, sophisticated/"
           "unpretentious steigt mit dem Alter, musikalisches Engagement sinkt. "
           "Formuliere eine Hypothese zur aktuellen Lebensphase und wie der "
           "Geschmack dazu passt.\n\n"
           "**3) Trends im Hörverhalten.** Deute die Zeitreihen (was wird wann "
           "gespeichert): Mainstream-Drift, Nostalgie vs. Neugier (Musik-Alter "
           "beim Speichern), Sammel-Tempo, Entdeckungsrate. Erzähle die "
           "Entwicklung als Verlauf (Stabilität vs. Exploration, mögliche "
           "Lebensübergänge).\n\n"
           "**Einordnung, die du einhalten MUSST:**\n"
           "- Musik↔Persönlichkeit ist real, aber statistisch **schwach bis "
           "moderat** (r≈.05-.20) und nur über Gruppen belastbar - keine "
           "Diagnose für die Einzelperson.\n"
           "- Formuliere **Hypothesen/Tendenzen**, gib Unsicherheit offen an.\n"
           "- Klangmerkmale (Energy/Tempo) fehlen (Spotify-API 2024 "
           "abgeschaltet); AVD ist hier aus Genres geschätzt - beachte das.\n")]

    md.append("## Empirische Bezugswerte (für deine Herleitung)\n")
    md.append("AVD↔Big-Five-Korrelationen (Greenberg 2016, Tab. A1) - nur die "
              "belastbaren Domänen:\n")
    md.append("| Domäne | Arousal | Valence | Depth |")
    md.append("|---|---|---|---|")
    md.append("| Offenheit | +.02 | +.04 | **+.13** |")
    md.append("| Verträglichkeit | **−.12** | −.02 | +.05 |")
    md.append("| Gewissenhaftigkeit | −.08 | .00 | +.03 |")
    md.append("\n(Extraversion und Neurotizismus korrelieren nur ~r.05 mit "
              "Musik-Attributen und werden weggelassen.)")
    md.append("Vielfalt↔Domäne: Offenheit +.13, Verträglichkeit +.10.\n")

    md.append("## Daten\n")

    avd = p.get("avd_profile") or {}
    if avd.get("arousal") is not None:
        md.append("### AVD-Profil (geschätzt aus Genres, 0-1)\n")
        md.append(f"- **Arousal/Intensität:** {avd['arousal']} "
                  "(hoch=intensiv/kraftvoll, niedrig=ruhig/sanft)")
        md.append(f"- **Valence/Stimmung:** {avd['valence']} "
                  "(hoch=fröhlich/lebhaft, niedrig=melancholisch)")
        md.append(f"- **Depth/Tiefe:** {avd['depth']} "
                  "(hoch=komplex/intellektuell, niedrig=Party/eingängig)")
        md.append(f"- _Abdeckung: {round(avd['coverage']*100)}% der Genre-Gewichte._\n")

    md.append("### Genre-Schwerpunkte (gewichtet)\n")
    for g, w in p.get("genre_ranking", []):
        md.append(f"- {g} ({w})")
    md.append("")

    mm = p.get("music_model")
    if mm and mm.get("shares"):
        md.append("### MUSIC-Modell (Geschmacks-Fingerprint)\n")
        for dim, share in sorted(mm["shares"].items(), key=lambda kv: -kv[1]):
            md.append(f"- {mm['labels'][dim]}: {round(share*100)}%")
        md.append("")

    bf = p.get("big_five")
    if bf and bf.get("traits"):
        md.append("### Big-Five-Tendenzen (aus AVD abgeleitet)\n")
        for key, t in bf["traits"].items():
            drv = ("; ".join(t["drivers"]) or "—")
            md.append(f"- {t['name']}: {t['score']}/100 "
                      f"(Konfidenz {t['confidence']}; Treiber: {drv})")
        md.append(f"\n_Methode: {bf.get('method', '')}. Konfidenz gesamt: "
                  f"{bf['overall_confidence']}._")
        md.append(f"_{bf['disclaimer']}_\n")

    lp = p.get("life_phase") or {}
    rem = lp.get("reminiscence")
    if rem:
        md.append("### Lebensphase & Alter (sehr grobe Schätzung)\n")
        md.append(f"- Prägende Musikjahre (Peak): **{rem['formative_peak_year']}** "
                  f"(Fenster {rem['formative_window'][0]}–{rem['formative_window'][1]}, "
                  f"{round(rem['bump_share']*100)}% der Bibliothek).")
        if rem.get("estimated_age_range"):
            md.append(f"- Daraus geschätztes Alter: **~{rem['estimated_age_center']}** "
                      f"(Spanne {rem['estimated_age_range'][0]}–"
                      f"{rem['estimated_age_range'][1]}), Geburtsjahr ~"
                      f"{rem['estimated_birth_year']} (Stand {lp.get('now_year')}).")
        md.append(f"- _{rem['interpretation']}_")
        md.append("")

    tr = p.get("trends") or {}
    if tr.get("summary"):
        s = tr["summary"]
        names = {"mainstream_trend": "Mainstream-Drift",
                 "nostalgia_trend": "Nostalgie vs. Neugier (Musik-Alter beim Speichern)",
                 "engagement_trend": "Sammel-Tempo",
                 "discovery_trend": "Entdeckungsrate (neue Artists)"}
        md.append("### Trends im Hörverhalten (aus Speicher-Zeitpunkten)\n")
        for key, label in names.items():
            if s.get(key):
                md.append(f"- {label}: **{s[key]['label']}** (Steigung {s[key]['slope']})")
        md.append("\n**Jahres-Kohorten** (Jahr · Titel · Ø-Musik-Alter · neue Artists):")
        for c in tr.get("cohorts", []):
            pop = f" · pop {c['median_popularity']}" if c.get("median_popularity") is not None else ""
            md.append(f"- {c['year']}: {c['added']}{pop} · "
                      f"Alter {c['median_music_age']} · +{c['new_artists']} neu")
        md.append(f"\n_{tr.get('hinweis', '')}_\n")

    md.append("### Top-Artists\n")
    md.append(f"- **Letzte 4 Wochen:** {fmt_list([a['name'] for a in ta.get('letzte_4_wochen', [])])}")
    md.append(f"- **Letzte 6 Monate:** {fmt_list([a['name'] for a in ta.get('letzte_6_monate', [])])}")
    md.append(f"- **All-Time:** {fmt_list([a['name'] for a in ta.get('all_time', [])])}\n")

    md.append("### Top-Tracks (All-Time laut API, Auswahl)\n")
    md.append("_Hinweis: Die API-'all-time'-Top-Tracks nutzen ein anderes, "
              "trägeres Verfahren als Spotifys 'On Repeat'/Wrapped-Playlists. "
              "Aktuelle Dauerschleifen siehe Abschnitt 'Replay-Verhalten'._\n")
    for t in tt.get("all_time", [])[:15]:
        md.append(f"- {t.get('name')} - {', '.join(t.get('artists', []))} "
                  f"({t.get('release_year')})")
    md.append("")

    rp = p.get("replay") or {}
    if rp:
        md.append("### Replay-Verhalten (letzte 50 Wiedergaben)\n")
        md.append(f"- Wiederhol-Rate: **{int(rp['repeat_rate']*100)}%** "
                  f"({rp['unique_tracks']} verschiedene von {rp['window_plays']} "
                  f"Plays) → {rp['intensity']}")
        if rp.get("obsession"):
            o = rp["obsession"]
            md.append(f"- Aktuelle Obsession: **{o['track']}** – {o['artists']} "
                      f"({o['plays']}× gespielt)")
        if rp.get("longest_streak"):
            ls = rp["longest_streak"]
            md.append(f"- Längste Dauerschleife: {ls['plays']}× am Stück "
                      f"({ls['track']}); {rp['back_to_back_loops']} direkte Wiederholungen")
        if rp.get("plays_per_hour"):
            md.append(f"- Intensität: {rp['plays_per_hour']} Plays/Stunde "
                      f"über {rp['span_hours']} h")
        if rp.get("most_replayed"):
            md.append("- Meist wiederholt: " + "; ".join(
                f"{t} ({c}×)" for t, _a, c in rp["most_replayed"][:5]))
        md.append(f"\n_{rp['hinweis']}_\n")

    if "popularity" in p:
        pp = p["popularity"]
        md.append("### Mainstream- vs. Nischen-Neigung\n")
        md.append(f"- Ø Popularität: **{pp['mittelwert']}** (Median {pp['median']}, "
                  f"Spanne {pp['min']}-{pp['max']}, n={pp['stichprobe']}; "
                  f"{pp['interpretation_hinweis']})\n")

    if "genre_entropy" in p:
        md.append("### Vielfalt\n")
        md.append(f"- Genre-Breite (Entropie 0-1): **{p['genre_entropy']}** "
                  f"über {p.get('genre_count', 0)} Genres\n")

    if "release_decades" in p:
        md.append("### Ära-Präferenz (Top-Tracks)\n")
        for dec, cnt in p["release_decades"]:
            md.append(f"- {dec}er: {cnt} Titel")
        md.append("")

    if "taste_stability" in p:
        ts = p["taste_stability"]
        md.append("### Geschmacks-Stabilität\n")
        md.append(f"- {ts['ueberschneidung_artists']} von {ts['von_kurzfrist_top']} "
                  f"aktuellen Top-Artists sind All-Time-Favoriten "
                  f"({ts['kurz_vs_alltime_pct']}%).")
        md.append(f"- {ts['interpretation_hinweis']}\n")

    if "listening_by_daytime" in p:
        md.append("### Hörzeiten (grobe Tendenz, letzte 50 Wiedergaben)\n")
        for bucket, cnt in p["listening_by_daytime"].items():
            md.append(f"- {bucket}: {cnt}")
        md.append(f"- _{p.get('listening_by_daytime_hinweis', '')}_\n")

    if "explicit_ratio" in p:
        md.append("### Sonstiges\n")
        md.append(f"- Explicit-Anteil der Top-Tracks: {int(p['explicit_ratio']*100)}%")
        if "avg_track_duration_min" in p:
            md.append(f"- Ø Track-Länge (Bibliothek): {p['avg_track_duration_min']} min")
        md.append("")

    if "library" in p:
        lib = p["library"]
        md.append("### Bibliothek\n")
        md.append(f"- Gespeicherte Titel: {lib['gespeicherte_titel']}")
        md.append(f"- Unterschiedliche Artists: {lib['unterschiedliche_artists']}")
        md.append(f"- Konzentration (Gini): {lib['artist_konzentration_gini']} "
                  f"(Top-15 = {lib['top15_anteil_pct']}% der Titel)\n")

    if "library_added_by_year" in p:
        md.append("### Zeitachse: Titel hinzugefügt (pro Jahr)\n")
        for year, cnt in p["library_added_by_year"]:
            md.append(f"- {year}: {cnt}")
        md.append("")

    if "library_release_eras_5y" in p:
        st = p.get("library_release_year_stats", {})
        md.append("### Ära über die gesamte Bibliothek\n")
        md.append(f"- Erscheinungsjahre {st.get('frühestes')}–{st.get('spätestes')}, "
                  f"Median {st.get('median')} (über {st.get('anzahl_mit_jahr')} Titel)\n")
        for dec, cnt in p.get("library_release_decades", []):
            md.append(f"- {dec}er: {cnt}")
        md.append("")

    return "\n".join(md)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def run_cli() -> None:
    print(">> Verbinde mit Spotify ...")
    sp = get_client(open_browser=True)
    profile = build_profile(sp)
    save_profile(profile)
    print(f">> Rohdaten gespeichert: {OUT_JSON}")
    print(f">> LLM-Profil gespeichert: {OUT_PROMPT}")
    print("\nFertig. Tipp: 'python spotify.py --web' für das Dashboard.")


def reprocess(in_path: str, log=print) -> None:
    """Vorhandenes Export-JSON neu auswerten: Genres extern nachladen +
    Kennzahlen/Persönlichkeit neu berechnen - ohne neuen Spotify-Abruf."""
    src = Path(in_path)
    if not src.exists():
        sys.exit(f"Datei nicht gefunden: {in_path}")
    profile = json.loads(src.read_text(encoding="utf-8"))
    log(f">> Lade {in_path} ({len(profile.get('saved_tracks_sample', []))} Titel)")
    log(">> Reichere Genres an ...")
    profile["top_artists"] = attach_genres_to_top_artists(profile["top_artists"], log=log)
    log(">> Berechne Muster + Persönlichkeit neu ...")
    profile["patterns"] = compute_patterns(
        profile["top_tracks"], profile["top_artists"],
        profile.get("recently_played", []), profile.get("saved_tracks_sample", []))
    save_profile(profile)
    gc = profile["patterns"].get("genre_count", 0)
    log(f">> Fertig. Genres jetzt: {gc}. Gespeichert: {OUT_JSON} + {OUT_PROMPT}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Spotify Musikprofil + Dashboard")
    parser.add_argument("--web", action="store_true",
                        help="Web-Dashboard starten (Browser öffnet automatisch)")
    parser.add_argument("--port", type=int, default=8888,
                        help="Port fürs Web-Dashboard (Default 8888)")
    parser.add_argument("--no-browser", action="store_true",
                        help="Browser nicht automatisch öffnen")
    parser.add_argument("--reprocess", metavar="FILE", nargs="?", const=OUT_JSON,
                        help="Vorhandenes Export-JSON neu auswerten (Genres "
                             "nachladen) statt neu von Spotify zu holen")
    args = parser.parse_args()

    if args.reprocess:
        reprocess(args.reprocess)
    elif args.web:
        import app as webapp
        webapp.run(port=args.port, open_browser=not args.no_browser)
    else:
        run_cli()


if __name__ == "__main__":
    main()
