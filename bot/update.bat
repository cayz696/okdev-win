@echo off
cd /d "%~dp0.."
git pull
cd bot
call install.bat
echo.
echo Restart bot: close run.bat window and start run.bat again.
