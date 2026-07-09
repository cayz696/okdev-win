@echo off
REM Full setup from scratch via CMD
REM Usage: setup.bat [target_folder]
REM Example: setup.bat C:\okdev-bot

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=C:\okdev-bot"

echo === Clone repo ===
if not exist "%TARGET%" mkdir "%TARGET%"
cd /d "%TARGET%"

if exist ".git" (
    echo Updating existing repo...
    git pull
) else (
    git clone https://github.com/cayz696/okdev-win.git .
)

cd /d "%TARGET%\bot"
call install.bat
echo.
echo === Ready ===
echo Edit .env if needed, then run:
echo   cd /d %TARGET%\bot
echo   run.bat
