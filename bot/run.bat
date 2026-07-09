@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Run install.bat first.
    exit /b 1
)

if not exist ".env" (
    echo .env not found. Copy .env.example to .env and fill in secrets.
    exit /b 1
)

call .venv\Scripts\activate.bat
python publish_bot.py
