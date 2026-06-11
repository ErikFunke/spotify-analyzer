#!/usr/bin/env bash
# Linux/macOS-Starter fürs Spotify-Dashboard
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "[Setup] Erstelle virtuelle Umgebung ..."
  python3 -m venv .venv
  source .venv/bin/activate
  echo "[Setup] Installiere Abhängigkeiten ..."
  pip install --upgrade pip >/dev/null
  pip install -r requirements.txt
else
  source .venv/bin/activate
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "[Hinweis] .env erstellt – bitte Zugangsdaten eintragen, dann erneut starten."
  exit 0
fi

echo "[Start] Web-Dashboard ..."
python spotify.py --web
