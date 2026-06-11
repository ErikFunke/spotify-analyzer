#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analysis.py
===========

Reine Auswertungslogik (keine Netzwerk-/IO-Abhängigkeiten).

Wissenschaftliche Grundlage
---------------------------
* Greenberg, Kosinski, Stillwell, Monteiro, Levitin & Rentfrow (2016):
  "The Song Is You" -> Musikpräferenzen lassen sich auf drei Attribut-
  Dimensionen abbilden: AROUSAL (Erregung/Intensität), VALENCE (Stimmung,
  fröhlich<->traurig) und DEPTH (Tiefe/Komplexität/Intellekt). Tabelle A1 des
  Papers liefert die EMPIRISCHEN Korrelationen zwischen diesen Dimensionen und
  den Big-Five-Domänen sowie dem Alter. Genau diese Korrelationen werden hier
  zur Persönlichkeits- und Lebensphasen-Schätzung verwendet.
* Rentfrow & Gosling (2003) / Rentfrow, Goldberg & Levitin (2011, MUSIC):
  Genre<->Persönlichkeit, Offenheit als robustester Prädiktor.
* Bonneville-Roussy, Rentfrow, Xu & Potter (2013): Alterstrends - intense/
  contemporary Musik dominiert in der Jugend, sophisticated/unpretentious
  nimmt mit dem Alter zu; musikalisches Engagement sinkt mit dem Alter.
* "Reminiscence Bump": stärkste musikalische Bindung an Musik aus der Zeit
  ~Alter 14-24 -> erlaubt eine grobe Alters-/Lebensphasen-Schätzung aus den
  Erscheinungsjahren der Bibliothek.

WICHTIG: Alle Persönlichkeits-/Alterswerte sind TENDENZEN/HYPOTHESEN. Der
Zusammenhang ist statistisch schwach bis moderat (r ~ .05-.20) und nur über
Gruppen belastbar. Am robustesten: Offenheit (über Depth, r=.13).
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timezone


# --------------------------------------------------------------------------- #
# GENRE -> AROUSAL / VALENCE / DEPTH   (0..1)
# --------------------------------------------------------------------------- #
# Werte qualitativ aus den Attribut-Ladungen (Greenberg 2016, Tab. 1) +
# Genre<->Attribut-Literatur abgeleitet.
#   Arousal: intensiv/kraftvoll/aggressiv  <->  sanft/ruhig/mellow
#   Valence: fröhlich/lebhaft/fun          <->  traurig/depressiv/emotional
#   Depth:   intelligent/komplex/poetisch  <->  Party/tanzbar
AVD_GENRES: list[tuple[tuple[str, ...], tuple[float, float, float]]] = [
    (("death metal", "black metal", "thrash", "grindcore", "metalcore", "deathcore"), (0.97, 0.22, 0.55)),
    (("metal", "djent", "doom", "sludge"), (0.92, 0.28, 0.55)),
    (("hardcore", "screamo", "punk"), (0.90, 0.33, 0.42)),
    (("grunge", "nu metal", "hard rock"), (0.85, 0.35, 0.48)),
    (("emo",), (0.66, 0.28, 0.55)),
    (("post-rock", "post rock", "shoegaze", "post-punk", "math rock"), (0.55, 0.35, 0.78)),
    (("prog", "art rock", "psychedelic"), (0.65, 0.42, 0.80)),
    (("indie rock", "alt", "alternative", "garage rock"), (0.62, 0.45, 0.68)),
    (("rock",), (0.66, 0.46, 0.66)),
    (("dubstep", "drum and bass", "dnb", "breakcore", "hardstyle"), (0.88, 0.55, 0.40)),
    (("techno", "trance", "hardstyle"), (0.84, 0.62, 0.35)),
    (("house", "edm", "electro", "big room"), (0.80, 0.72, 0.33)),
    (("hyperpop",), (0.82, 0.66, 0.38)),
    (("phonk", "trap"), (0.76, 0.45, 0.38)),
    (("drill", "grime"), (0.72, 0.38, 0.48)),
    (("conscious hip hop", "jazz rap", "abstract hip hop"), (0.52, 0.45, 0.80)),
    (("hip hop", "hip-hop", "rap"), (0.62, 0.50, 0.58)),
    (("disco", "funk", "boogie"), (0.62, 0.86, 0.46)),
    (("neo soul", "soul", "r&b", "rnb", "motown"), (0.50, 0.66, 0.62)),
    (("reggaeton", "dancehall", "afrobeat", "afro", "amapiano"), (0.66, 0.84, 0.40)),
    (("reggae", "ska", "dub"), (0.55, 0.80, 0.50)),
    (("latin", "salsa", "cumbia", "bachata"), (0.62, 0.82, 0.45)),
    (("bebop", "swing", "big band", "hard bop"), (0.50, 0.58, 0.90)),
    (("jazz", "bossa", "fusion"), (0.42, 0.55, 0.92)),
    (("blues",), (0.46, 0.40, 0.80)),
    (("opera", "operatic"), (0.55, 0.50, 0.95)),
    (("classical", "orchestra", "baroque", "romantic era", "neoclassical", "chamber", "contemporary classical"), (0.36, 0.50, 0.95)),
    (("soundtrack", "score", "cinematic", "instrumental"), (0.45, 0.45, 0.82)),
    (("singer-songwriter", "singer songwriter", "songwriter"), (0.42, 0.50, 0.78)),
    (("folk", "americana", "bluegrass"), (0.42, 0.56, 0.72)),
    (("country",), (0.50, 0.60, 0.55)),
    (("world", "flamenco", "celtic", "fado"), (0.55, 0.60, 0.75)),
    (("gospel", "worship", "christian", "religious"), (0.55, 0.75, 0.58)),
    (("ambient", "drone", "new age"), (0.18, 0.45, 0.68)),
    (("lo-fi", "lofi", "chill", "downtempo", "trip hop", "chillhop"), (0.30, 0.48, 0.62)),
    (("acoustic", "soft rock", "mellow", "adult contemporary", "ballad", "yacht rock"), (0.30, 0.55, 0.55)),
    (("dream pop", "bedroom pop"), (0.42, 0.50, 0.60)),
    (("indie pop",), (0.52, 0.62, 0.55)),
    (("synth", "synthpop", "synth-pop", "new wave"), (0.62, 0.68, 0.45)),
    (("electropop", "dance pop", "dance-pop"), (0.58, 0.80, 0.32)),
    (("k-pop", "kpop", "j-pop", "jpop"), (0.66, 0.80, 0.36)),
    (("schlager", "europop", "eurodance"), (0.58, 0.86, 0.25)),
    (("pop",), (0.55, 0.78, 0.32)),
    (("dance",), (0.78, 0.74, 0.33)),
    (("electronic", "idm", "experimental"), (0.62, 0.50, 0.66)),
]

# Big-Five-Domäne <- (Arousal, Valence, Depth)  (Greenberg 2016, Tabelle A1)
# NUR Domänen mit belastbarem Bezug. Extraversion (r≈.05) und Neurotizismus
# (r≈.05) sind aus Musik praktisch nicht vorhersagbar -> bewusst weggelassen.
AVD_BIGFIVE = {
    "openness":          (0.02,  0.04,  0.13),
    "agreeableness":     (-0.12, -0.02,  0.05),
    "conscientiousness": (-0.08,  0.00,  0.03),
}
# Vielfalt der Präferenzen <- Domäne (Greenberg 2016, Ergebnistext)
DIVERSITY_BIGFIVE = {
    "openness": 0.13, "agreeableness": 0.10, "conscientiousness": 0.03,
}

BIGFIVE_NAMES = {
    "openness": "Offenheit für Erfahrungen",
    "agreeableness": "Verträglichkeit",
    "conscientiousness": "Gewissenhaftigkeit",
}

# MUSIC-Modell (vertrautes Geschmacks-Fingerprint, sekundär)
MUSIC_KEYWORDS = {
    "mellow": ["soul", "r&b", "rnb", "soft rock", "smooth", "lo-fi", "lofi",
               "chill", "ambient", "downtempo", "dream pop", "ballad", "acoustic"],
    "unpretentious": ["country", "folk", "singer-songwriter", "americana",
                      "bluegrass", "schlager", "worship"],
    "sophisticated": ["classical", "jazz", "blues", "opera", "orchestra",
                      "bossa", "world", "soundtrack", "instrumental", "post-rock"],
    "intense": ["rock", "metal", "punk", "hardcore", "grunge", "emo",
                "industrial", "thrash", "metalcore", "hard rock"],
    "contemporary": ["hip hop", "hip-hop", "rap", "trap", "edm", "house",
                     "techno", "dance", "funk", "disco", "reggaeton", "pop",
                     "phonk", "k-pop"],
}
MUSIC_LABELS = {
    "mellow": "Mellow", "unpretentious": "Unpretentious",
    "sophisticated": "Sophisticated", "intense": "Intense",
    "contemporary": "Contemporary",
}


# --------------------------------------------------------------------------- #
# KLEINE HELFER
# --------------------------------------------------------------------------- #
def _clamp(x: float, lo: float = 5.0, hi: float = 95.0) -> int:
    return int(round(max(lo, min(hi, x))))


def weighted_genre_counter(top_artists: dict) -> Counter:
    """Gewichtet Genres über alle drei Zeiträume nach Rang + Zeitfenster."""
    range_factor = {"all_time": 1.0, "letzte_6_monate": 0.6, "letzte_4_wochen": 0.4}
    counter: Counter = Counter()
    for label, factor in range_factor.items():
        for rank, artist in enumerate(top_artists.get(label, [])):
            rank_weight = (50 - rank) * factor
            for g in artist.get("genres", []) or []:
                counter[g] += rank_weight
    return counter


def shannon_entropy_normalized(counter: Counter) -> float:
    total = sum(counter.values())
    if total <= 0 or len(counter) < 2:
        return 0.0
    h = -sum((c / total) * math.log(c / total) for c in counter.values() if c > 0)
    return round(h / math.log(len(counter)), 3)


def gini(values: list[float]) -> float:
    vals = sorted(v for v in values if v is not None)
    n = len(vals)
    if n == 0 or sum(vals) == 0:
        return 0.0
    cum = sum((i + 1) * v for i, v in enumerate(vals))
    return round((2 * cum) / (n * sum(vals)) - (n + 1) / n, 3)


def _slope(series: list[tuple[float, float]]) -> float:
    """Least-squares-Steigung; series = [(x, y), ...]."""
    n = len(series)
    if n < 2:
        return 0.0
    sx = sum(x for x, _ in series)
    sy = sum(y for _, y in series)
    sxx = sum(x * x for x, _ in series)
    sxy = sum(x * y for x, y in series)
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0
    return (n * sxy - sx * sy) / denom


# --------------------------------------------------------------------------- #
# AVD-PROFIL
# --------------------------------------------------------------------------- #
def compute_avd(genre_counter: Counter) -> dict:
    """Gewichteter Mittelwert der Arousal/Valence/Depth über alle Genres."""
    acc = [0.0, 0.0, 0.0]
    matched = 0.0
    n_matched = 0
    for genre, weight in genre_counter.items():
        g = genre.lower()
        hits = [avd for kws, avd in AVD_GENRES if any(kw in g for kw in kws)]
        if not hits:
            continue
        a = sum(h[0] for h in hits) / len(hits)
        v = sum(h[1] for h in hits) / len(hits)
        de = sum(h[2] for h in hits) / len(hits)
        acc[0] += a * weight
        acc[1] += v * weight
        acc[2] += de * weight
        matched += weight
        n_matched += 1
    if matched <= 0:
        return {"arousal": None, "valence": None, "depth": None,
                "coverage": 0.0, "genres_matched": 0}
    return {
        "arousal": round(acc[0] / matched, 3),
        "valence": round(acc[1] / matched, 3),
        "depth": round(acc[2] / matched, 3),
        "coverage": round(matched / max(sum(genre_counter.values()), 1), 3),
        "genres_matched": n_matched,
    }


def compute_music_model(genre_counter: Counter) -> dict:
    scores = {k: 0.0 for k in MUSIC_KEYWORDS}
    for genre, weight in genre_counter.items():
        g = genre.lower()
        hits = [dim for dim, kws in MUSIC_KEYWORDS.items()
                if any(kw in g for kw in kws)]
        if not hits:
            continue
        for dim in hits:
            scores[dim] += weight / len(hits)
    total = sum(scores.values())
    if total <= 0:
        return {"shares": {k: 0.0 for k in scores}, "dominant": None}
    shares = {k: round(v / total, 4) for k, v in scores.items()}
    return {"shares": shares, "dominant": max(shares, key=shares.get)}


# --------------------------------------------------------------------------- #
# BIG FIVE (aus AVD + Vielfalt + Nische)
# --------------------------------------------------------------------------- #
def compute_big_five(avd: dict, genre_entropy: float, mean_pop: float | None,
                     n_genres: int) -> dict:
    if avd.get("arousal") is None:
        return {"traits": {}, "overall_confidence": "keine (zu wenig Genre-Daten)",
                "method": "AVD/Greenberg 2016",
                "disclaimer": "Nicht genug Genre-Daten für eine Schätzung."}

    devA = (avd["arousal"] - 0.5) * 2   # -1..+1
    devV = (avd["valence"] - 0.5) * 2
    devD = (avd["depth"] - 0.5) * 2
    div_dev = (genre_entropy - 0.5) * 2
    niche = (50 - mean_pop) / 50 if mean_pop is not None else 0.0  # +nischig

    GAIN, DIV_GAIN = 180.0, 70.0
    avd_names = {0: ("Arousal/Intensität", devA), 1: ("Valence/Stimmung", devV),
                 2: ("Depth/Tiefe", devD)}

    traits = {}
    for key, (cA, cV, cD) in AVD_BIGFIVE.items():
        contrib = GAIN * (cA * devA + cV * devV + cD * devD)
        contrib += DIV_GAIN * DIVERSITY_BIGFIVE[key] * div_dev
        if key == "openness":
            contrib += 12 * niche  # Nische -> Offenheit (Rentfrow & Gosling)
        score = _clamp(50 + contrib)

        # Treiber: welcher AVD-Anteil trägt am stärksten (betragsmäßig) bei
        parts = [(cA * devA, "hohe Intensität" if devA > 0 else "ruhige Musik", "Arousal"),
                 (cV * devV, "fröhliche Musik" if devV > 0 else "melancholische Musik", "Valence"),
                 (cD * devD, "tiefe/komplexe Musik" if devD > 0 else "eingängige Musik", "Depth")]
        parts.sort(key=lambda t: abs(t[0]), reverse=True)
        drivers = []
        for val, label, _dim in parts[:2]:
            if abs(val) < 0.005:
                continue
            sign = "+" if val > 0 else "−"
            drivers.append(f"{sign} {label}")
        if key in ("openness", "agreeableness") and abs(div_dev) > 0.15:
            drivers.append(("+ " if div_dev > 0 else "− ") + "Genre-Vielfalt")
        if key == "openness" and abs(niche) > 0.15:
            drivers.append(("+ " if niche > 0 else "− ") + "Nischen-Neigung")

        traits[key] = {
            "name": BIGFIVE_NAMES[key],
            "score": score,
            "confidence": _trait_confidence(key, n_genres, avd["coverage"]),
            "drivers": drivers or ["kaum ausgeprägte Signale"],
        }

    if n_genres >= 25 and avd["coverage"] >= 0.6:
        overall = "moderat (für eine Schätzung gut belegt)"
    elif n_genres >= 12:
        overall = "niedrig (begrenzte Genre-Datenbasis)"
    else:
        overall = "sehr niedrig (zu wenig Genre-Daten)"

    return {
        "traits": traits,
        "overall_confidence": overall,
        "method": "AVD-Modell (Greenberg et al. 2016, Tab. A1)",
        "disclaimer": (
            "Nur Merkmale mit belastbarem Bezug werden gezeigt: Offenheit "
            "(robust, über Depth r≈.13), Verträglichkeit und Gewissenhaftigkeit "
            "(schwach, über Arousal r≈−.12/−.08). Extraversion und Neurotizismus "
            "sind aus Musik kaum vorhersagbar (r≈.05) und werden weggelassen. "
            "Tendenzen, keine Diagnose - der Bezug gilt nur über Gruppen, nicht "
            "für Einzelpersonen, und hängt stark von Alter/Kultur/Lebensphase ab."
        ),
    }


def _trait_confidence(key: str, n_genres: int, coverage: float) -> str:
    base = {"openness": "moderat", "agreeableness": "niedrig",
            "conscientiousness": "niedrig"}[key]
    if n_genres < 12 or coverage < 0.4:
        return "sehr niedrig (dünne Datenbasis)"
    return base


# --------------------------------------------------------------------------- #
# LEBENSPHASE / ALTER
# --------------------------------------------------------------------------- #
def estimate_life_phase(saved: list, avd: dict) -> dict:
    """Schätzt prägende Musikjahre + grobe Altersspanne.

    Grundlage: Reminiscence Bump (stärkste Bindung an Musik aus ~Alter 14-24).
    Der frühere AVD-Alters-Lean wurde entfernt (statistisch zu schwach).
    """
    now_year = datetime.now().year
    out: dict = {"now_year": now_year}

    years = [t["release_year"] for t in saved if t.get("release_year")]
    if len(years) >= 25:
        hist = Counter(years)
        lo, hi = min(years), max(years)
        # 5-Jahres-Fenster mit der höchsten Masse suchen
        best_center, best_mass = lo, -1
        for c in range(lo, hi + 1):
            mass = sum(hist.get(y, 0) for y in range(c - 2, c + 3))
            if mass > best_mass:
                best_mass, best_center = mass, c
        formative_peak = best_center
        bump_share = round(best_mass / len(years), 3)
        # Reminiscence Bump: Musik des Peaks ~ Alter 14-24 erlebt
        age_low = now_year - (formative_peak - 14)
        age_high = now_year - (formative_peak - 24)
        age_center = now_year - (formative_peak - 19)
        plausible = 12 <= age_center <= 90
        out["reminiscence"] = {
            "formative_peak_year": formative_peak,
            "formative_window": [formative_peak - 2, formative_peak + 2],
            "bump_share": bump_share,
            "release_year_range": [lo, hi],
            "estimated_age_range": [age_low, age_high] if plausible else None,
            "estimated_age_center": age_center if plausible else None,
            "estimated_birth_year": formative_peak - 19 if plausible else None,
            "interpretation": (
                "Grobe Schätzung über den 'Reminiscence Bump': stärkste "
                "musikalische Prägung erfolgt typischerweise mit ~14-24 Jahren. "
                "Sehr unsicher - viele hören auch viel aktuelle Musik."
            ),
        }
    return out


# --------------------------------------------------------------------------- #
# TRENDS (aus added_at der Bibliothek)
# --------------------------------------------------------------------------- #
def compute_trends(saved: list) -> dict:
    rows = []
    for t in saved:
        ts = t.get("added_at")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        rows.append((dt, t))
    if len(rows) < 12:
        return {}
    rows.sort(key=lambda r: r[0])

    by_year: dict[int, list] = {}
    for dt, t in rows:
        by_year.setdefault(dt.year, []).append((dt, t))

    cohorts = []
    seen_artists: set[str] = set()
    for year in sorted(by_year):
        items = by_year[year]
        pops = [t["popularity"] for _, t in items if t.get("popularity") is not None]
        music_age = [year - t["release_year"] for _, t in items if t.get("release_year")]
        new_artists = 0
        for _, t in items:
            for a in t.get("artists", []):
                if a not in seen_artists:
                    seen_artists.add(a)
                    new_artists += 1
        cohorts.append({
            "year": year,
            "added": len(items),
            "median_popularity": (sorted(pops)[len(pops) // 2] if pops else None),
            "median_music_age": (sorted(music_age)[len(music_age) // 2] if music_age else None),
            "new_artists": new_artists,
        })

    def trend(key, rising, falling, thresh=0.5):
        pts = [(i, c[key]) for i, c in enumerate(cohorts) if c[key] is not None]
        if len(pts) < 2:
            return None
        s = _slope(pts)
        lbl = rising if s > thresh else falling if s < -thresh else "stabil"
        return {"label": lbl, "slope": round(s, 2)}

    summary = {}
    pop = trend("median_popularity", "zunehmend Mainstream", "zunehmend nischig")
    if pop:  # nur wenn Popularität verfügbar (Spotify liefert sie für Dev-Apps nicht mehr)
        summary["mainstream_trend"] = pop
    summary["nostalgia_trend"] = trend(
        "median_music_age", "zunehmend retrospektiv/nostalgisch",
        "zunehmend auf aktuelle Releases fokussiert")
    summary["engagement_trend"] = trend(
        "added", "steigendes Sammel-Tempo", "nachlassendes Sammel-Tempo", thresh=1.0)
    summary["discovery_trend"] = trend(
        "new_artists", "zunehmend explorativ (mehr neue Artists)",
        "zunehmend gefestigt (weniger neue Artists)", thresh=1.0)

    return {
        "cohorts": cohorts,
        "summary": {k: v for k, v in summary.items() if v},
        "hinweis": (
            "Trends aus dem Speicher-Zeitpunkt (added_at). 'Musik-Alter beim "
            "Speichern' = wie alt ein Titel beim Hinzufügen war (hoch = "
            "retrospektiv). Engagement-Verlauf vgl. Bonneville-Roussy 2013."
        ),
    }


# --------------------------------------------------------------------------- #
# REPLAY-VERHALTEN (aus recently_played, nur letzte 50)
# --------------------------------------------------------------------------- #
def compute_replay(recently: list) -> dict:
    """Analysiert Wiederholungs-/Dauerschleifen-Verhalten der letzten Plays.

    Hinweis: Spotify gibt nur die letzten 50 Wiedergaben zurück - das ist
    genau das Fenster, das auch die 'On Repeat'-Playlist speist. Aktuelle
    'Obsession'-Tracks erscheinen hier, in den API-Top-Tracks aber oft nicht.
    """
    plays = [(r.get("track"), tuple(r.get("artists") or []), r.get("played_at"))
             for r in recently if r.get("track")]
    total = len(plays)
    if total < 5:
        return {}

    track_counts = Counter((t, a) for t, a, _ in plays)
    unique = len(track_counts)
    repeat_rate = round(1 - unique / total, 2)

    # Back-to-back-Loops (gleicher Track direkt hintereinander)
    loops, cur, max_streak, streak_track = 0, 1, 1, None
    for i in range(1, total):
        same = (plays[i][0], plays[i][1]) == (plays[i - 1][0], plays[i - 1][1])
        if same:
            loops += 1
            cur += 1
            if cur > max_streak:
                max_streak, streak_track = cur, plays[i][0]
        else:
            cur = 1

    artist_counts: Counter = Counter()
    for _t, arts, _ in plays:
        for a in arts:
            artist_counts[a] += 1

    # Zeitfenster
    times = []
    for _t, _a, ts in plays:
        if not ts:
            continue
        try:
            times.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
        except ValueError:
            pass
    span_hours = None
    plays_per_hour = None
    if len(times) >= 2:
        span_hours = round((max(times) - min(times)).total_seconds() / 3600, 1)
        if span_hours and span_hours > 0:
            plays_per_hour = round(total / span_hours, 2)

    if repeat_rate >= 0.5:
        intensity = "sehr hoch (starke Wiederholung / Dauerschleifen)"
    elif repeat_rate >= 0.3:
        intensity = "hoch (klare Lieblinge in Rotation)"
    elif repeat_rate >= 0.15:
        intensity = "mittel (Mix aus Wiederholung und Neuem)"
    else:
        intensity = "niedrig (viel Abwechslung, wenig Wiederholung)"

    most = [[t, " / ".join(a), c] for (t, a), c in track_counts.most_common(8) if c > 1]
    obsession = None
    if track_counts:
        (t, a), c = track_counts.most_common(1)[0]
        if c >= 3:
            obsession = {"track": t, "artists": " / ".join(a), "plays": c}

    return {
        "window_plays": total,
        "unique_tracks": unique,
        "repeat_rate": repeat_rate,
        "intensity": intensity,
        "back_to_back_loops": loops,
        "longest_streak": {"plays": max_streak, "track": streak_track} if max_streak > 1 else None,
        "most_replayed": most,
        "top_artists_recent": artist_counts.most_common(8),
        "unique_artists": len(artist_counts),
        "obsession": obsession,
        "span_hours": span_hours,
        "plays_per_hour": plays_per_hour,
        "hinweis": ("Basiert auf den letzten 50 Wiedergaben (API-Limit) - das "
                    "gleiche Fenster wie Spotifys 'On Repeat'. Erklärt, warum "
                    "aktuelle Dauerschleifen hier auftauchen, in den 'all-time' "
                    "Top-Tracks der API aber nicht."),
    }


# --------------------------------------------------------------------------- #
# HAUPT-STATISTIK
# --------------------------------------------------------------------------- #
def compute_patterns(top_tracks: dict, top_artists: dict,
                     recently: list, saved: list) -> dict:
    p: dict = {}

    genre_counter = weighted_genre_counter(top_artists)
    p["genre_ranking"] = [[g, round(w, 1)] for g, w in genre_counter.most_common(25)]
    p["genre_count"] = len(genre_counter)
    p["genre_entropy"] = shannon_entropy_normalized(genre_counter)
    if not genre_counter:
        p["genre_ranking_hinweis"] = "Keine Genres im Top-Artists-Payload gefunden."

    # Popularität (Top-Tracks aller Zeiträume + Bibliothek)
    all_pops = []
    for label in ("all_time", "letzte_6_monate", "letzte_4_wochen"):
        all_pops += [t["popularity"] for t in top_tracks.get(label, [])
                     if t.get("popularity") is not None]
    lib_pops = [t["popularity"] for t in saved if t.get("popularity") is not None]
    combined = all_pops + lib_pops
    if combined:
        srt = sorted(combined)
        hist = Counter(min(pp // 10 * 10, 90) for pp in combined)
        p["popularity"] = {
            "mittelwert": round(sum(combined) / len(combined), 1),
            "median": srt[len(srt) // 2],
            "min": min(combined), "max": max(combined), "stichprobe": len(combined),
            "histogramm": [[b, hist.get(b, 0)] for b in range(0, 100, 10)],
            "interpretation_hinweis": "0=sehr nischig, 100=sehr mainstream",
        }

    # Ära (Top-Tracks)
    years = [t["release_year"] for t in top_tracks.get("all_time", [])
             if t.get("release_year")]
    if years:
        p["release_decades"] = sorted(Counter((y // 10) * 10 for y in years).items())
        p["release_year_span"] = {"min": min(years), "max": max(years),
                                  "median": sorted(years)[len(years) // 2]}

    # Explicit-Anteil bevorzugt aus der ganzen Bibliothek (mehr Datenpunkte)
    flags = [t["explicit"] for t in saved if t.get("explicit") is not None]
    if not flags:
        flags = [t["explicit"] for t in top_tracks.get("all_time", [])
                 if t.get("explicit") is not None]
    if flags:
        p["explicit_ratio"] = round(sum(flags) / len(flags), 2)
        p["explicit_n"] = len(flags)

    durs = [t["duration_min"] for t in saved if t.get("duration_min")]
    if durs:
        p["avg_track_duration_min"] = round(sum(durs) / len(durs), 2)

    # Stabilität über 3 Zeiträume
    sa = {a["name"] for a in top_artists.get("letzte_4_wochen", [])}
    ma = {a["name"] for a in top_artists.get("letzte_6_monate", [])}
    la = {a["name"] for a in top_artists.get("all_time", [])}
    if sa and la:
        overlap_sl = sa & la
        p["taste_stability"] = {
            "ueberschneidung_artists": len(overlap_sl),
            "von_kurzfrist_top": len(sa),
            "kurz_vs_alltime_pct": round(100 * len(overlap_sl) / max(len(sa), 1)),
            "mittel_vs_alltime_pct": round(100 * len(ma & la) / max(len(ma), 1)),
            "gemeinsam": sorted(overlap_sl),
            "interpretation_hinweis": (
                "Hohe Überschneidung = stabiler Geschmack; "
                "niedrige = aktuell explorative Phase."),
        }

    # Hörzeiten (nur letzte 50)
    hour_counter: Counter = Counter()
    weekday_counter: Counter = Counter()
    for item in recently:
        ts = item.get("played_at")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            continue
        hour_counter[dt.hour] += 1
        weekday_counter[dt.weekday()] += 1
    if hour_counter:
        p["listening_by_hour"] = [[h, hour_counter.get(h, 0)] for h in range(24)]
        buckets = {"nacht_0_6": 0, "morgen_6_12": 0,
                   "nachmittag_12_18": 0, "abend_18_24": 0}
        for h, c in hour_counter.items():
            key = ("nacht_0_6" if h < 6 else "morgen_6_12" if h < 12
                   else "nachmittag_12_18" if h < 18 else "abend_18_24")
            buckets[key] += c
        p["listening_by_daytime"] = buckets
        p["listening_by_weekday"] = [weekday_counter.get(i, 0) for i in range(7)]
        p["listening_by_daytime_hinweis"] = \
            "Basiert nur auf den letzten 50 Wiedergaben - nur grobe Tendenz."

    # Bibliothek
    if saved:
        saved_artists: Counter = Counter()
        for t in saved:
            for a in t.get("artists", []):
                saved_artists[a] += 1
        p["library"] = {
            "gespeicherte_titel": len(saved),
            "unterschiedliche_artists": len(saved_artists),
            "top_artists_in_bibliothek": saved_artists.most_common(15),
            "artist_konzentration_gini": gini([float(c) for c in saved_artists.values()]),
            "top15_anteil_pct": round(
                100 * sum(c for _, c in saved_artists.most_common(15)) / max(len(saved), 1)),
        }
        by_year: Counter = Counter()
        by_month: Counter = Counter()
        for t in saved:
            ts = t.get("added_at")
            if not ts:
                continue
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                continue
            by_year[dt.year] += 1
            by_month[f"{dt.year}-{dt.month:02d}"] += 1
        if by_year:
            p["library_added_by_year"] = sorted(by_year.items())
            p["library_added_by_month_recent"] = sorted(by_month.items())[-24:]
        lib_years = [t["release_year"] for t in saved if t.get("release_year")]
        if lib_years:
            p["library_release_eras_5y"] = sorted(
                Counter((y // 5) * 5 for y in lib_years).items())
            p["library_release_decades"] = sorted(
                Counter((y // 10) * 10 for y in lib_years).items())
            srt = sorted(lib_years)
            p["library_release_year_stats"] = {
                "frühestes": srt[0], "spätestes": srt[-1],
                "median": srt[len(srt) // 2], "anzahl_mit_jahr": len(lib_years)}

    # --- AVD + MUSIC + Big Five + Lebensphase + Trends ---------------------
    avd = compute_avd(genre_counter)
    p["avd_profile"] = avd
    music = compute_music_model(genre_counter)
    p["music_model"] = {"shares": music["shares"], "labels": MUSIC_LABELS,
                        "dominant": music["dominant"]}
    mean_pop = p.get("popularity", {}).get("mittelwert")
    p["big_five"] = compute_big_five(avd, p["genre_entropy"], mean_pop, len(genre_counter))
    p["life_phase"] = estimate_life_phase(saved, avd)
    p["trends"] = compute_trends(saved)
    p["replay"] = compute_replay(recently)

    return p
