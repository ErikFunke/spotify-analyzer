#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
history.py
==========

Baut das Musikprofil aus der **Extended Streaming History** (Spotify-Download)
statt aus der Web-API.

Quelle: "Account-Daten anfordern" -> "Erweiterte Streaming-History" auf
https://www.spotify.com/account/privacy/  -> ZIP enthält
``Streaming_History_Audio_*.json``.

Vorteile gegenüber der API:
  * ECHTE Wiedergaben über Jahre (nicht nur 50 letzte / Top-50)
  * echte Hörzeiten (Stunde/Wochentag) über die gesamte Historie
  * echte Skip-Rate, Hörminuten, Entdeckungs-Zeitachse

Grenzen (gegenüber API): die History enthält KEINE Erscheinungsjahre,
Popularität, Explicit-Flags oder Genres. Genres werden - wie im API-Pfad -
extern (MusicBrainz/Last.fm) ergänzt. Erscheinungsjahr-/Popularitäts-basierte
Auswertungen (Reminiscence-Bump-Alter, Mainstream-Drift) entfallen daher.

Das erzeugte Profil hat dasselbe Schema wie der API-Pfad (spotify.py), damit
Dashboard, LLM-Markdown und JSON-Export unverändert funktionieren.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from analysis import compute_patterns
from genres import attach_genres_to_top_artists

# Ab dieser Spieldauer (ms) zählt eine Wiedergabe als "echt gehört" (kein Skip).
MIN_PLAY_MS = 30_000
TOP_LIMIT = 50
RECENT_LIMIT = 50


# --------------------------------------------------------------------------- #
# DATEIEN LADEN
# --------------------------------------------------------------------------- #
def find_history_files(path: str | Path) -> list[Path]:
    """Findet alle Audio-Streaming-History-JSONs (Video wird ignoriert)."""
    p = Path(path)
    if p.is_file():
        return [p]
    if not p.is_dir():
        return []
    files = sorted(p.glob("Streaming_History_Audio_*.json"))
    if not files:  # Fallback: irgendwelche JSONs, die nach Audio aussehen
        files = [f for f in sorted(p.glob("*.json"))
                 if "Video" not in f.name]
    return files


def load_events(files: list[Path], log=print) -> list[dict]:
    """Lädt alle Wiedergabe-Events; behält nur Musik (keine Podcasts/Hörbücher)."""
    events: list[dict] = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            log(f"   !! {f.name} nicht lesbar: {e}")
            continue
        n0 = len(events)
        for r in data:
            if not r.get("master_metadata_track_name"):
                continue  # Podcast/Hörbuch/Video -> raus
            events.append(r)
        log(f"   {f.name}: +{len(events) - n0} Musik-Wiedergaben")
    return events


# --------------------------------------------------------------------------- #
# HILFSFUNKTIONEN
# --------------------------------------------------------------------------- #
def _ts(r: dict) -> datetime | None:
    s = r.get("ts")
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _artist(r: dict) -> str | None:
    return r.get("master_metadata_album_artist_name")


def _slim_track_from_agg(agg: dict) -> dict:
    return {
        "name": agg["name"],
        "artists": [agg["artist"]] if agg["artist"] else [],
        "artist_ids": [None],
        "album": agg.get("album"),
        "image": None,
        "release_year": None,
        "popularity": None,
        "explicit": None,
        "duration_min": None,
        # History-Extras (vom restlichen Code ignoriert, aber im JSON sichtbar):
        "play_count": agg["plays"],
        "minutes": round(agg["ms"] / 60000, 1),
    }


def _top_tracks_in(window: list[dict]) -> list[dict]:
    """Top-Tracks eines Zeitfensters nach Anzahl 'echter' Wiedergaben."""
    agg: dict[str, dict] = {}
    for r in window:
        if (r.get("ms_played") or 0) < MIN_PLAY_MS:
            continue
        key = r.get("spotify_track_uri") or f"{r.get('master_metadata_track_name')}|{_artist(r)}"
        a = agg.get(key)
        if not a:
            a = agg[key] = {"name": r.get("master_metadata_track_name"),
                            "artist": _artist(r),
                            "album": r.get("master_metadata_album_album_name"),
                            "plays": 0, "ms": 0}
        a["plays"] += 1
        a["ms"] += r.get("ms_played") or 0
    ranked = sorted(agg.values(), key=lambda a: (a["plays"], a["ms"]), reverse=True)
    return [_slim_track_from_agg(a) for a in ranked[:TOP_LIMIT]]


def _top_artists_in(window: list[dict]) -> list[dict]:
    agg: dict[str, dict] = {}
    for r in window:
        if (r.get("ms_played") or 0) < MIN_PLAY_MS:
            continue
        name = _artist(r)
        if not name:
            continue
        a = agg.get(name)
        if not a:
            a = agg[name] = {"name": name, "plays": 0, "ms": 0}
        a["plays"] += 1
        a["ms"] += r.get("ms_played") or 0
    ranked = sorted(agg.values(), key=lambda a: (a["plays"], a["ms"]), reverse=True)
    return [{
        "name": a["name"], "genres": [], "popularity": None,
        "followers": None, "image": None,
        "play_count": a["plays"], "minutes": round(a["ms"] / 60000, 1),
    } for a in ranked[:TOP_LIMIT]]


# --------------------------------------------------------------------------- #
# HISTORY-SPEZIFISCHE GESAMT-STATISTIK
# --------------------------------------------------------------------------- #
def _history_stats(events: list[dict], dated: list[tuple[datetime, dict]]) -> dict:
    """Aggregat-Kennzahlen über die gesamte Hörhistorie (alles je gehört)."""
    total_ms = sum(r.get("ms_played") or 0 for r in events)
    real = [r for r in events if (r.get("ms_played") or 0) >= MIN_PLAY_MS]
    skipped = sum(1 for r in events if r.get("skipped"))

    by_year_ms: Counter = Counter()
    for dt, r in dated:
        by_year_ms[dt.year] += r.get("ms_played") or 0

    first = dated[0][0] if dated else None
    last = dated[-1][0] if dated else None
    return {
        "total_plays": len(events),
        "real_plays": len(real),
        "skipped_plays": skipped,
        "skip_rate": round(skipped / len(events), 3) if events else None,
        "total_minutes": round(total_ms / 60000),
        "total_hours": round(total_ms / 3_600_000, 1),
        "total_days_listened": round(total_ms / 86_400_000, 1),
        "date_range": [first.date().isoformat() if first else None,
                       last.date().isoformat() if last else None],
        "minutes_by_year": [[y, round(ms / 60000)] for y, ms in sorted(by_year_ms.items())],
    }


def _most_played(events: list[dict]) -> dict:
    """Meistgehörte Tracks/Artists über die GESAMTE Historie (alles je gehört) -
    bewusst getrennt von den API-'Top'-Listen (= erklärte Favoriten/Affinität)."""
    real = [r for r in events if (r.get("ms_played") or 0) >= MIN_PLAY_MS]
    track_agg: dict[str, dict] = {}
    artist_agg: dict[str, dict] = {}
    for r in real:
        name = r.get("master_metadata_track_name")
        art = _artist(r)
        key = r.get("spotify_track_uri") or f"{name}|{art}"
        t = track_agg.get(key)
        if not t:
            t = track_agg[key] = {"name": name, "artist": art, "ms": 0, "plays": 0}
        t["ms"] += r.get("ms_played") or 0
        t["plays"] += 1
        if art:
            a = artist_agg.get(art)
            if not a:
                a = artist_agg[art] = {"name": art, "ms": 0, "plays": 0}
            a["ms"] += r.get("ms_played") or 0
            a["plays"] += 1

    def trk(t):
        return {"name": t["name"], "artist": t["artist"],
                "plays": t["plays"], "minutes": round(t["ms"] / 60000, 1)}

    def art(a):
        return {"name": a["name"], "plays": a["plays"],
                "minutes": round(a["ms"] / 60000)}

    return {
        "tracks_by_plays": [trk(t) for t in sorted(
            track_agg.values(), key=lambda x: x["plays"], reverse=True)[:20]],
        "tracks_by_minutes": [trk(t) for t in sorted(
            track_agg.values(), key=lambda x: x["ms"], reverse=True)[:20]],
        "artists_by_plays": [art(a) for a in sorted(
            artist_agg.values(), key=lambda x: x["plays"], reverse=True)[:20]],
        "artists_by_minutes": [art(a) for a in sorted(
            artist_agg.values(), key=lambda x: x["ms"], reverse=True)[:20]],
        "unique_tracks": len(track_agg),
        "unique_artists": len(artist_agg),
    }


def _full_listening_times(dated: list[tuple[datetime, dict]]) -> dict:
    """Hörzeiten über die GESAMTE Historie (nicht nur 50 Plays wie bei der API)."""
    hour_counter: Counter = Counter()
    weekday_counter: Counter = Counter()
    for dt, r in dated:
        if (r.get("ms_played") or 0) < MIN_PLAY_MS:
            continue
        loc = dt.astimezone(timezone.utc)
        hour_counter[loc.hour] += 1
        weekday_counter[loc.weekday()] += 1
    if not hour_counter:
        return {}
    buckets = {"nacht_0_6": 0, "morgen_6_12": 0, "nachmittag_12_18": 0, "abend_18_24": 0}
    for h, c in hour_counter.items():
        key = ("nacht_0_6" if h < 6 else "morgen_6_12" if h < 12
               else "nachmittag_12_18" if h < 18 else "abend_18_24")
        buckets[key] += c
    return {
        "listening_by_hour": [[h, hour_counter.get(h, 0)] for h in range(24)],
        "listening_by_daytime": buckets,
        "listening_by_weekday": [weekday_counter.get(i, 0) for i in range(7)],
        "listening_by_daytime_hinweis": (
            "Basiert auf der GESAMTEN Streaming-History (UTC) - belastbare "
            "Tendenz, nicht nur ein 50-Plays-Fenster wie im API-Modus."),
    }


# --------------------------------------------------------------------------- #
# LADEN + ZUSAMMENFASSEN (für History-only UND Combined wiederverwendet)
# --------------------------------------------------------------------------- #
def load_history(path: str | Path, log=print) -> tuple[list[dict], list[tuple[datetime, dict]]]:
    """Lädt Events + nach Zeit sortierte (dt, event)-Paare. Wirft bei leer."""
    files = find_history_files(path)
    if not files:
        raise FileNotFoundError(
            f"Keine Streaming_History_Audio_*.json unter '{path}' gefunden.")
    log(f">> {len(files)} History-Datei(en) gefunden.")
    events = load_events(files, log=log)
    if not events:
        raise ValueError("Keine Musik-Wiedergaben in der Streaming-History.")
    log(f">> {len(events)} Musik-Wiedergaben gesamt.")
    dated = sorted(((dt, r) for r in events if (dt := _ts(r))), key=lambda x: x[0])
    if not dated:
        raise ValueError("Keine gültigen Zeitstempel in der Streaming-History.")
    return events, dated


def summarize_history(events: list[dict],
                      dated: list[tuple[datetime, dict]]) -> dict:
    """Export-Overlay: Gesamt-Kennzahlen, Meistgehörtes, echte Hörzeiten.
    Wird in den Combined-Modus über das API-Profil gelegt."""
    return {
        "history_stats": _history_stats(events, dated),
        "most_played": _most_played(events),
        "listening_times": _full_listening_times(dated),
    }


# --------------------------------------------------------------------------- #
# PROFIL BAUEN (nur Export)
# --------------------------------------------------------------------------- #
def build_profile_from_history(path: str | Path, log=print) -> dict:
    events, dated = load_history(path, log=log)
    anchor = dated[-1][0]  # "jetzt" = letzte Wiedergabe im Export
    cut_4w = anchor - timedelta(weeks=4)
    cut_6m = anchor - timedelta(days=183)

    win_4w = [r for dt, r in dated if dt >= cut_4w]
    win_6m = [r for dt, r in dated if dt >= cut_6m]
    win_all = [r for _, r in dated]

    log(">> Berechne Top-Tracks/-Artists je Zeitfenster ...")
    top_tracks = {
        "letzte_4_wochen": _top_tracks_in(win_4w),
        "letzte_6_monate": _top_tracks_in(win_6m),
        "all_time": _top_tracks_in(win_all),
    }
    top_artists = {
        "letzte_4_wochen": _top_artists_in(win_4w),
        "letzte_6_monate": _top_artists_in(win_6m),
        "all_time": _top_artists_in(win_all),
    }

    log(">> Reichere Genres an (MusicBrainz/Last.fm) ...")
    top_artists = attach_genres_to_top_artists(top_artists, log=log)

    # Zuletzt gehört: echte letzte 50 Wiedergaben (neueste zuerst, wie API)
    recently = [{
        "played_at": r.get("ts"),
        "track": r.get("master_metadata_track_name"),
        "artists": [_artist(r)] if _artist(r) else [],
    } for dt, r in reversed(dated[-RECENT_LIMIT:])]

    # "Bibliothek" = jeder je gehörte Track einmal, added_at = ERSTE Wiedergabe.
    # Liefert eine echte Entdeckungs-Zeitachse für die Trend-Analyse.
    log(">> Baue Entdeckungs-Bibliothek (erste Wiedergabe je Track) ...")
    first_seen: dict[str, dict] = {}
    for dt, r in dated:
        name = r.get("master_metadata_track_name")
        art = _artist(r)
        key = r.get("spotify_track_uri") or f"{name}|{art}"
        f = first_seen.get(key)
        if not f:
            first_seen[key] = {"name": name, "artist": art,
                               "album": r.get("master_metadata_album_album_name"),
                               "added_at": r.get("ts"), "plays": 1,
                               "ms": r.get("ms_played") or 0}
        else:
            f["plays"] += 1
            f["ms"] += r.get("ms_played") or 0
    saved = []
    for f in first_seen.values():
        row = _slim_track_from_agg({"name": f["name"], "artist": f["artist"],
                                    "album": f["album"], "plays": f["plays"],
                                    "ms": f["ms"]})
        row["added_at"] = f["added_at"]
        saved.append(row)

    log(">> Berechne Muster + Persönlichkeit ...")
    patterns = compute_patterns(top_tracks, top_artists, recently, saved)

    # Export-Overlay: echte Hörzeiten (statt 50-Plays-Fenster), Gesamt-Stats,
    # Meistgehörtes (alles je gehört).
    summary = summarize_history(events, dated)
    patterns.update(summary["listening_times"])
    hstats = summary["history_stats"]
    patterns["history_stats"] = hstats
    patterns["most_played"] = summary["most_played"]

    country = Counter(r.get("conn_country") for r in events if r.get("conn_country"))
    common_country = country.most_common(1)[0][0] if country else None

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": "extended_history",
        "user": {"display_name": "Extended Streaming History",
                 "country": common_country, "image": None},
        "note": (
            "Quelle: Spotify Extended Streaming History (Download). Echte "
            "Wiedergaben über " + (hstats["date_range"][0] or "?") + " bis " +
            (hstats["date_range"][1] or "?") + f" ({hstats['total_hours']} h, "
            f"{hstats['real_plays']} echte Plays). Genres extern ergänzt. "
            "Erscheinungsjahr/Popularität/Explicit liegen im Download nicht vor; "
            "release-year-/popularitäts-basierte Auswertungen (Alters-Schätzung, "
            "Mainstream-Drift) entfallen daher in diesem Modus."),
        "top_tracks": top_tracks,
        "top_artists": top_artists,
        "recently_played": recently,
        "saved_tracks_sample": saved,
        "patterns": patterns,
    }
