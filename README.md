# 🎧 Spotify Music Profile & Personality Dashboard

Reads your personal Spotify data (read-only), computes detailed listening
statistics and **evidence-based** personality tendencies **entirely on your
machine**, and shows everything in a polished web dashboard. Also generates a
ready-to-paste LLM analysis prompt.

> **What Spotify no longer provides** (as of 2026, for Development-Mode apps):
> audio features (`audio-features`, gone since 2024), artist **genres**,
> artist popularity, followers, and track **popularity** were removed
> (`/artists` returns 403; `genres`/`popularity` come back empty). Still
> available: top lists, recently played, your library, release years, track
> length, the explicit flag, and cover art.
>
> **Genre gap closed:** genres are fetched from an external source
> (MusicBrainz, no key required; Last.fm optional) and cached in
> `.genre_cache.json`. This is what makes the AVD/personality analysis work
> again. The mainstream-vs-niche dimension is dropped since popularity is gone.

## Features

- **Web dashboard** (dark, animated, Chart.js): genres, era preferences,
  library timeline, listening times, weekdays, diversity, and top lists.
- **Evidence-based personality**: an **AVD model** (Arousal / Valence / Depth,
  Greenberg et al. 2016) is estimated from your genres, then mapped to the Big
  Five using the **empirical correlations from the paper** (Table A1) — not
  guesswork. Only the three traits with a defensible signal are shown
  (Openness, Agreeableness, Conscientiousness); Extraversion and Neuroticism
  are deliberately omitted because music barely predicts them (r ≈ .05).
  Each trait comes with a confidence label and the drivers behind it.
- **Life phase & age**: a rough age estimate via the *reminiscence bump*
  (formative musical years ≈ ages 14–24), derived from your library's
  release-year distribution.
- **Replay behavior**: from your recently played tracks (last 50 — the same
  window Spotify's "On Repeat" uses): repeat rate, current obsession,
  back-to-back loops, longest streak, plays/hour.
- **Listening trends**: from save timestamps (`added_at`): nostalgia vs.
  novelty (how old tracks are when you save them), collection pace, and
  discovery rate — cf. Bonneville-Roussy et al. (2013).
- **"LLM Analysis" button**: builds a complete prompt (copy or download) with
  your key stats + the empirical correlation tables + the analysis task, so any
  LLM can do the write-up correctly.
- **Integrated login**: OAuth runs straight in the browser via the dashboard.
- **Cross-platform**: Windows launchers (`run.bat` / `run.ps1`), `.env`
  support, UTF-8 console, script-relative paths.

## Quick start

First, create a Spotify app at
<https://developer.spotify.com/dashboard> → **Create app**, and set the
Redirect URI to exactly `http://127.0.0.1:8888/callback`. Note the **Client ID**
and **Client Secret**.

### Windows
1. **Double-click `run.bat`** — it creates a virtualenv, installs dependencies,
   and on first run opens `.env` for you to fill in (Client ID / Secret).
2. Run `run.bat` again → the browser opens the dashboard → log in with Spotify.

### Linux / macOS
```bash
cp .env.example .env      # fill in Client ID / Secret
./run.sh                  # or manually:
# python3 -m venv .venv && source .venv/bin/activate
# pip install -r requirements.txt
# python spotify.py --web
```

## Usage

| Command | What it does |
|---|---|
| `python spotify.py --web` | Start the web dashboard (opens the browser) |
| `python spotify.py` | Collect data only → `spotify_export.json` + `music_profile_for_llm.md` |
| `python spotify.py --web --port 9000` | Use another port (update the Redirect URI in your Spotify app!) |
| `python spotify.py --web --no-browser` | Don't open the browser automatically |
| `python spotify.py --history <DIR>` | Build the profile from the **Extended Streaming History** download instead of the Web API |
| `python spotify.py --combined <DIR>` | **Combine both** — API favorites/top + full streaming history (best data basis) |
| `python spotify.py --reprocess file.json` | Re-analyze an existing export + fetch genres (no new Spotify call) |

### Three data sources

When you open the dashboard with no profile yet (or click **⇄ Quelle**), you pick
a source:

* **🔗 Web API (live)** — top lists, recently played, library. Fast, but limited:
  only the last 50 plays for listening times.
* **📂 Extended Streaming History (download)** — your *real* plays across **all
  years**. Request it under *Spotify → Account → Privacy → Extended streaming
  history*; unzip it and point the app at the folder containing
  `Streaming_History_Audio_*.json`. Adds true listening times, skip rate, hours
  listened, per-year volume and a discovery timeline. On its own the download has
  no release years / popularity, so age estimate and mainstream drift are off.
* **🔀 Combined (recommended)** — both at once. The two carry *different*
  meaning and are kept **strictly separate**, including in the LLM analysis:
  * **API = declared favorites / taste** (top lists + saved library, *with*
    release years → personality, age estimate and mainstream stay available).
  * **History = everything ever played** (behaviour/volume incl. background &
    skips → listening times, hours, skip rate, most-played).
  The LLM prompt is told to treat favorites ≠ total plays and to comment on the
  *gap* (e.g. what plays a lot but isn't a favorite).

Genres are enriched externally in every mode. Pre-fill the history folder via
`SPOTIFY_HISTORY_DIR` in `.env`.

In the dashboard, the **⟳ button** refreshes the data live (using the current
profile's source), and the **🧠 LLM Analysis** button opens the ready-made
prompt (copy / download).

> **Note:** the first real data fetch enriches genres via MusicBrainz at
> ~1 request/second (a few minutes for ~100 artists); results are cached, so
> later runs are instant. Set a free `LASTFM_API_KEY` in `.env` for faster
> enrichment with better tags.

## Personality, age & trends — the science

**Method.** An **AVD profile** (Arousal / Valence / Depth) is estimated from
your genres, then mapped to the Big Five using the *empirical* correlations from
Greenberg et al. (2016), *The Song Is You*, Table A1. Only the traits with a
defensible link are reported:

| Trait | Arousal | Valence | Depth |
|---|---|---|---|
| Openness | +.02 | +.04 | **+.13** |
| Agreeableness | **−.12** | −.02 | +.05 |
| Conscientiousness | −.08 | .00 | +.03 |

Extraversion and Neuroticism correlate only ~r .05 with musical attributes, so
they are **left out** rather than guessed. Diversity → trait: Openness +.13,
Agreeableness +.10.

**Life phase** is estimated via the *reminiscence bump* (strongest musical
imprinting at ~14–24 years → formative years / age range). **Trends** draw on
Bonneville-Roussy et al. (2013): intense/contemporary music peaks in youth,
sophisticated/unpretentious rises with age, and musical engagement declines.

**Caution.** These effects are small (r ≈ .05–.20) and only hold across groups —
**not a diagnosis** of any individual. Openness (via Depth) is the most robust;
everything else is weak. Audio features (energy/tempo) are unavailable (Spotify
removed `audio-features` in 2024), so AVD is approximated from genres here. Read
everything as a **tendency**, not a fact.

Source: Greenberg, D. M., Kosinski, M., Stillwell, D. J., Monteiro, B. L.,
Levitin, D. J., & Rentfrow, P. J. (2016). *The Song Is You: Preferences for
Musical Attribute Dimensions Reflect Personality.* Social Psychological and
Personality Science, 7(6), 597–605.
[doi:10.1177/1948550616641473](https://doi.org/10.1177/1948550616641473)

## Project layout

```
spotify.py        Data fetching + CLI + entry point (--web, --history, --reprocess)
history.py        Build the profile from the Extended Streaming History download
analysis.py       Statistics + AVD model + Big Five + life phase + trends + replay
genres.py         Genre enrichment (MusicBrainz / Last.fm) with caching
app.py            Flask web dashboard + OAuth (/callback) + LLM-prompt endpoint
templates/        dashboard.html, start.html, connect.html, setup.html
static/           css/style.css, js/dashboard.js
requirements.txt  Dependencies
run.bat/.ps1/.sh  Launchers
.env.example      Credentials template
LICENSE           MIT
```

## Privacy

All data is processed locally and stored on your machine only
(`spotify_export.json`, `.spotify_cache`, `.genre_cache.json`). Nothing is
uploaded. These files plus your `.env` are git-ignored, so your credentials and
personal data won't be committed.

## License

No license file is included yet. Add one (e.g. MIT) before publishing if you
want others to reuse the code.
