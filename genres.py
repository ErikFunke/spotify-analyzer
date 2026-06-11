#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
genres.py
=========

Genre-Anreicherung, weil Spotify seit der 2026-Migration für Development-Mode-
Apps KEINE Genres mehr liefert (/me/top/artists -> genres=[], /artists -> 403).

Wir holen die Genres/Tags daher extern:
  * MusicBrainz  (kein API-Key nötig, Standard) - 1 Anfrage/Sekunde
  * Last.fm      (optional, schneller + bessere Tags) - wenn LASTFM_API_KEY gesetzt

Ergebnisse werden in .genre_cache.json zwischengespeichert, damit weitere Läufe
sofort sind und das Rate-Limit geschont wird.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
CACHE_PATH = BASE_DIR / ".genre_cache.json"

USER_AGENT = "SpotifyMusicProfile/1.0 (https://github.com/local; personal-use)"
MB_URL = "https://musicbrainz.org/ws/2/artist"
LASTFM_URL = "https://ws.audioscrobbler.com/2.0/"

# Tags, die keine Genres sind -> raus (Substring, lowercase).
_STOP = (
    "seen live", "favorite", "favourite", "spotify", "vocalist", "vocalists",
    "beautiful", "awesome", "cool", "love", "best", "epic", "my ", "amazing",
    "under ", "listened", "discover", "good", "great", "albums i own",
    "german", "deutsch", "british", "english", "american", "usa", "uk ",
    "france", "french", "spanish", "swedish", "norwegian", "finnish", "polish",
    "australian", "canadian", "dutch", "italian", "japanese", "korean",
    "male", "female", "band", "artist", "singer", "instrument",
)
_STOP_EXACT = {
    "uk", "us", "00s", "10s", "20s", "30s", "40s", "50s", "60s", "70s",
    "80s", "90s", "2000s", "2010s", "2020s", "all", "other", "misc",
}


def _is_genre(tag: str) -> bool:
    t = tag.strip().lower()
    if not t or t in _STOP_EXACT:
        return False
    if t.isdigit():
        return False
    return not any(s in t for s in _STOP)


def _clean(tags: list[str], limit: int = 6) -> list[str]:
    out, seen = [], set()
    for t in tags:
        t = t.strip().lower()
        if _is_genre(t) and t not in seen:
            seen.add(t)
            out.append(t)
        if len(out) >= limit:
            break
    return out


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    try:
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# PROVIDER
# --------------------------------------------------------------------------- #
def _lastfm(name: str, key: str) -> list[str] | None:
    try:
        r = requests.get(LASTFM_URL, params={
            "method": "artist.gettoptags", "artist": name,
            "api_key": key, "format": "json", "autocorrect": 1},
            headers={"User-Agent": USER_AGENT}, timeout=12)
        if r.status_code != 200:
            return None
        tags = r.json().get("toptags", {}).get("tag", [])
        # nach count sortiert; nur einigermaßen relevante
        names = [t["name"] for t in tags if int(t.get("count", 0)) >= 10]
        return _clean(names or [t["name"] for t in tags])
    except Exception:
        return None


def _musicbrainz(name: str) -> list[str] | None:
    try:
        r = requests.get(MB_URL, params={
            "query": f'artist:"{name}"', "fmt": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT}, timeout=15)
        if r.status_code != 200:
            return None
        arr = r.json().get("artists", [])
        if not arr:
            return []
        a = arr[0]
        tags = a.get("tags", []) or []
        genres = a.get("genres", []) or []
        pool = sorted(genres + tags, key=lambda t: -int(t.get("count", 0)))
        return _clean([t["name"] for t in pool])
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# ÖFFENTLICH
# --------------------------------------------------------------------------- #
def enrich_artist_genres(names, log=print) -> dict:
    """names -> {name: [genre, ...]}. Cached + rate-limited."""
    cache = _load_cache()
    uniq = []
    seen = set()
    for n in names:
        if n and n not in seen:
            seen.add(n)
            uniq.append(n)

    lastfm_key = os.getenv("LASTFM_API_KEY", "").strip()
    source = "Last.fm" if lastfm_key else "MusicBrainz"

    todo = [n for n in uniq if n not in cache]
    if todo:
        log(f"   Genre-Anreicherung via {source}: {len(todo)} neue Artists "
            f"({len(uniq) - len(todo)} aus Cache) ...")

    done = 0
    for i, name in enumerate(uniq, 1):
        if name in cache:
            continue
        if lastfm_key:
            tags = _lastfm(name, lastfm_key)
            if tags is None:
                tags = _musicbrainz(name) or []
        else:
            tags = _musicbrainz(name) or []
            time.sleep(1.1)  # MusicBrainz: max 1 req/s
        cache[name] = tags
        done += 1
        if done % 10 == 0:
            log(f"   ... {done}/{len(todo)} angereichert")
            _save_cache(cache)

    _save_cache(cache)
    matched = sum(1 for n in uniq if cache.get(n))
    log(f"   Genres gefunden für {matched}/{len(uniq)} Artists.")
    return {n: cache.get(n, []) for n in uniq}


def attach_genres_to_top_artists(top_artists: dict, log=print) -> dict:
    """Füllt das genres-Feld aller Top-Artists (alle Zeiträume) extern auf."""
    names = []
    for arr in top_artists.values():
        names += [a.get("name") for a in arr if a.get("name")]
    mapping = enrich_artist_genres(names, log=log)
    for arr in top_artists.values():
        for a in arr:
            if not a.get("genres"):
                a["genres"] = mapping.get(a.get("name"), [])
    return top_artists
