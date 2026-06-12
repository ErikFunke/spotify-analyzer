#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py
======

Hübsches Web-Dashboard für dein Spotify-Musikprofil.

  * Integrierter Spotify-OAuth-Flow (Redirect auf /callback, Port 8888)
  * Liest/erzeugt spotify_export.json
  * Zeigt alle Statistiken + MUSIC-Modell + Big-Five-Tendenzen mit Charts

Start:  python spotify.py --web        (oder direkt: python app.py)
"""

from __future__ import annotations

import threading
import time
import webbrowser

from flask import (Flask, jsonify, redirect, render_template, request,
                   url_for)

import spotify as core

app = Flask(__name__, template_folder="templates", static_folder="static")

# Hintergrund-Job-Status fürs "Daten aktualisieren"
_job = {"running": False, "log": [], "done": False, "error": None,
        "started": None}
_lock = threading.Lock()


# --------------------------------------------------------------------------- #
# AUTH-HELFER
# --------------------------------------------------------------------------- #
def _oauth():
    return core.make_oauth(open_browser=False)


def _has_token() -> bool:
    try:
        tok = _oauth().get_cached_token()
        return bool(tok)
    except Exception:
        return False


def _spotify_client():
    return core.spotipy.Spotify(auth_manager=_oauth(), requests_timeout=20, retries=3)


# --------------------------------------------------------------------------- #
# REFRESH-JOB
# --------------------------------------------------------------------------- #
def _run_refresh(source: str = "api", history_dir: str = ""):
    def log(msg):
        with _lock:
            _job["log"].append(str(msg))
    try:
        if source == "history":
            log(">> Quelle: Extended Streaming History (Download)")
            core.build_history_profile(history_dir or None, log=log)
        elif source == "combined":
            log(">> Quelle: API-Favoriten + Streaming-History (kombiniert)")
            sp = _spotify_client()
            profile = core.build_combined_profile(sp, history_dir or None, log=log)
            core.save_profile(profile)
        else:
            sp = _spotify_client()
            profile = core.build_profile(sp, log=log)
            core.save_profile(profile)
        with _lock:
            _job["done"] = True
        log(">> Fertig.")
    except Exception as e:  # noqa: BLE001
        with _lock:
            _job["error"] = str(e)
        log(f"!! Fehler: {e}")
    finally:
        with _lock:
            _job["running"] = False


# --------------------------------------------------------------------------- #
# ROUTES
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    profile = core.load_profile()
    if profile is not None and not request.args.get("setup"):
        return render_template("dashboard.html", profile=profile)

    has_creds = bool(core.CONFIG["client_id"] and core.CONFIG["client_secret"])
    has_token = has_creds and _has_token()
    auth_url = _oauth().get_authorize_url() if (has_creds and not has_token) else None
    return render_template(
        "start.html",
        has_creds=has_creds,
        has_token=has_token,
        auth_url=auth_url,
        redirect_uri=core.CONFIG["redirect_uri"],
        default_history_dir=core.CONFIG["history_dir"],
        has_profile=profile is not None,
    )


@app.route("/callback")
def callback():
    code = request.args.get("code")
    error = request.args.get("error")
    if error:
        return f"Spotify-Login abgebrochen: {error}", 400
    if not code:
        return redirect(url_for("index"))
    try:
        _oauth().get_access_token(code, as_dict=False)
    except Exception as e:  # noqa: BLE001
        return f"Token-Austausch fehlgeschlagen: {e}", 500
    return redirect(url_for("index"))


@app.route("/api/data")
def api_data():
    profile = core.load_profile()
    if profile is None:
        return jsonify({"error": "no_data"}), 404
    return jsonify(profile)


@app.route("/api/llm-prompt")
def api_llm_prompt():
    profile = core.load_profile()
    if profile is None:
        return jsonify({"error": "no_data"}), 404
    md = core.build_llm_markdown(profile)
    dl = request.args.get("download")
    resp = app.response_class(md, mimetype="text/markdown; charset=utf-8")
    if dl:
        resp.headers["Content-Disposition"] = "attachment; filename=music_profile_for_llm.md"
    return resp


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    body = request.get_json(silent=True) or request.form
    source = (body.get("source") or "api").strip()
    history_dir = (body.get("history_dir") or "").strip()

    if source in ("history", "combined"):
        path = history_dir or core.CONFIG["history_dir"]
        if not path:
            return jsonify({"error": "no_history_dir"}), 400
        import history as hist
        if not hist.find_history_files(path):
            return jsonify({"error": "history_not_found", "path": path}), 400
    if source in ("api", "combined"):
        if not _has_token():
            return jsonify({"error": "not_authenticated"}), 401

    with _lock:
        if _job["running"]:
            return jsonify({"status": "already_running"})
        _job.update({"running": True, "log": [], "done": False,
                     "error": None, "started": time.time()})
    threading.Thread(target=_run_refresh, args=(source, history_dir),
                     daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/refresh/status")
def api_refresh_status():
    with _lock:
        return jsonify(dict(_job))


@app.route("/logout")
def logout():
    try:
        (core.BASE_DIR / ".spotify_cache").unlink(missing_ok=True)
    except Exception:
        pass
    return redirect(url_for("index"))


# --------------------------------------------------------------------------- #
# START
# --------------------------------------------------------------------------- #
def run(port: int = 8888, open_browser: bool = True):
    url = f"http://127.0.0.1:{port}/"
    print("=" * 64)
    print(" Spotify Dashboard läuft auf:  " + url)
    print(" (Strg+C zum Beenden)")
    print("=" * 64)
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    # threaded=True, damit Refresh-Job + Requests parallel laufen
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    run()
