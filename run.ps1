# ===================================================================
#  Spotify Musikprofil - PowerShell-Starter
#  Start:  Rechtsklick > "Mit PowerShell ausfuehren"
#          oder:  powershell -ExecutionPolicy Bypass -File run.ps1
# ===================================================================
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$py = (Get-Command py -ErrorAction SilentlyContinue) ? "py" : "python"

if (-not (Test-Path ".venv")) {
    Write-Host "[Setup] Erstelle virtuelle Umgebung ..." -ForegroundColor Cyan
    & $py -m venv .venv
    & ".\.venv\Scripts\Activate.ps1"
    Write-Host "[Setup] Installiere Abhaengigkeiten ..." -ForegroundColor Cyan
    python -m pip install --upgrade pip | Out-Null
    python -m pip install -r requirements.txt
} else {
    & ".\.venv\Scripts\Activate.ps1"
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[Hinweis] .env erstellt - bitte Zugangsdaten eintragen." -ForegroundColor Yellow
    notepad ".env"
    Read-Host "Enter druecken, wenn .env ausgefuellt ist"
}

Write-Host "[Start] Web-Dashboard wird gestartet ..." -ForegroundColor Green
python spotify.py --web
