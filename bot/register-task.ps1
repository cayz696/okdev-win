#Requires -RunAsAdministrator
#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$BotDir = $PSScriptRoot
$Python = Join-Path $BotDir ".venv\Scripts\python.exe"
$Script = Join-Path $BotDir "publish_bot.py"
$TaskName = "OkdevBlogBot"

$Action = New-ScheduledTaskAction -Execute $Python -Argument $Script -WorkingDirectory $BotDir
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -RunLevel Highest -Force

Write-Host "Task '$TaskName' registered. Starts on boot." -ForegroundColor Green
Write-Host "Start now: Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Cyan
