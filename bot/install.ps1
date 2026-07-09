#Requires -Version 5.1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== okdev.win blog bot install ===" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found. Install Python 3.11+ and add to PATH." -ForegroundColor Red
    exit 1
}

python -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env — fill in your secrets!" -ForegroundColor Yellow
}

New-Item -ItemType Directory -Force -Path "data" | Out-Null
Write-Host "Done. Edit .env then run: .\run.ps1" -ForegroundColor Green
