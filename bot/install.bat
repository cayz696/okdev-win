@echo off
cd /d "%~dp0"
echo === okdev.win blog bot install ===

where python >nul 2>&1
if errorlevel 1 (
    echo Python not found. Install Python 3.11+ and add to PATH.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

if not exist "data" mkdir data

if not exist ".env" (
    if exist ".env.example" copy /Y ".env.example" ".env"
    echo Created .env - fill in your secrets!
) else (
    echo .env already exists - kept as is.
)

echo Done. Run: run.bat
exit /b 0
