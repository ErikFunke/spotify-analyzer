@echo off
REM ===================================================================
REM  Spotify Musikprofil - Windows-Starter (Doppelklick)
REM ===================================================================
setlocal
cd /d "%~dp0"

REM Python finden (py-Launcher bevorzugt)
where py >nul 2>nul && (set "PY=py") || (set "PY=python")

REM venv anlegen beim ersten Start
if not exist ".venv\" (
  echo [Setup] Erstelle virtuelle Umgebung ...
  %PY% -m venv .venv
  call ".venv\Scripts\activate.bat"
  echo [Setup] Installiere Abhaengigkeiten ...
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
) else (
  call ".venv\Scripts\activate.bat"
)

REM .env pruefen
if not exist ".env" (
  echo.
  echo [Hinweis] Keine .env gefunden. Kopiere .env.example zu .env
  echo           und trage deine Spotify-Zugangsdaten ein.
  copy ".env.example" ".env" >nul
  echo [Hinweis] .env wurde erstellt. Bitte jetzt ausfuellen, dann erneut starten.
  notepad ".env"
  pause
  exit /b
)

echo [Start] Web-Dashboard wird gestartet ...
python spotify.py --web

pause
