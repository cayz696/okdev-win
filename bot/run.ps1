#Requires -Version 5.1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
& .\.venv\Scripts\Activate.ps1
python publish_bot.py
