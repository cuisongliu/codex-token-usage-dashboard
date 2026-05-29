$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskName = "CodexTokenUsageDashboard"

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null

Write-Host "Uninstalled Windows Scheduled Task: $TaskName"
Write-Host "Local config and usage data were kept in $RootDir."
